from __future__ import annotations

from typing import Any

from google.ads.googleads.client import GoogleAdsClient

from ads_optimizer.dates import date_range_clause
from ads_optimizer.models import AccountSnapshot


def _micros_to_currency(value: int | None) -> float:
    return (value or 0) / 1_000_000


def _safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def _run_gaql(client: GoogleAdsClient, customer_id: str, query: str) -> list[Any]:
    service = client.get_service("GoogleAdsService")
    return list(service.search(customer_id=customer_id, query=query))


def _enum_name(value: Any) -> str:
    if value is None:
        return ""
    return getattr(value, "name", None) or str(value)


def fetch_campaigns(
    client: GoogleAdsClient, customer_id: str, lookback_days: int
) -> list[dict[str, Any]]:
    query = f"""
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          campaign.advertising_channel_type,
          campaign.bidding_strategy_type,
          campaign_budget.amount_micros,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value,
          metrics.ctr,
          metrics.average_cpc,
          metrics.search_impression_share,
          metrics.search_budget_lost_impression_share,
          metrics.search_rank_lost_impression_share
        FROM campaign
        WHERE {date_range_clause(lookback_days)}
          AND campaign.status != 'REMOVED'
    """
    rows: list[dict[str, Any]] = []
    for row in _run_gaql(client, customer_id, query):
        cost = _micros_to_currency(row.metrics.cost_micros)
        conversions = float(row.metrics.conversions or 0)
        conv_value = float(row.metrics.conversions_value or 0)
        rows.append(
            {
                "id": str(row.campaign.id),
                "name": row.campaign.name,
                "status": _enum_name(row.campaign.status),
                "channel": _enum_name(row.campaign.advertising_channel_type),
                "bidding_strategy_type": _enum_name(row.campaign.bidding_strategy_type),
                "budget": _micros_to_currency(row.campaign_budget.amount_micros),
                "impressions": int(row.metrics.impressions or 0),
                "clicks": int(row.metrics.clicks or 0),
                "cost": cost,
                "conversions": conversions,
                "conversions_value": conv_value,
                "ctr": float(row.metrics.ctr or 0),
                "avg_cpc": _micros_to_currency(row.metrics.average_cpc),
                "cpa": _safe_div(cost, conversions),
                "roas": _safe_div(conv_value, cost),
                "search_impression_share": float(row.metrics.search_impression_share or 0),
                "search_budget_lost_is": float(
                    row.metrics.search_budget_lost_impression_share or 0
                ),
                "search_rank_lost_is": float(
                    row.metrics.search_rank_lost_impression_share or 0
                ),
            }
        )
    return rows


def fetch_keywords(
    client: GoogleAdsClient, customer_id: str, lookback_days: int
) -> list[dict[str, Any]]:
    query = f"""
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          campaign.bidding_strategy_type,
          campaign.advertising_channel_type,
          ad_group.id,
          ad_group.name,
          ad_group_criterion.criterion_id,
          ad_group_criterion.keyword.text,
          ad_group_criterion.keyword.match_type,
          ad_group_criterion.status,
          ad_group_criterion.effective_cpc_bid_micros,
          ad_group_criterion.quality_info.quality_score,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value,
          metrics.ctr
        FROM keyword_view
        WHERE {date_range_clause(lookback_days)}
          AND campaign.status != 'REMOVED'
          AND ad_group.status != 'REMOVED'
          AND ad_group_criterion.status != 'REMOVED'
    """
    rows: list[dict[str, Any]] = []
    for row in _run_gaql(client, customer_id, query):
        cost = _micros_to_currency(row.metrics.cost_micros)
        conversions = float(row.metrics.conversions or 0)
        conv_value = float(row.metrics.conversions_value or 0)
        qs = 0
        try:
            qs = int(row.ad_group_criterion.quality_info.quality_score or 0)
        except Exception:  # noqa: BLE001 — quality_info often unset
            qs = 0
        rows.append(
            {
                "campaign_id": str(row.campaign.id),
                "campaign_name": row.campaign.name,
                "campaign_status": _enum_name(row.campaign.status),
                "bidding_strategy_type": _enum_name(row.campaign.bidding_strategy_type),
                "channel": _enum_name(row.campaign.advertising_channel_type),
                "ad_group_id": str(row.ad_group.id),
                "ad_group_name": row.ad_group.name,
                "criterion_id": str(row.ad_group_criterion.criterion_id),
                "text": row.ad_group_criterion.keyword.text,
                "match_type": _enum_name(row.ad_group_criterion.keyword.match_type),
                "status": _enum_name(row.ad_group_criterion.status),
                "bid": _micros_to_currency(
                    row.ad_group_criterion.effective_cpc_bid_micros
                ),
                "impressions": int(row.metrics.impressions or 0),
                "clicks": int(row.metrics.clicks or 0),
                "cost": cost,
                "conversions": conversions,
                "conversions_value": conv_value,
                "ctr": float(row.metrics.ctr or 0),
                "quality_score": qs,
                "cpa": _safe_div(cost, conversions),
                "roas": _safe_div(conv_value, cost),
            }
        )
    return rows


