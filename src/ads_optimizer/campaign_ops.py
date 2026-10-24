from __future__ import annotations

import re
from collections import Counter
from typing import Any
from uuid import uuid4

from google.ads.googleads.client import GoogleAdsClient

from ads_optimizer.applicator import _set_update_mask, _short_error
from ads_optimizer.ids import format_customer_id
from ads_optimizer.url_check import require_working_url

# Synonyms that often stack into the same "route message" (hurts Ad Strength).
_ROUTE_SERVICE_SYNONYMS = re.compile(
    r"\b("
    r"transfer|transport|taxi|przew[oó]z|przewoz|"
    r"kierowca|przejazd|prywatny|chauffeur|ride|shuttle"
    r")\b",
    re.IGNORECASE,
)


def require_confirm(confirm: bool, preview: dict[str, Any]) -> dict[str, Any] | None:
    """Return preview payload when confirm is not True."""
    if confirm is True:
        return None
    return {
        "needs_confirmation": True,
        "confirm_required": True,
        "message": (
            "Действие НЕ выполнено. Это preview. "
            "Чтобы применить, пользователь должен явно подтвердить, "
            "после чего вызовите тот же tool с confirm=true."
        ),
        "preview": preview,
    }


def _rsa_headline_len(text: str) -> int:
    """Effective RSA headline length (DKI default text, not braces)."""
    t = text.strip()
    lower = t.lower()
    if lower.startswith("{keyword:") and t.endswith("}"):
        return len(t[len("{KeyWord:") : -1])
    return len(t)


