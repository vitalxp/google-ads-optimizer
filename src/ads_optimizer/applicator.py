from __future__ import annotations

from dataclasses import dataclass

from google.ads.googleads.client import GoogleAdsClient

from ads_optimizer.models import ActionType, Recommendation


@dataclass(slots=True)
class ApplyResult:
    recommendation: Recommendation
    success: bool
    message: str


def apply_recommendations(
    client: GoogleAdsClient,
    customer_id: str,
    recommendations: list[Recommendation],
    *,
    dry_run: bool = True,
) -> list[ApplyResult]:
    results: list[ApplyResult] = []
    for rec in recommendations:
        if dry_run:
            results.append(
                ApplyResult(rec, True, f"[dry-run] Would apply {rec.action.value}")
            )
            continue
        try:
            message = _apply_one(client, customer_id, rec)
            results.append(ApplyResult(rec, True, message))
        except Exception as exc:  # noqa: BLE001 - surface API errors to CLI
            results.append(ApplyResult(rec, False, _short_error(exc)))
    return results


def _short_error(exc: Exception) -> str:
    text = str(exc)
    for line in text.splitlines():
        if "message:" in line:
            return line.split("message:", 1)[-1].strip().strip('"')
    return text[:500]


def _set_update_mask(operation, *paths: str) -> None:
    """Google Ads API v25+: FieldMask is not available via client.get_type()."""
    mask = operation.update_mask
    # Clear existing paths if any, then set requested ones
    while mask.paths:
        mask.paths.pop()
    for path in paths:
        mask.paths.append(path)


def _apply_one(
    client: GoogleAdsClient, customer_id: str, rec: Recommendation
) -> str:
    if rec.action == ActionType.PAUSE_KEYWORD:
        return _pause_keyword(client, customer_id, rec)
    if rec.action == ActionType.PAUSE_AD:
        return _pause_ad(client, customer_id, rec)
    if rec.action == ActionType.ADD_NEGATIVE:
        return _add_negative(client, customer_id, rec)
    if rec.action in {ActionType.LOWER_BID, ActionType.RAISE_BID}:
        return _update_keyword_bid(client, customer_id, rec)
    if rec.action == ActionType.ADJUST_BUDGET:
        return _adjust_budget(client, customer_id, rec)
    if rec.action in {
        ActionType.REVIEW_CAMPAIGN,
        ActionType.IMPROVE_RSA,
        ActionType.FILL_AD_GROUP,
        ActionType.REVIEW_TRACKING,
    }:
        return f"Manual/AI Assistant action only — {rec.action.value} (no auto-mutate)."
    raise ValueError(f"Unsupported action: {rec.action}")


def _pause_keyword(
    client: GoogleAdsClient, customer_id: str, rec: Recommendation
) -> str:
    ad_group_id = str(rec.payload.get("ad_group_id") or rec.ad_group_id or "")
    criterion_id = str(rec.payload.get("criterion_id") or rec.entity_id or "")
    if not ad_group_id or not criterion_id:
        raise ValueError("pause_keyword requires ad_group_id and criterion_id in payload")

    service = client.get_service("AdGroupCriterionService")
    operation = client.get_type("AdGroupCriterionOperation")
    criterion = operation.update
    criterion.resource_name = service.ad_group_criterion_path(
        customer_id, ad_group_id, criterion_id
    )
    criterion.status = client.enums.AdGroupCriterionStatusEnum.PAUSED
    _set_update_mask(operation, "status")
    service.mutate_ad_group_criteria(customer_id=customer_id, operations=[operation])
    return f"Paused keyword {rec.entity_name}"


def _pause_ad(client: GoogleAdsClient, customer_id: str, rec: Recommendation) -> str:
    ad_group_id = str(rec.payload.get("ad_group_id") or rec.ad_group_id or "")
    ad_id = str(rec.payload.get("ad_id") or rec.entity_id or "")
    if not ad_group_id or not ad_id:
        raise ValueError("pause_ad requires ad_group_id and ad_id in payload")

    service = client.get_service("AdGroupAdService")
    operation = client.get_type("AdGroupAdOperation")
    ad_group_ad = operation.update
    ad_group_ad.resource_name = service.ad_group_ad_path(customer_id, ad_group_id, ad_id)
    ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED
    _set_update_mask(operation, "status")
    service.mutate_ad_group_ads(customer_id=customer_id, operations=[operation])
    return f"Paused ad {rec.entity_id}"


def _add_negative(
    client: GoogleAdsClient, customer_id: str, rec: Recommendation
) -> str:
    campaign_id = str(rec.payload.get("campaign_id") or rec.campaign_id or "")
    search_term = str(rec.payload.get("search_term") or rec.entity_name or "")
    if not campaign_id or not search_term:
        raise ValueError("add_negative requires campaign_id and search_term")

    service = client.get_service("CampaignCriterionService")
    operation = client.get_type("CampaignCriterionOperation")
    criterion = operation.create
    criterion.campaign = client.get_service("CampaignService").campaign_path(
        customer_id, campaign_id
    )
    criterion.negative = True
    criterion.keyword.text = search_term
    criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.EXACT
    service.mutate_campaign_criteria(customer_id=customer_id, operations=[operation])
    return f"Added negative exact: {search_term}"


def _update_keyword_bid(
    client: GoogleAdsClient, customer_id: str, rec: Recommendation
) -> str:
    new_bid = rec.payload.get("new_bid")
    if not new_bid:
        return "Skipped bid update: missing new_bid"
    ad_group_id = str(rec.payload.get("ad_group_id") or rec.ad_group_id or "")
    criterion_id = str(rec.payload.get("criterion_id") or rec.entity_id or "")
    if not ad_group_id or not criterion_id:
        raise ValueError("bid update requires ad_group_id and criterion_id")

    service = client.get_service("AdGroupCriterionService")
    operation = client.get_type("AdGroupCriterionOperation")
    criterion = operation.update
    criterion.resource_name = service.ad_group_criterion_path(
        customer_id, ad_group_id, criterion_id
    )
    criterion.cpc_bid_micros = int(float(new_bid) * 1_000_000)
    _set_update_mask(operation, "cpc_bid_micros")
    service.mutate_ad_group_criteria(customer_id=customer_id, operations=[operation])
    return f"Updated bid for {rec.entity_name} -> {float(new_bid):.2f}"


def _adjust_budget(
    client: GoogleAdsClient, customer_id: str, rec: Recommendation
) -> str:
    from ads_optimizer.campaign_ops import update_campaign_budget_amount

    factor = float(rec.payload.get("suggested_budget_factor", 1.0))
    current = float(rec.payload.get("current_budget", 0) or 0)
    campaign_id = str(rec.payload.get("campaign_id") or rec.campaign_id or rec.entity_id or "")
    if not campaign_id:
        raise ValueError("adjust_budget requires campaign_id")
    if current <= 0:
        raise ValueError("adjust_budget requires current_budget in payload")
    suggested = round(current * factor, 2)
    if suggested < 0.01:
        raise ValueError("suggested daily budget too small")
    update_campaign_budget_amount(
        client,
        customer_id,
        campaign_id=campaign_id,
        daily_budget=suggested,
        confirm=True,
    )
    return f"Updated campaign {campaign_id} daily budget {current:.2f} -> {suggested:.2f}"