def fetch_search_terms(
    client: GoogleAdsClient, customer_id: str, lookback_days: int
) -> list[dict[str, Any]]:
    query = f"""
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          ad_group.id,
          ad_group.name,
          search_term_view.search_term,
          search_term_view.status,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value
        FROM search_term_view
        WHERE {date_range_clause(lookback_days)}
          AND campaign.status != 'REMOVED'
          AND ad_group.status != 'REMOVED'
    """
    rows: list[dict[str, Any]] = []
    for row in _run_gaql(client, customer_id, query):
        cost = _micros_to_currency(row.metrics.cost_micros)
        conversions = float(row.metrics.conversions or 0)
        conv_value = float(row.metrics.conversions_value or 0)
        clicks = int(row.metrics.clicks or 0)
        impressions = int(row.metrics.impressions or 0)
        rows.append(
            {
                "campaign_id": str(row.campaign.id),
                "campaign_name": row.campaign.name,
                "campaign_status": _enum_name(row.campaign.status),
                "ad_group_id": str(row.ad_group.id),
                "ad_group_name": row.ad_group.name,
                "search_term": row.search_term_view.search_term,
                "status": _enum_name(row.search_term_view.status),
                "impressions": impressions,
                "clicks": clicks,
                "cost": cost,
                "conversions": conversions,
                "conversions_value": conv_value,
                "ctr": _safe_div(clicks, impressions),
                "cpa": _safe_div(cost, conversions),
                "roas": _safe_div(conv_value, cost),
            }
        )
    return rows


def fetch_ads(
    client: GoogleAdsClient, customer_id: str, lookback_days: int
) -> list[dict[str, Any]]:
    query = f"""
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          ad_group.id,
          ad_group.name,
          ad_group_ad.ad.id,
          ad_group_ad.ad.name,
          ad_group_ad.ad.type,
          ad_group_ad.status,
          ad_group_ad.ad_strength,
          ad_group_ad.policy_summary.approval_status,
          ad_group_ad.policy_summary.review_status,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value,
          metrics.ctr
        FROM ad_group_ad
        WHERE {date_range_clause(lookback_days)}
          AND campaign.status != 'REMOVED'
          AND ad_group.status != 'REMOVED'
          AND ad_group_ad.status != 'REMOVED'
    """
    rows: list[dict[str, Any]] = []
    for row in _run_gaql(client, customer_id, query):
        cost = _micros_to_currency(row.metrics.cost_micros)
        conversions = float(row.metrics.conversions or 0)
        conv_value = float(row.metrics.conversions_value or 0)
        ad_name = row.ad_group_ad.ad.name or f"ad:{row.ad_group_ad.ad.id}"
        policy = row.ad_group_ad.policy_summary
        rows.append(
            {
                "campaign_id": str(row.campaign.id),
                "campaign_name": row.campaign.name,
                "campaign_status": _enum_name(row.campaign.status),
                "ad_group_id": str(row.ad_group.id),
                "ad_group_name": row.ad_group.name,
                "ad_id": str(row.ad_group_ad.ad.id),
                "name": ad_name,
                "type": _enum_name(row.ad_group_ad.ad.type_),
                "status": _enum_name(row.ad_group_ad.status),
                "ad_strength": _enum_name(row.ad_group_ad.ad_strength),
                "approval_status": _enum_name(policy.approval_status) if policy else "",
                "review_status": _enum_name(policy.review_status) if policy else "",
                "impressions": int(row.metrics.impressions or 0),
                "clicks": int(row.metrics.clicks or 0),
                "cost": cost,
                "conversions": conversions,
                "conversions_value": conv_value,
                "ctr": float(row.metrics.ctr or 0),
                "cpa": _safe_div(cost, conversions),
                "roas": _safe_div(conv_value, cost),
            }
        )
    return rows