def _norm_asset(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _semantic_core(text: str) -> str:
    """Strip service synonyms so Transfer/Taxi + same cities collapse to one idea."""
    s = _ROUTE_SERVICE_SYNONYMS.sub(" ", _norm_asset(text))
    return " ".join(s.split())


def _set_repeated_urls(field: Any, url: str) -> None:
    del field[:]
    field.append(url)


def validate_rsa_copy(headlines: list[str], descriptions: list[str]) -> tuple[list[str], list[str]]:
    clean_headlines = [t.strip() for t in headlines if t and str(t).strip()]
    clean_descriptions = [t.strip() for t in descriptions if t and str(t).strip()]
    if len(clean_headlines) < 3 or len(clean_descriptions) < 2:
        raise ValueError("RSA needs at least 3 headlines and 2 descriptions")
    if len(clean_headlines) > 15:
        raise ValueError("Max 15 headlines")
    if len(clean_descriptions) > 4:
        raise ValueError("Max 4 descriptions")
    for text in clean_headlines:
        if _rsa_headline_len(text) > 30:
            raise ValueError(f"Headline too long (>30): {text!r}")
    for text in clean_descriptions:
        if len(text) > 90:
            raise ValueError(f"Description too long (>90): {text!r}")
    return clean_headlines, clean_descriptions


def evaluate_rsa_for_ad_strength(
    headlines: list[str],
    descriptions: list[str],
    *,
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    """Checklist toward Good/Excellent Ad Strength (see knowledge rsa-ad-strength)."""
    hs = [str(h).strip() for h in headlines if h and str(h).strip()]
    ds = [str(d).strip() for d in descriptions if d and str(d).strip()]
    warnings: list[str] = []
    tips: list[str] = []

    if len(hs) < 10:
        warnings.append(f"Only {len(hs)} headlines — aim for 15 (min 10 for Good+).")
    elif len(hs) < 15:
        tips.append(f"{len(hs)} headlines — fill to 15 for Excellent potential.")
    if len(ds) < 3:
        warnings.append(f"Only {len(ds)} descriptions — aim for 4 (min 3).")
    elif len(ds) < 4:
        tips.append(f"{len(ds)} descriptions — add a 4th for more combinations.")

    seen: set[str] = set()
    dupes = 0
    for h in hs:
        key = _norm_asset(h)
        if key in seen:
            dupes += 1
        seen.add(key)
    if dupes:
        warnings.append(f"{dupes} near-duplicate headline(s) — uniqueness required.")

    # Synonym stacking: many unique strings, same meaning after stripping service words.
    cores = [_semantic_core(h) for h in hs]
    core_counts = Counter(c for c in cores if c)
    stacked = [(core, n) for core, n in core_counts.items() if n >= 4]
    synonym_route_hits = sum(
        1 for h in hs if _ROUTE_SERVICE_SYNONYMS.search(h) and len(_semantic_core(h).split()) >= 2
    )
    if stacked:
        top = ", ".join(f"{n}× «{core}»" for core, n in sorted(stacked, key=lambda x: -x[1])[:3])
        warnings.append(
            f"Synonym stacking: {top}. Cap the same idea at ≤2 H; use balanced pool "
            f"(4–5 route-specific + ~10 universal categories) — see rsa-ad-strength."
        )
    elif synonym_route_hits >= 8:
        warnings.append(
            f"{synonym_route_hits}/15 headlines look like service-synonym + route. "
            f"Keep ≤4 of that pattern; add USP/feature/trust/CTA/price headlines."
        )
    elif synonym_route_hits >= 5:
        tips.append(
            f"{synonym_route_hits} synonym+route headlines — prefer ≤4; fill rest from "
            f"universal category pool (rsa-ad-strength)."
        )

    kw_list = [str(k).strip() for k in (keywords or []) if k and str(k).strip()]
    # Prefer longer phrases first for matching
    kw_sorted = sorted(kw_list, key=len, reverse=True)
    coverage = 0
    primary_hits = 0
    primary = kw_sorted[0] if kw_sorted else ""
    per_kw_hits: dict[str, int] = {k: 0 for k in kw_sorted}

    def _contains(asset: str, phrase: str) -> bool:
        a = _norm_asset(asset)
        p = _norm_asset(phrase)
        if not p:
            return False
        if p in a:
            return True
        # allow match without spaces differences
        return p.replace(" ", "") in a.replace(" ", "")

    for h in hs:
        hit_any = False
        for k in kw_sorted:
            if _contains(h, k):
                per_kw_hits[k] = per_kw_hits.get(k, 0) + 1
                hit_any = True
                if primary and k == primary:
                    primary_hits += 1
                break
        if hit_any:
            coverage += 1

    desc_primary = sum(1 for d in ds if primary and _contains(d, primary)) if primary else 0

    stats = {
        "headline_count": len(hs),
        "description_count": len(ds),
        "keyword_headlines": coverage,
        "keyword_headline_share": round(coverage / len(hs), 2) if hs else 0,
        "primary_keyword": primary or None,
        "primary_keyword_headlines": primary_hits,
        "primary_keyword_descriptions": desc_primary,
        "keywords_checked": len(kw_sorted),
        "unique_semantic_cores": len(core_counts),
        "synonym_route_headlines": synonym_route_hits,
        "max_core_repeats": max(core_counts.values()) if core_counts else 0,
    }

    if kw_sorted:
        share = coverage / len(hs) if hs else 0
        if share < 0.5:
            warnings.append(
                f"Keyword density low: {coverage}/{len(hs)} headlines contain an ad-group "
                f"keyword (need >=50%)."
            )
        if primary and primary_hits < 4:
            warnings.append(
                f"Primary keyword {primary!r} in {primary_hits} headlines — need >=4 "
                f"(max 6, keep unique)."
            )
        if primary and primary_hits > 6:
            warnings.append(
                f"Primary keyword {primary!r} in {primary_hits} headlines — max 6 "
                f"(avoid stuffing; add theme diversity)."
            )
        if primary and len(primary) > 30 and not any(_contains(d, primary) for d in ds):
            warnings.append(
                f"Long keyword {primary!r} (>30) must appear fully in a description."
            )
        if primary and desc_primary < 2 and len(ds) >= 2:
            warnings.append(
                f"Primary keyword in {desc_primary} description(s) — need >=2 of 4."
            )
        for k, n in per_kw_hits.items():
            if n > 6:
                warnings.append(f"Keyword {k!r} appears in {n} headlines — cap at 6.")
    else:
        tips.append(
            "Pass keywords= (ad group ENABLED phrases) for density check, "
            "or load get_keywords before drafting (KB rsa-ad-strength)."
        )

    ok = not warnings
    return {
        "ok_for_good_excellent": ok,
        "warnings": warnings,
        "tips": tips,
        "stats": stats,
        "rule": "rsa-ad-strength",
    }


def _normalize_bidding_key(bidding: str | None) -> str:
    key = (bidding or "maximize_clicks").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "max_clicks": "maximize_clicks",
        "target_spend": "maximize_clicks",
        "max_conversions": "maximize_conversions",
        "tcpa": "target_cpa",
        "troas": "target_roas",
        "max_conversion_value": "maximize_conversion_value",
        "manual": "manual_cpc",
    }
    return aliases.get(key, key)


def apply_bidding_scheme(
    client: GoogleAdsClient,
    campaign: Any,
    *,
    bidding: str,
    target_cpa: float | None = None,
    target_roas: float | None = None,
    cpc_bid_ceiling: float | None = None,
) -> str:
    """Set campaign bidding oneof.

    Returns a *leaf* update-mask path. Parent paths like ``target_spend`` cause
    FieldMaskError.FIELD_HAS_SUBFIELDS on CampaignService updates.
    """
    bidding_key = _normalize_bidding_key(bidding)

    if bidding_key == "maximize_clicks":
        ts = client.get_type("TargetSpend")
        if cpc_bid_ceiling and float(cpc_bid_ceiling) > 0:
            ts.cpc_bid_ceiling_micros = int(float(cpc_bid_ceiling) * 1_000_000)
        client.copy_from(campaign.target_spend, ts)
        return "target_spend.cpc_bid_ceiling_micros"

    if bidding_key == "maximize_conversions":
        mc = client.get_type("MaximizeConversions")
        if target_cpa and float(target_cpa) > 0:
            mc.target_cpa_micros = int(float(target_cpa) * 1_000_000)
        client.copy_from(campaign.maximize_conversions, mc)
        return "maximize_conversions.target_cpa_micros"

    if bidding_key == "target_cpa":
        if not target_cpa or float(target_cpa) <= 0:
            raise ValueError("target_cpa requires target_cpa > 0")
        tc = client.get_type("TargetCpa")
        tc.target_cpa_micros = int(float(target_cpa) * 1_000_000)
        client.copy_from(campaign.target_cpa, tc)
        return "target_cpa.target_cpa_micros"

    if bidding_key == "maximize_conversion_value":
        mv = client.get_type("MaximizeConversionValue")
        if target_roas and float(target_roas) > 0:
            mv.target_roas = float(target_roas)
        client.copy_from(campaign.maximize_conversion_value, mv)
        return "maximize_conversion_value.target_roas"

    if bidding_key == "target_roas":
        if not target_roas or float(target_roas) <= 0:
            raise ValueError("target_roas requires target_roas > 0 (e.g. 3.0 = 300%)")
        tr = client.get_type("TargetRoas")
        tr.target_roas = float(target_roas)
        client.copy_from(campaign.target_roas, tr)
        return "target_roas.target_roas"

    if bidding_key == "manual_cpc":
        campaign.manual_cpc.enhanced_cpc_enabled = False
        return "manual_cpc.enhanced_cpc_enabled"

    raise ValueError(
        "Unsupported bidding. Use: maximize_clicks, maximize_conversions, target_cpa, "
        "maximize_conversion_value, target_roas, manual_cpc"
    )


def create_search_campaign(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    name: str,
    daily_budget: float,
    bidding: str = "maximize_clicks",
    target_cpa: float | None = None,
    start_paused: bool = True,
    geo_country_constant: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Create budget + Search campaign. Starts PAUSED by default for safety."""
    cid = format_customer_id(customer_id)
    preview = {
        "action": "create_search_campaign",
        "customer_id": cid,
        "name": name,
        "daily_budget": daily_budget,
        "bidding": bidding,
        "target_cpa": target_cpa,
        "status": "PAUSED" if start_paused else "ENABLED",
        "channel": "SEARCH",
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    budget_service = client.get_service("CampaignBudgetService")
    budget_op = client.get_type("CampaignBudgetOperation")
    budget = budget_op.create
    budget.name = f"{name} Budget {uuid4().hex[:8]}"
    budget.amount_micros = int(float(daily_budget) * 1_000_000)
    budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
    budget_response = budget_service.mutate_campaign_budgets(
        customer_id=cid, operations=[budget_op]
    )
    budget_rn = budget_response.results[0].resource_name

    campaign_service = client.get_service("CampaignService")
    campaign_op = client.get_type("CampaignOperation")
    campaign = campaign_op.create
    campaign.name = name
    campaign.campaign_budget = budget_rn
    campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SEARCH
    campaign.status = (
        client.enums.CampaignStatusEnum.PAUSED
        if start_paused
        else client.enums.CampaignStatusEnum.ENABLED
    )
    campaign.contains_eu_political_advertising = (
        client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
    )
    campaign.network_settings.target_google_search = True
    campaign.network_settings.target_search_network = True
    campaign.network_settings.target_content_network = False
    campaign.network_settings.target_partner_search_network = False

    bidding_key = _normalize_bidding_key(bidding)
    apply_bidding_scheme(
        client,
        campaign,
        bidding=bidding_key,
        target_cpa=target_cpa,
        cpc_bid_ceiling=None,
    )

    # API v25+: start_date/end_date removed. Optional:
    # campaign.start_date_time = "yyyy-MM-dd HH:mm:ss" (account timezone)
    # Omitting defaults to starting immediately.

    campaign_response = campaign_service.mutate_campaigns(
        customer_id=cid, operations=[campaign_op]
    )
    campaign_rn = campaign_response.results[0].resource_name
    campaign_id = campaign_rn.split("/")[-1]

    result: dict[str, Any] = {
        "ok": True,
        "action": "create_search_campaign",
        "campaign_id": campaign_id,
        "campaign_resource_name": campaign_rn,
        "budget_resource_name": budget_rn,
        "status": "PAUSED" if start_paused else "ENABLED",
        "name": name,
        "daily_budget": daily_budget,
    }

    if geo_country_constant:
        # e.g. geoTargetConstants/2276 for Germany — optional
        try:
            crit_service = client.get_service("CampaignCriterionService")
            crit_op = client.get_type("CampaignCriterionOperation")
            loc = crit_op.create
            loc.campaign = campaign_rn
            loc.location.geo_target_constant = geo_country_constant
            crit_service.mutate_campaign_criteria(customer_id=cid, operations=[crit_op])
            result["geo"] = geo_country_constant
        except Exception as exc:  # noqa: BLE001
            result["geo_error"] = _short_error(exc)

    return result


def set_campaign_status(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_id: str,
    status: str,
    confirm: bool = False,
) -> dict[str, Any]:
    cid = format_customer_id(customer_id)
    status_key = status.upper()
    preview = {
        "action": "set_campaign_status",
        "customer_id": cid,
        "campaign_id": campaign_id,
        "status": status_key,
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    service = client.get_service("CampaignService")
    resource_name = service.campaign_path(cid, campaign_id)

    # v25: REMOVED cannot be set via update status — use remove operation.
    if status_key == "REMOVED":
        operation = client.get_type("CampaignOperation")
        operation.remove = resource_name
        service.mutate_campaigns(customer_id=cid, operations=[operation])
        return {"ok": True, **preview}

    enum_map = {
        "ENABLED": client.enums.CampaignStatusEnum.ENABLED,
        "PAUSED": client.enums.CampaignStatusEnum.PAUSED,
    }
    if status_key not in enum_map:
        raise ValueError("status must be ENABLED, PAUSED, or REMOVED")

    operation = client.get_type("CampaignOperation")
    campaign = operation.update
    campaign.resource_name = resource_name
    campaign.status = enum_map[status_key]
    _set_update_mask(operation, "status")
    service.mutate_campaigns(customer_id=cid, operations=[operation])
    return {"ok": True, **preview}


def update_campaign_budget_amount(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_id: str,
    daily_budget: float,
    confirm: bool = False,
) -> dict[str, Any]:
    cid = format_customer_id(customer_id)
    preview = {
        "action": "update_campaign_budget",
        "customer_id": cid,
        "campaign_id": campaign_id,
        "daily_budget": daily_budget,
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    # Resolve budget resource name from campaign
    gaql = f"""
        SELECT campaign.id, campaign.campaign_budget
        FROM campaign
        WHERE campaign.id = {int(campaign_id)}
        LIMIT 1
    """
    rows = list(
        client.get_service("GoogleAdsService").search(customer_id=cid, query=gaql)
    )
    if not rows:
        raise ValueError(f"Campaign {campaign_id} not found")
    budget_rn = rows[0].campaign.campaign_budget

    service = client.get_service("CampaignBudgetService")
    operation = client.get_type("CampaignBudgetOperation")
    budget = operation.update
    budget.resource_name = budget_rn
    budget.amount_micros = int(float(daily_budget) * 1_000_000)
    _set_update_mask(operation, "amount_micros")
    service.mutate_campaign_budgets(customer_id=cid, operations=[operation])
    return {"ok": True, "budget_resource_name": budget_rn, **preview}


def rename_campaign(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_id: str,
    name: str,
    confirm: bool = False,
) -> dict[str, Any]:
    cid = format_customer_id(customer_id)
    preview = {
        "action": "rename_campaign",
        "customer_id": cid,
        "campaign_id": campaign_id,
        "name": name,
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    service = client.get_service("CampaignService")
    operation = client.get_type("CampaignOperation")
    campaign = operation.update
    campaign.resource_name = service.campaign_path(cid, campaign_id)
    campaign.name = name
    _set_update_mask(operation, "name")
    service.mutate_campaigns(customer_id=cid, operations=[operation])
    return {"ok": True, **preview}


def update_campaign_bidding(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_id: str,
    bidding: str,
    target_cpa: float | None = None,
    target_roas: float | None = None,
    cpc_bid_ceiling: float | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Change bidding strategy on an existing campaign."""
    cid = format_customer_id(customer_id)
    bidding_key = _normalize_bidding_key(bidding)
    preview = {
        "action": "update_campaign_bidding",
        "customer_id": cid,
        "campaign_id": campaign_id,
        "bidding": bidding_key,
        "target_cpa": target_cpa,
        "target_roas": target_roas,
        "cpc_bid_ceiling": cpc_bid_ceiling,
        "note": (
            "Changing bidding starts/resets learning. Avoid stacking other big edits "
            "for several days (see bidding-strategies KB)."
        ),
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    service = client.get_service("CampaignService")
    operation = client.get_type("CampaignOperation")
    campaign = operation.update
    campaign.resource_name = service.campaign_path(cid, campaign_id)
    mask_path = apply_bidding_scheme(
        client,
        campaign,
        bidding=bidding_key,
        target_cpa=target_cpa,
        target_roas=target_roas,
        cpc_bid_ceiling=cpc_bid_ceiling,
    )
    _set_update_mask(operation, mask_path)
    service.mutate_campaigns(customer_id=cid, operations=[operation])
    return {"ok": True, "update_mask": mask_path, **preview}


def create_ad_group(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_id: str,
    name: str,
    cpc_bid: float = 1.0,
    confirm: bool = False,
) -> dict[str, Any]:
    cid = format_customer_id(customer_id)
    preview = {
        "action": "create_ad_group",
        "customer_id": cid,
        "campaign_id": campaign_id,
        "name": name,
        "cpc_bid": cpc_bid,
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    service = client.get_service("AdGroupService")
    operation = client.get_type("AdGroupOperation")
    ad_group = operation.create
    ad_group.name = name
    ad_group.campaign = client.get_service("CampaignService").campaign_path(
        cid, campaign_id
    )
    ad_group.status = client.enums.AdGroupStatusEnum.ENABLED
    ad_group.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD
    ad_group.cpc_bid_micros = int(float(cpc_bid) * 1_000_000)
    response = service.mutate_ad_groups(customer_id=cid, operations=[operation])
    rn = response.results[0].resource_name
    return {"ok": True, "ad_group_id": rn.split("/")[-1], "resource_name": rn, **preview}


def rename_ad_group(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    ad_group_id: str,
    name: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """Rename an existing ad group (AdGroupService update mask: name)."""
    cid = format_customer_id(customer_id)
    ag_id = str(ad_group_id).replace("-", "").strip()
    new_name = str(name or "").strip()
    if not ag_id:
        raise ValueError("ad_group_id is required")
    if not new_name:
        raise ValueError("name is required")
    preview = {
        "action": "rename_ad_group",
        "customer_id": cid,
        "ad_group_id": ag_id,
        "name": new_name,
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    service = client.get_service("AdGroupService")
    operation = client.get_type("AdGroupOperation")
    ad_group = operation.update
    ad_group.resource_name = service.ad_group_path(cid, ag_id)
    ad_group.name = new_name
    _set_update_mask(operation, "name")
    service.mutate_ad_groups(customer_id=cid, operations=[operation])
    return {"ok": True, **preview}


def add_keywords(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    ad_group_id: str,
    keywords: list[dict[str, str]],
    confirm: bool = False,
) -> dict[str, Any]:
    """keywords: [{text, match_type}] match_type=EXACT|PHRASE|BROAD"""
    cid = format_customer_id(customer_id)
    preview = {
        "action": "add_keywords",
        "customer_id": cid,
        "ad_group_id": ad_group_id,
        "keywords": keywords,
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    match_map = {
        "EXACT": client.enums.KeywordMatchTypeEnum.EXACT,
        "PHRASE": client.enums.KeywordMatchTypeEnum.PHRASE,
        "BROAD": client.enums.KeywordMatchTypeEnum.BROAD,
    }
    service = client.get_service("AdGroupCriterionService")
    operations = []
    for item in keywords:
        op = client.get_type("AdGroupCriterionOperation")
        crit = op.create
        crit.ad_group = service.ad_group_path(cid, ad_group_id)
        crit.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
        crit.keyword.text = item["text"]
        crit.keyword.match_type = match_map.get(
            str(item.get("match_type", "PHRASE")).upper(),
            client.enums.KeywordMatchTypeEnum.PHRASE,
        )
        operations.append(op)

    response = service.mutate_ad_group_criteria(customer_id=cid, operations=operations)
    return {
        "ok": True,
        "created": [r.resource_name for r in response.results],
        **preview,
    }


def set_keyword_status(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    keywords: list[dict[str, str]],
    status: str = "PAUSED",
    confirm: bool = False,
) -> dict[str, Any]:
    """Pause or enable keywords.

    keywords: [{ad_group_id, criterion_id, text?}] — text is optional (preview only).
    status: PAUSED | ENABLED
    """
    cid = format_customer_id(customer_id)
    status_key = str(status or "PAUSED").upper()
    if status_key not in {"PAUSED", "ENABLED"}:
        raise ValueError("status must be PAUSED or ENABLED")
    if not keywords:
        raise ValueError("keywords list is empty")

    normalized: list[dict[str, str]] = []
    for item in keywords:
        ad_group_id = str(item.get("ad_group_id") or "").strip()
        criterion_id = str(item.get("criterion_id") or "").strip()
        if not ad_group_id or not criterion_id:
            raise ValueError("Each keyword needs ad_group_id and criterion_id")
        normalized.append(
            {
                "ad_group_id": ad_group_id,
                "criterion_id": criterion_id,
                "text": str(item.get("text") or ""),
            }
        )

    preview = {
        "action": "set_keyword_status",
        "customer_id": cid,
        "status": status_key,
        "keywords": normalized,
        "count": len(normalized),
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    enum_map = {
        "PAUSED": client.enums.AdGroupCriterionStatusEnum.PAUSED,
        "ENABLED": client.enums.AdGroupCriterionStatusEnum.ENABLED,
    }
    service = client.get_service("AdGroupCriterionService")
    operations = []
    for item in normalized:
        op = client.get_type("AdGroupCriterionOperation")
        criterion = op.update
        criterion.resource_name = service.ad_group_criterion_path(
            cid, item["ad_group_id"], item["criterion_id"]
        )
        criterion.status = enum_map[status_key]
        _set_update_mask(op, "status")
        operations.append(op)

    response = service.mutate_ad_group_criteria(customer_id=cid, operations=operations)
    return {
        "ok": True,
        "updated": [r.resource_name for r in response.results],
        **preview,
    }


def set_ad_status(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    ads: list[dict[str, str]],
    status: str = "PAUSED",
    confirm: bool = False,
) -> dict[str, Any]:
    """Pause or enable ads (including RSA).

    ads: [{ad_group_id, ad_id, name?}] — name optional for preview.
    status: PAUSED | ENABLED
    """
    cid = format_customer_id(customer_id)
    status_key = str(status or "PAUSED").upper()
    if status_key not in {"PAUSED", "ENABLED"}:
        raise ValueError("status must be PAUSED or ENABLED")
    if not ads:
        raise ValueError("ads list is empty")

    normalized: list[dict[str, str]] = []
    for item in ads:
        ad_group_id = str(item.get("ad_group_id") or "").strip()
        ad_id = str(item.get("ad_id") or item.get("id") or "").strip()
        if not ad_group_id or not ad_id:
            raise ValueError("Each ad needs ad_group_id and ad_id")
        normalized.append(
            {
                "ad_group_id": ad_group_id,
                "ad_id": ad_id,
                "name": str(item.get("name") or ""),
            }
        )

    preview = {
        "action": "set_ad_status",
        "customer_id": cid,
        "status": status_key,
        "ads": normalized,
        "count": len(normalized),
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    enum_map = {
        "PAUSED": client.enums.AdGroupAdStatusEnum.PAUSED,
        "ENABLED": client.enums.AdGroupAdStatusEnum.ENABLED,
    }
    service = client.get_service("AdGroupAdService")
    operations = []
    for item in normalized:
        op = client.get_type("AdGroupAdOperation")
        ad_group_ad = op.update
        ad_group_ad.resource_name = service.ad_group_ad_path(
            cid, item["ad_group_id"], item["ad_id"]
        )
        ad_group_ad.status = enum_map[status_key]
        _set_update_mask(op, "status")
        operations.append(op)

    response = service.mutate_ad_group_ads(customer_id=cid, operations=operations)
    return {
        "ok": True,
        "updated": [r.resource_name for r in response.results],
        **preview,
    }


def add_negative_keywords(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    negatives: list[dict[str, str]],
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Add negative keywords at campaign or ad group level.

    negatives: [{text, match_type}] match_type=EXACT|PHRASE|BROAD (default EXACT).
    Provide exactly one of campaign_id or ad_group_id.
    """
    cid = format_customer_id(customer_id)
    has_campaign = bool(campaign_id)
    has_ad_group = bool(ad_group_id)
    if has_campaign == has_ad_group:
        raise ValueError("Provide exactly one of campaign_id or ad_group_id")
    if not negatives:
        raise ValueError("negatives list is empty")

    preview = {
        "action": "add_negative_keywords",
        "customer_id": cid,
        "level": "campaign" if has_campaign else "ad_group",
        "campaign_id": campaign_id,
        "ad_group_id": ad_group_id,
        "negatives": negatives,
        "count": len(negatives),
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    match_map = {
        "EXACT": client.enums.KeywordMatchTypeEnum.EXACT,
        "PHRASE": client.enums.KeywordMatchTypeEnum.PHRASE,
        "BROAD": client.enums.KeywordMatchTypeEnum.BROAD,
    }

    if has_campaign:
        service = client.get_service("CampaignCriterionService")
        operations = []
        for item in negatives:
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            op = client.get_type("CampaignCriterionOperation")
            criterion = op.create
            criterion.campaign = client.get_service("CampaignService").campaign_path(
                cid, campaign_id
            )
            criterion.negative = True
            criterion.keyword.text = text
            criterion.keyword.match_type = match_map.get(
                str(item.get("match_type", "EXACT")).upper(),
                client.enums.KeywordMatchTypeEnum.EXACT,
            )
            operations.append(op)
        if not operations:
            raise ValueError("No valid negative keywords to add")
        response = service.mutate_campaign_criteria(customer_id=cid, operations=operations)
        return {
            "ok": True,
            "created": [r.resource_name for r in response.results],
            **preview,
        }

    service = client.get_service("AdGroupCriterionService")
    operations = []
    for item in negatives:
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        op = client.get_type("AdGroupCriterionOperation")
        criterion = op.create
        criterion.ad_group = service.ad_group_path(cid, ad_group_id)
        criterion.negative = True
        criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
        criterion.keyword.text = text
        criterion.keyword.match_type = match_map.get(
            str(item.get("match_type", "EXACT")).upper(),
            client.enums.KeywordMatchTypeEnum.EXACT,
        )
        operations.append(op)
    if not operations:
        raise ValueError("No valid negative keywords to add")
    response = service.mutate_ad_group_criteria(customer_id=cid, operations=operations)
    return {
        "ok": True,
        "created": [r.resource_name for r in response.results],
        **preview,
    }


def create_responsive_search_ad(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    ad_group_id: str,
    final_url: str,
    headlines: list[str],
    descriptions: list[str],
    path1: str | None = None,
    path2: str | None = None,
    keywords: list[str] | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    cid = format_customer_id(customer_id)
    strength = evaluate_rsa_for_ad_strength(
        headlines, descriptions, keywords=keywords
    )
    preview = {
        "action": "create_responsive_search_ad",
        "customer_id": cid,
        "ad_group_id": ad_group_id,
        "final_url": final_url,
        "headlines": headlines,
        "descriptions": descriptions,
        "ad_strength_checklist": strength,
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    clean_headlines, clean_descriptions = validate_rsa_copy(headlines, descriptions)
    require_working_url(final_url)

    service = client.get_service("AdGroupAdService")
    operation = client.get_type("AdGroupAdOperation")
    ad_group_ad = operation.create
    ad_group_ad.ad_group = client.get_service("AdGroupService").ad_group_path(
        cid, ad_group_id
    )
    ad_group_ad.status = client.enums.AdGroupAdStatusEnum.ENABLED
    ad = ad_group_ad.ad
    _set_repeated_urls(ad.final_urls, final_url)
    if path1:
        ad.responsive_search_ad.path1 = path1
    if path2:
        ad.responsive_search_ad.path2 = path2
    for text in clean_headlines[:15]:
        asset = client.get_type("AdTextAsset")
        asset.text = text
        ad.responsive_search_ad.headlines.append(asset)
    for text in clean_descriptions[:4]:
        asset = client.get_type("AdTextAsset")
        asset.text = text
        ad.responsive_search_ad.descriptions.append(asset)

    response = service.mutate_ad_group_ads(customer_id=cid, operations=[operation])
    rn = response.results[0].resource_name
    return {"ok": True, "resource_name": rn, "ad_id": rn.split("~")[-1], **preview}


def create_ad_group_with_rsa(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_id: str,
    ad_group_name: str,
    final_url: str,
    headlines: list[str],
    descriptions: list[str],
    keywords: list[dict[str, str]] | None = None,
    cpc_bid: float = 1.0,
    path1: str | None = None,
    path2: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Create ad group + RSA (+ optional keywords) in an existing campaign — one confirm."""
    cid = format_customer_id(customer_id)
    camp_id = str(campaign_id).replace("-", "").strip()
    kw_phrases: list[str] = []
    for item in keywords or []:
        if isinstance(item, str):
            kw_phrases.append(item)
        elif isinstance(item, dict) and item.get("text"):
            kw_phrases.append(str(item["text"]))
    strength = evaluate_rsa_for_ad_strength(
        headlines, descriptions, keywords=kw_phrases or None
    )
    preview = {
        "action": "create_ad_group_with_rsa",
        "customer_id": cid,
        "campaign_id": camp_id,
        "ad_group_name": ad_group_name,
        "final_url": final_url,
        "headlines": headlines,
        "descriptions": descriptions,
        "keywords": keywords or [],
        "cpc_bid": cpc_bid,
        "path1": path1,
        "path2": path2,
        "ad_strength_checklist": strength,
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    clean_headlines, clean_descriptions = validate_rsa_copy(headlines, descriptions)
    if final_url:
        require_working_url(final_url)

    ag = create_ad_group(
        client,
        cid,
        campaign_id=camp_id,
        name=ad_group_name,
        cpc_bid=cpc_bid,
        confirm=True,
    )
    if not ag.get("ok"):
        return ag

    ad_group_id = str(ag["ad_group_id"])
    result: dict[str, Any] = {
        "ok": True,
        "campaign_id": camp_id,
        "ad_group_id": ad_group_id,
        "ad_group": ag,
    }

    if keywords:
        kws = add_keywords(
            client,
            cid,
            ad_group_id=ad_group_id,
            keywords=keywords,
            confirm=True,
        )
        result["keywords"] = kws

    ad = create_responsive_search_ad(
        client,
        cid,
        ad_group_id=ad_group_id,
        final_url=final_url,
        headlines=headlines,
        descriptions=descriptions,
        path1=path1,
        path2=path2,
        confirm=True,
    )
    result["ad"] = ad
    result["ad_id"] = ad.get("ad_id")
    result.update({k: v for k, v in preview.items() if k != "action"})
    result["action"] = "create_ad_group_with_rsa"
    return result


def update_responsive_search_ad(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    ad_id: str,
    headlines: list[str],
    descriptions: list[str],
    final_url: str | None = None,
    path1: str | None = None,
    path2: str | None = None,
    keywords: list[str] | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Replace RSA headlines/descriptions to improve Ad Strength.

    Pins are cleared (assets uploaded without pinned_field) — Google often
    recommends unpinning to raise strength.
    """
    cid = format_customer_id(customer_id)
    strength = evaluate_rsa_for_ad_strength(
        headlines, descriptions, keywords=keywords
    )
    preview = {
        "action": "update_responsive_search_ad",
        "customer_id": cid,
        "ad_id": ad_id,
        "headlines": headlines,
        "descriptions": descriptions,
        "final_url": final_url,
        "path1": path1,
        "path2": path2,
        "pins": "cleared (recommended for Ad Strength)",
        "ad_strength_checklist": strength,
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    clean_headlines, clean_descriptions = validate_rsa_copy(headlines, descriptions)
    if final_url:
        require_working_url(final_url)

    ad_service = client.get_service("AdService")
    operation = client.get_type("AdOperation")
    ad = operation.update
    ad.resource_name = ad_service.ad_path(cid, ad_id)

    for text in clean_headlines:
        asset = client.get_type("AdTextAsset")
        asset.text = text
        ad.responsive_search_ad.headlines.append(asset)
    for text in clean_descriptions:
        asset = client.get_type("AdTextAsset")
        asset.text = text
        ad.responsive_search_ad.descriptions.append(asset)

    paths = [
        "responsive_search_ad.headlines",
        "responsive_search_ad.descriptions",
    ]
    if final_url:
        _set_repeated_urls(ad.final_urls, final_url)
        paths.append("final_urls")
    if path1 is not None:
        ad.responsive_search_ad.path1 = path1
        paths.append("responsive_search_ad.path1")
    if path2 is not None:
        ad.responsive_search_ad.path2 = path2
        paths.append("responsive_search_ad.path2")

    _set_update_mask(operation, *paths)
    response = ad_service.mutate_ads(customer_id=cid, operations=[operation])
    return {
        "ok": True,
        "resource_name": response.results[0].resource_name,
        "headline_count": len(clean_headlines),
        "description_count": len(clean_descriptions),
        **preview,
    }


def create_full_search_setup(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_name: str,
    daily_budget: float,
    ad_group_name: str,
    final_url: str,
    headlines: list[str],
    descriptions: list[str],
    keywords: list[dict[str, str]],
    bidding: str = "maximize_clicks",
    cpc_bid: float = 1.0,
    start_paused: bool = True,
    target_cpa: float | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Create campaign + ad group + keywords + RSA in one confirmed flow."""
    preview = {
        "action": "create_full_search_setup",
        "campaign_name": campaign_name,
        "daily_budget": daily_budget,
        "ad_group_name": ad_group_name,
        "final_url": final_url,
        "keywords": keywords,
        "headlines": headlines,
        "descriptions": descriptions,
        "start_paused": start_paused,
        "bidding": bidding,
        "target_cpa": target_cpa,
        "ad_strength_checklist": evaluate_rsa_for_ad_strength(
            headlines, descriptions, keywords=[k.get("text") if isinstance(k, dict) else str(k) for k in (keywords or [])]
        ),
    }
    blocked = require_confirm(confirm, preview)
    if blocked:
        return blocked

    validate_rsa_copy(headlines, descriptions)
    require_working_url(final_url)

    created_campaign_id: str | None = None
    try:
        camp = create_search_campaign(
            client,
            customer_id,
            name=campaign_name,
            daily_budget=daily_budget,
            bidding=bidding,
            target_cpa=target_cpa,
            start_paused=start_paused,
            confirm=True,
        )
        if not camp.get("ok"):
            return camp
        created_campaign_id = str(camp["campaign_id"])
        ag = create_ad_group(
            client,
            customer_id,
            campaign_id=created_campaign_id,
            name=ad_group_name,
            cpc_bid=cpc_bid,
            confirm=True,
        )
        if not ag.get("ok"):
            raise RuntimeError(ag.get("error") or "ad group create failed")
        kws = None
        if keywords:
            kws = add_keywords(
                client,
                customer_id,
                ad_group_id=ag["ad_group_id"],
                keywords=keywords,
                confirm=True,
            )
        ad = create_responsive_search_ad(
            client,
            customer_id,
            ad_group_id=ag["ad_group_id"],
            final_url=final_url,
            headlines=headlines,
            descriptions=descriptions,
            confirm=True,
        )
        if not ad.get("ok"):
            raise RuntimeError(ad.get("error") or "RSA create failed")
        return {
            "ok": True,
            "campaign": camp,
            "ad_group": ag,
            "keywords": kws,
            "ad": ad,
            "campaign_id": created_campaign_id,
            "ad_group_id": ag.get("ad_group_id"),
            "ad_id": ad.get("ad_id"),
        }
    except Exception as exc:  # noqa: BLE001
        rollback: dict[str, Any] | None = None
        if created_campaign_id:
            try:
                rollback = set_campaign_status(
                    client,
                    customer_id,
                    campaign_id=created_campaign_id,
                    status="PAUSED",
                    confirm=True,
                )
            except Exception as rb:  # noqa: BLE001
                rollback = {"ok": False, "error": str(rb)}
        return {
            "ok": False,
            "error": str(exc),
            "campaign_id": created_campaign_id,
            "rollback": rollback,
            "note": (
                "Partial create rolled back by pausing the campaign when possible. "
                "Inspect campaign_id if rollback failed."
            ),
        }