def fetch_ad_groups(client: GoogleAdsClient, customer_id: str) -> list[dict[str, Any]]:
    """ENABLED Search ad groups + whether they have any non-removed ads."""
    groups_query = """
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          campaign.advertising_channel_type,
          ad_group.id,
          ad_group.name,
          ad_group.status
        FROM ad_group
        WHERE campaign.status != 'REMOVED'
          AND ad_group.status != 'REMOVED'
    """
    ads_query = """
        SELECT
          ad_group.id,
          ad_group_ad.ad.id
        FROM ad_group_ad
        WHERE campaign.status != 'REMOVED'
          AND ad_group.status != 'REMOVED'
          AND ad_group_ad.status != 'REMOVED'
    """
    ads_count: dict[str, int] = {}
    for row in _run_gaql(client, customer_id, ads_query):
        ag_id = str(row.ad_group.id)
        ads_count[ag_id] = ads_count.get(ag_id, 0) + 1

    rows: list[dict[str, Any]] = []
    for row in _run_gaql(client, customer_id, groups_query):
        ag_id = str(row.ad_group.id)
        count = ads_count.get(ag_id, 0)
        rows.append(
            {
                "campaign_id": str(row.campaign.id),
                "campaign_name": row.campaign.name,
                "campaign_status": _enum_name(row.campaign.status),
                "channel": _enum_name(row.campaign.advertising_channel_type),
                "ad_group_id": ag_id,
                "ad_group_name": row.ad_group.name,
                "status": _enum_name(row.ad_group.status),
                "ads_count": count,
                "empty_ad_group": count == 0,
            }
        )
    return rows


def fetch_conversion_actions(
    client: GoogleAdsClient, customer_id: str
) -> list[dict[str, Any]]:
    query = """
        SELECT
          conversion_action.id,
          conversion_action.name,
          conversion_action.status,
          conversion_action.type,
          conversion_action.primary_for_goal,
          conversion_action.include_in_conversions_metric,
          conversion_action.category,
          conversion_action.origin
        FROM conversion_action
        WHERE conversion_action.status != 'REMOVED'
    """
    rows: list[dict[str, Any]] = []
    for row in _run_gaql(client, customer_id, query):
        ca = row.conversion_action
        rows.append(
            {
                "id": str(ca.id),
                "name": ca.name,
                "status": _enum_name(ca.status),
                "type": _enum_name(ca.type_),
                "primary_for_goal": bool(ca.primary_for_goal),
                "include_in_conversions_metric": bool(ca.include_in_conversions_metric),
                "category": _enum_name(ca.category),
                "origin": _enum_name(ca.origin),
            }
        )
    return rows


def collect_snapshot(
    client: GoogleAdsClient, customer_id: str, lookback_days: int
) -> AccountSnapshot:
    return AccountSnapshot(
        campaigns=fetch_campaigns(client, customer_id, lookback_days),
        keywords=fetch_keywords(client, customer_id, lookback_days),
        search_terms=fetch_search_terms(client, customer_id, lookback_days),
        ads=fetch_ads(client, customer_id, lookback_days),
        ad_groups=fetch_ad_groups(client, customer_id),
        conversion_actions=fetch_conversion_actions(client, customer_id),
    )
