from __future__ import annotations

from typing import Any

from google.ads.googleads.client import GoogleAdsClient
from google.protobuf.json_format import MessageToDict

from ads_optimizer.dates import date_range_clause
from ads_optimizer.ids import format_customer_id


def run_gaql(
    client: GoogleAdsClient,
    customer_id: str,
    query: str,
) -> list[dict[str, Any]]:
    """Execute arbitrary GAQL and return JSON-serializable rows."""
    cid = format_customer_id(customer_id)
    service = client.get_service("GoogleAdsService")
    rows: list[dict[str, Any]] = []
    for batch in service.search_stream(customer_id=cid, query=query):
        for row in batch.results:
            rows.append(_proto_row_to_dict(row))
    return rows


def _proto_row_to_dict(row: Any) -> dict[str, Any]:
    try:
        return MessageToDict(row._pb, preserving_proto_field_name=True)
    except AttributeError:
        return MessageToDict(type(row).pb(row), preserving_proto_field_name=True)


def list_accessible_accounts(client: GoogleAdsClient) -> list[dict[str, str]]:
    service = client.get_service("CustomerService")
    response = service.list_accessible_customers()
    accounts: list[dict[str, str]] = []
    for resource_name in response.resource_names:
        cid = format_customer_id(resource_name.split("/")[-1])
        accounts.append({"id": cid, "resource_name": resource_name})
    return accounts


def get_account_currency(client: GoogleAdsClient, customer_id: str) -> dict[str, Any]:
    query = """
        SELECT
          customer.id,
          customer.descriptive_name,
          customer.currency_code,
          customer.time_zone
        FROM customer
        LIMIT 1
    """
    rows = run_gaql(client, customer_id, query)
    if not rows:
        return {"id": format_customer_id(customer_id), "currency_code": "USD"}
    customer = rows[0].get("customer", {})
    return {
        "id": str(customer.get("id", format_customer_id(customer_id))),
        "name": customer.get("descriptive_name", ""),
        "currency_code": customer.get("currency_code", "USD"),
        "time_zone": customer.get("time_zone", ""),
    }


def campaign_performance(
    client: GoogleAdsClient, customer_id: str, days: int = 30
) -> list[dict[str, Any]]:
    query = f"""
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          campaign.advertising_channel_type,
          campaign.bidding_strategy_type,
          campaign.maximize_conversions.target_cpa_micros,
          campaign.target_cpa.target_cpa_micros,
          campaign.target_roas.target_roas,
          campaign.maximize_conversion_value.target_roas,
          campaign.target_spend.cpc_bid_ceiling_micros,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value,
          metrics.average_cpc,
          metrics.ctr
        FROM campaign
        WHERE {date_range_clause(days)}
          AND campaign.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC
        LIMIT 100
    """
    return _normalize_metric_rows(run_gaql(client, customer_id, query), entity="campaign")


def list_ad_groups(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_id: str | None = None,
    name_contains: str | None = None,
) -> list[dict[str, Any]]:
    """List ad groups with ids — for looking up ad_group_id before creating RSA."""
    where = ["campaign.status != 'REMOVED'", "ad_group.status != 'REMOVED'"]
    if campaign_id:
        where.append(f"campaign.id = {int(str(campaign_id).replace('-', ''))}")
    query = f"""
        SELECT
          campaign.id,
          campaign.name,
          ad_group.id,
          ad_group.name,
          ad_group.status
        FROM ad_group
        WHERE {" AND ".join(where)}
        ORDER BY campaign.name, ad_group.name
    """
    rows = run_gaql(client, customer_id, query)

    ads_query = """
        SELECT
          ad_group.id,
          ad_group_ad.ad.id,
          ad_group_ad.status
        FROM ad_group_ad
        WHERE campaign.status != 'REMOVED'
          AND ad_group.status != 'REMOVED'
          AND ad_group_ad.status != 'REMOVED'
    """
    ads_count: dict[str, int] = {}
    for row in run_gaql(client, customer_id, ads_query):
        ag_id = str((row.get("ad_group") or {}).get("id", "") or "")
        if ag_id:
            ads_count[ag_id] = ads_count.get(ag_id, 0) + 1

    needle = (name_contains or "").strip().lower()
    items: list[dict[str, Any]] = []
    for row in rows:
        ag = row.get("ad_group") or {}
        camp = row.get("campaign") or {}
        ag_id = str(ag.get("id", "") or "")
        name = ag.get("name", "") or ""
        if needle and needle not in name.lower() and needle not in (camp.get("name") or "").lower():
            continue
        count = ads_count.get(ag_id, 0)
        items.append(
            {
                "campaign_id": str(camp.get("id", "") or ""),
                "campaign": camp.get("name", ""),
                "ad_group_id": ag_id,
                "ad_group": name,
                "status": ag.get("status", ""),
                "ads_count": count,
                "has_ads": count > 0,
                "empty_ad_group": count == 0,
            }
        )
    return items


def ad_performance(
    client: GoogleAdsClient, customer_id: str, days: int = 30
) -> list[dict[str, Any]]:
    """Full ad inventory + period metrics (includes ads/groups with 0 traffic).

    Also appends placeholder rows for ENABLED ad groups that have no non-removed ads,
    so empty groups (e.g. Kurorty without RSA) are visible in the UI.
    """
    inventory_query = """
        SELECT
          campaign.id,
          campaign.name,
          ad_group.id,
          ad_group.name,
          ad_group_ad.ad.id,
          ad_group_ad.ad.name,
          ad_group_ad.status,
          ad_group_ad.ad.responsive_search_ad.headlines
        FROM ad_group_ad
        WHERE campaign.status != 'REMOVED'
          AND ad_group.status != 'REMOVED'
          AND ad_group_ad.status != 'REMOVED'
        ORDER BY campaign.name, ad_group.name
    """
    metrics_query = f"""
        SELECT
          ad_group.id,
          ad_group_ad.ad.id,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value,
          metrics.ctr
        FROM ad_group_ad
        WHERE {date_range_clause(days)}
          AND campaign.status != 'REMOVED'
          AND ad_group_ad.status != 'REMOVED'
    """
    groups_query = """
        SELECT
          campaign.id,
          campaign.name,
          ad_group.id,
          ad_group.name,
          ad_group.status
        FROM ad_group
        WHERE campaign.status != 'REMOVED'
          AND ad_group.status != 'REMOVED'
        ORDER BY campaign.name, ad_group.name
    """

    metrics_by_key: dict[str, dict[str, Any]] = {}
    for row in run_gaql(client, customer_id, metrics_query):
        ad_id = str((row.get("ad_group_ad") or {}).get("ad", {}).get("id", "") or "")
        ag_id = str((row.get("ad_group") or {}).get("id", "") or "")
        if not ad_id:
            continue
        key = f"{ag_id}:{ad_id}"
        metrics = row.get("metrics", {}) or {}
        bucket = metrics_by_key.setdefault(
            key,
            {
                "impressions": 0,
                "clicks": 0,
                "cost_micros": 0,
                "conversions": 0.0,
                "conversions_value": 0.0,
            },
        )
        bucket["impressions"] += int(metrics.get("impressions", 0) or 0)
        bucket["clicks"] += int(metrics.get("clicks", 0) or 0)
        bucket["cost_micros"] += int(metrics.get("cost_micros", 0) or 0)
        bucket["conversions"] += float(metrics.get("conversions", 0) or 0)
        bucket["conversions_value"] += float(metrics.get("conversions_value", 0) or 0)

    out: list[dict[str, Any]] = []
    groups_with_ads: set[str] = set()
    for row in run_gaql(client, customer_id, inventory_query):
        aga = row.get("ad_group_ad", {}) or {}
        ad = aga.get("ad", {}) or {}
        rsa = ad.get("responsive_search_ad") or {}
        headlines = [
            h.get("text", "") for h in (rsa.get("headlines") or []) if h.get("text")
        ]
        ad_id = str(ad.get("id", "") or "")
        ag_id = str((row.get("ad_group") or {}).get("id", "") or "")
        groups_with_ads.add(ag_id)
        m = metrics_by_key.get(f"{ag_id}:{ad_id}", {})
        cost = int(m.get("cost_micros", 0) or 0) / 1_000_000
        clicks = int(m.get("clicks", 0) or 0)
        impressions = int(m.get("impressions", 0) or 0)
        conversions = float(m.get("conversions", 0) or 0)
        value = float(m.get("conversions_value", 0) or 0)
        display_name = (
            (ad.get("name") or "").strip()
            or (headlines[0] if headlines else "")
            or (f"Ad {ad_id}" if ad_id else "Ad")
        )
        out.append(
            {
                "id": ad_id,
                "ad_id": ad_id,
                "name": display_name,
                "status": aga.get("status", ""),
                "campaign_id": str((row.get("campaign") or {}).get("id", "") or ""),
                "ad_group_id": ag_id,
                "campaign": (row.get("campaign") or {}).get("name", ""),
                "ad_group": (row.get("ad_group") or {}).get("name", ""),
                "impressions": impressions,
                "clicks": clicks,
                "cost": round(cost, 2),
                "conversions": round(conversions, 2),
                "conversions_value": round(value, 2),
                "ctr": round(clicks / impressions, 4) if impressions else 0,
                "cpa": round(cost / conversions, 2) if conversions else 0,
                "roas": round(value / cost, 2) if cost else 0,
                "headline": headlines[0] if headlines else "",
                "empty_ad_group": False,
            }
        )

    for row in run_gaql(client, customer_id, groups_query):
        ag_id = str((row.get("ad_group") or {}).get("id", "") or "")
        if not ag_id or ag_id in groups_with_ads:
            continue
        out.append(
            {
                "id": "",
                "ad_id": "",
                "name": "(нет объявления)",
                "status": "NO_AD",
                "campaign_id": str((row.get("campaign") or {}).get("id", "") or ""),
                "ad_group_id": ag_id,
                "campaign": (row.get("campaign") or {}).get("name", ""),
                "ad_group": (row.get("ad_group") or {}).get("name", ""),
                "impressions": 0,
                "clicks": 0,
                "cost": 0,
                "conversions": 0,
                "conversions_value": 0,
                "ctr": 0,
                "cpa": 0,
                "roas": 0,
                "headline": "",
                "empty_ad_group": True,
            }
        )

    out.sort(
        key=lambda r: (
            r.get("campaign") or "",
            r.get("ad_group") or "",
            1 if r.get("empty_ad_group") else 0,
            r.get("name") or "",
        )
    )
    return out


def ad_creatives(client: GoogleAdsClient, customer_id: str) -> list[dict[str, Any]]:
    query = """
        SELECT
          campaign.id,
          campaign.name,
          ad_group.id,
          ad_group.name,
          ad_group_ad.resource_name,
          ad_group_ad.ad.id,
          ad_group_ad.ad.name,
          ad_group_ad.ad.type,
          ad_group_ad.status,
          ad_group_ad.ad_strength,
          ad_group_ad.action_items,
          ad_group_ad.policy_summary.approval_status,
          ad_group_ad.policy_summary.review_status,
          ad_group_ad.policy_summary.policy_topic_entries,
          ad_group_ad.primary_status,
          ad_group_ad.ad.final_urls,
          ad_group_ad.ad.responsive_search_ad.headlines,
          ad_group_ad.ad.responsive_search_ad.descriptions,
          ad_group_ad.ad.responsive_search_ad.path1,
          ad_group_ad.ad.responsive_search_ad.path2
        FROM ad_group_ad
        WHERE campaign.status != 'REMOVED'
          AND ad_group.status != 'REMOVED'
          AND ad_group_ad.status != 'REMOVED'
        ORDER BY campaign.name, ad_group.name
    """
    try:
        rows = run_gaql(client, customer_id, query)
    except Exception:
        query = query.replace("ad_group_ad.policy_summary.policy_topic_entries,\n          ", "")
        rows = run_gaql(client, customer_id, query)
    creatives: list[dict[str, Any]] = []
    groups_with_ads: set[str] = set()
    for row in rows:
        aga = row.get("ad_group_ad", {}) or {}
        ad = aga.get("ad", {}) or {}
        rsa = ad.get("responsive_search_ad", {}) or {}
        pol = aga.get("policy_summary") or {}
        topics_raw = pol.get("policy_topic_entries") or []
        policy_topics: list[dict[str, str]] = []
        for t in topics_raw:
            if not isinstance(t, dict):
                continue
            topic = str(t.get("topic") or "").strip()
            if not topic:
                continue
            policy_topics.append(
                {
                    "topic": topic,
                    "type": str(t.get("type") or t.get("type_") or ""),
                }
            )
        headline_assets = [
            {"text": h.get("text", ""), "pinned": h.get("pinned_field") or None}
            for h in (rsa.get("headlines") or [])
        ]
        description_assets = [
            {"text": d.get("text", ""), "pinned": d.get("pinned_field") or None}
            for d in (rsa.get("descriptions") or [])
        ]
        headlines = [h["text"] for h in headline_assets if h.get("text")]
        descriptions = [d["text"] for d in description_assets if d.get("text")]
        strength = aga.get("ad_strength") or ""
        ag_id = str(row.get("ad_group", {}).get("id", "") or "")
        groups_with_ads.add(ag_id)
        display_name = (
            (ad.get("name") or "").strip()
            or (headlines[0] if headlines else "")
            or f"Ad {ad.get('id', '')}"
        )
        creatives.append(
            {
                "campaign_id": str(row.get("campaign", {}).get("id", "") or ""),
                "ad_group_id": ag_id,
                "campaign": row.get("campaign", {}).get("name", ""),
                "ad_group": row.get("ad_group", {}).get("name", ""),
                "resource_name": aga.get("resource_name", ""),
                "ad_id": str(ad.get("id", "")),
                "name": display_name,
                "type": ad.get("type", ""),
                "status": aga.get("status", ""),
                "ad_strength": strength,
                "action_items": list(aga.get("action_items") or []),
                "approval_status": pol.get("approval_status") or "",
                "review_status": pol.get("review_status") or "",
                "policy_topics": policy_topics,
                "primary_status": aga.get("primary_status") or "",
                "needs_improvement": str(strength).upper()
                in {"POOR", "AVERAGE", "INCOMPLETE", "PENDING"},
                "final_urls": ad.get("final_urls", []),
                "path1": rsa.get("path1") or "",
                "path2": rsa.get("path2") or "",
                "headlines": headlines,
                "descriptions": descriptions,
                "headline_assets": headline_assets,
                "description_assets": description_assets,
                "headline_count": len(headlines),
                "description_count": len(descriptions),
                "empty_ad_group": False,
            }
        )

    groups_query = """
        SELECT
          campaign.id,
          campaign.name,
          ad_group.id,
          ad_group.name,
          ad_group.status
        FROM ad_group
        WHERE campaign.status != 'REMOVED'
          AND ad_group.status != 'REMOVED'
    """
    for row in run_gaql(client, customer_id, groups_query):
        ag_id = str((row.get("ad_group") or {}).get("id", "") or "")
        if not ag_id or ag_id in groups_with_ads:
            continue
        creatives.append(
            {
                "campaign_id": str((row.get("campaign") or {}).get("id", "") or ""),
                "ad_group_id": ag_id,
                "campaign": (row.get("campaign") or {}).get("name", ""),
                "ad_group": (row.get("ad_group") or {}).get("name", ""),
                "resource_name": "",
                "ad_id": "",
                "name": "(нет объявления)",
                "type": "",
                "status": "NO_AD",
                "ad_strength": "MISSING",
                "action_items": ["Create a Responsive Search Ad for this ad group."],
                "needs_improvement": True,
                "final_urls": [],
                "path1": "",
                "path2": "",
                "headlines": [],
                "descriptions": [],
                "headline_assets": [],
                "description_assets": [],
                "headline_count": 0,
                "description_count": 0,
                "empty_ad_group": True,
            }
        )

    order = {
        "MISSING": -1,
        "INCOMPLETE": 0,
        "POOR": 1,
        "PENDING": 2,
        "AVERAGE": 3,
        "GOOD": 4,
        "EXCELLENT": 5,
    }
    creatives.sort(
        key=lambda c: (
            order.get(str(c.get("ad_strength") or "").upper(), 9),
            c.get("campaign") or "",
            c.get("ad_group") or "",
        )
    )
    return creatives


def keyword_performance(
    client: GoogleAdsClient, customer_id: str, days: int = 30
) -> list[dict[str, Any]]:
    """Full keyword inventory + metrics for the selected period.

    Google Ads UI shows all keywords in the ad group. The previous query used
    keyword_view + LIMIT 100 ordered by cost, so zero-traffic and long-tail
    keywords looked "missing" / stale compared to the account.
    """
    inventory_query = """
        SELECT
          campaign.id,
          campaign.name,
          ad_group.id,
          ad_group.name,
          ad_group_criterion.criterion_id,
          ad_group_criterion.keyword.text,
          ad_group_criterion.keyword.match_type,
          ad_group_criterion.status
        FROM ad_group_criterion
        WHERE ad_group_criterion.type = 'KEYWORD'
          AND campaign.status != 'REMOVED'
          AND ad_group.status != 'REMOVED'
          AND ad_group_criterion.status != 'REMOVED'
        ORDER BY campaign.name, ad_group.name, ad_group_criterion.keyword.text
    """
    metrics_query = f"""
        SELECT
          ad_group_criterion.criterion_id,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value,
          metrics.ctr,
          metrics.average_cpc
        FROM keyword_view
        WHERE {date_range_clause(days)}
          AND campaign.status != 'REMOVED'
          AND ad_group_criterion.status != 'REMOVED'
    """
    inventory = run_gaql(client, customer_id, inventory_query)
    metrics_by_id: dict[str, dict[str, Any]] = {}
    for row in run_gaql(client, customer_id, metrics_query):
        cid = str(row.get("ad_group_criterion", {}).get("criterion_id", "") or "")
        if not cid:
            continue
        metrics = row.get("metrics", {}) or {}
        bucket = metrics_by_id.setdefault(
            cid,
            {
                "impressions": 0,
                "clicks": 0,
                "cost_micros": 0,
                "conversions": 0.0,
                "conversions_value": 0.0,
                "average_cpc": 0,
            },
        )
        bucket["impressions"] += int(metrics.get("impressions", 0) or 0)
        bucket["clicks"] += int(metrics.get("clicks", 0) or 0)
        bucket["cost_micros"] += int(metrics.get("cost_micros", 0) or 0)
        bucket["conversions"] += float(metrics.get("conversions", 0) or 0)
        bucket["conversions_value"] += float(metrics.get("conversions_value", 0) or 0)
        bucket["average_cpc"] = int(metrics.get("average_cpc", 0) or 0)

    out: list[dict[str, Any]] = []
    for row in inventory:
        criterion = row.get("ad_group_criterion", {}) or {}
        keyword = criterion.get("keyword", {}) or {}
        criterion_id = str(criterion.get("criterion_id", "") or "")
        m = metrics_by_id.get(criterion_id, {})
        cost = int(m.get("cost_micros", 0) or 0) / 1_000_000
        clicks = int(m.get("clicks", 0) or 0)
        impressions = int(m.get("impressions", 0) or 0)
        conversions = float(m.get("conversions", 0) or 0)
        value = float(m.get("conversions_value", 0) or 0)
        out.append(
            {
                "criterion_id": criterion_id,
                "campaign_id": str(row.get("campaign", {}).get("id", "") or ""),
                "ad_group_id": str(row.get("ad_group", {}).get("id", "") or ""),
                "text": keyword.get("text", ""),
                "match_type": keyword.get("match_type", ""),
                "status": criterion.get("status", ""),
                "campaign": row.get("campaign", {}).get("name", ""),
                "ad_group": row.get("ad_group", {}).get("name", ""),
                "impressions": impressions,
                "clicks": clicks,
                "cost": round(cost, 2),
                "conversions": round(conversions, 2),
                "conversions_value": round(value, 2),
                "ctr": round(clicks / impressions, 4) if impressions else 0,
                "cpa": round(cost / conversions, 2) if conversions else 0,
                "roas": round(value / cost, 2) if cost else 0,
                "avg_cpc": round(int(m.get("average_cpc", 0) or 0) / 1_000_000, 2),
            }
        )
    return out


def daily_trend(
    client: GoogleAdsClient, customer_id: str, days: int = 30
) -> list[dict[str, Any]]:
    query = f"""
        SELECT
          segments.date,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value
        FROM customer
        WHERE {date_range_clause(days)}
        ORDER BY segments.date
    """
    rows = run_gaql(client, customer_id, query)
    out: list[dict[str, Any]] = []
    for row in rows:
        metrics = row.get("metrics", {})
        cost = int(metrics.get("cost_micros", 0) or 0) / 1_000_000
        conversions = float(metrics.get("conversions", 0) or 0)
        value = float(metrics.get("conversions_value", 0) or 0)
        out.append(
            {
                "date": row.get("segments", {}).get("date"),
                "impressions": int(metrics.get("impressions", 0) or 0),
                "clicks": int(metrics.get("clicks", 0) or 0),
                "cost": round(cost, 2),
                "conversions": round(conversions, 2),
                "conversions_value": round(value, 2),
                "roas": round(value / cost, 2) if cost else 0,
            }
        )
    return out


def ad_strength_report(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    strengths: list[str] | None = None,
) -> dict[str, Any]:
    """RSA Ad Strength (Сила объявления) + Google action items."""
    all_items = ad_creatives(client, customer_id)
    summary: dict[str, int] = {}
    for c in all_items:
        key = str(c.get("ad_strength") or "UNKNOWN").upper() or "UNKNOWN"
        summary[key] = summary.get(key, 0) + 1

    wanted = {s.strip().upper() for s in (strengths or []) if s and s.strip()}
    filtered = (
        [c for c in all_items if str(c.get("ad_strength") or "").upper() in wanted]
        if wanted
        else all_items
    )
    weak = [
        c
        for c in all_items
        if str(c.get("ad_strength") or "").upper() in {"POOR", "INCOMPLETE", "AVERAGE"}
    ]
    return {
        "summary": summary,
        "poor_or_average_count": len(weak),
        "total": len(all_items),
        "items": filtered,
        "note": (
            "Ad Strength = Google RSA quality (Incomplete/Poor/Average/Good/Excellent). "
            "Use action_items + update_responsive_search_ad (confirm) to fix. "
            "Ad Strength = Google RSA quality (Incomplete/Poor/Average/Good/Excellent). "
            "ALWAYS read action_items first and act on them (sitelinks → add_sitelinks; "
            "keywords → rewrite H/D). Aim ≥6 sitelinks per campaign. "
            "Use update_responsive_search_ad (confirm) for copy. "
            "Aim for 10–15 unique headlines and 3–4 descriptions; unpin most assets. "
            "Keyword density + semantic diversity (rsa-ad-strength): primary KW in ≥4 headlines, "
            "≥50% headlines with ad-group keywords, ≥2 descriptions with primary KW; "
            "no Transfer/Transport/Taxi×N stacking — use 4–5 route + ~10 universal headlines."
        ),
    }


def negative_keywords(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """List existing negative keywords (campaign + ad group levels)."""
    lim = max(1, min(int(limit or 500), 2000))
    out: list[dict[str, Any]] = []

    camp_where = ["campaign.status != 'REMOVED'", "campaign_criterion.negative = TRUE"]
    if campaign_id:
        camp_where.append(f"campaign.id = {int(str(campaign_id).replace('-', ''))}")
    camp_query = f"""
        SELECT
          campaign.id,
          campaign.name,
          campaign_criterion.criterion_id,
          campaign_criterion.keyword.text,
          campaign_criterion.keyword.match_type
        FROM campaign_criterion
        WHERE {" AND ".join(camp_where)}
          AND campaign_criterion.type = 'KEYWORD'
        LIMIT {lim}
    """
    for row in run_gaql(client, customer_id, camp_query):
        crit = row.get("campaign_criterion", {}) or {}
        kw = crit.get("keyword", {}) or {}
        out.append(
            {
                "level": "campaign",
                "campaign_id": str(row.get("campaign", {}).get("id", "") or ""),
                "campaign": row.get("campaign", {}).get("name", ""),
                "ad_group_id": "",
                "ad_group": "",
                "criterion_id": str(crit.get("criterion_id", "") or ""),
                "text": kw.get("text", ""),
                "match_type": kw.get("match_type", ""),
            }
        )

    ag_where = [
        "campaign.status != 'REMOVED'",
        "ad_group.status != 'REMOVED'",
        "ad_group_criterion.negative = TRUE",
        "ad_group_criterion.type = 'KEYWORD'",
        "ad_group_criterion.status != 'REMOVED'",
    ]
    if campaign_id:
        ag_where.append(f"campaign.id = {int(str(campaign_id).replace('-', ''))}")
    if ad_group_id:
        ag_where.append(f"ad_group.id = {int(str(ad_group_id).replace('-', ''))}")
    ag_query = f"""
        SELECT
          campaign.id,
          campaign.name,
          ad_group.id,
          ad_group.name,
          ad_group_criterion.criterion_id,
          ad_group_criterion.keyword.text,
          ad_group_criterion.keyword.match_type
        FROM ad_group_criterion
        WHERE {" AND ".join(ag_where)}
        LIMIT {lim}
    """
    for row in run_gaql(client, customer_id, ag_query):
        crit = row.get("ad_group_criterion", {}) or {}
        kw = crit.get("keyword", {}) or {}
        out.append(
            {
                "level": "ad_group",
                "campaign_id": str(row.get("campaign", {}).get("id", "") or ""),
                "campaign": row.get("campaign", {}).get("name", ""),
                "ad_group_id": str(row.get("ad_group", {}).get("id", "") or ""),
                "ad_group": row.get("ad_group", {}).get("name", ""),
                "criterion_id": str(crit.get("criterion_id", "") or ""),
                "text": kw.get("text", ""),
                "match_type": kw.get("match_type", ""),
            }
        )
    return out


def _normalize_metric_rows(
    rows: list[dict[str, Any]], *, entity: str
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        metrics = row.get("metrics", {})
        cost = int(metrics.get("cost_micros", 0) or 0) / 1_000_000
        clicks = int(metrics.get("clicks", 0) or 0)
        impressions = int(metrics.get("impressions", 0) or 0)
        conversions = float(metrics.get("conversions", 0) or 0)
        value = float(metrics.get("conversions_value", 0) or 0)
        item: dict[str, Any] = {
            "impressions": impressions,
            "clicks": clicks,
            "cost": round(cost, 2),
            "conversions": round(conversions, 2),
            "conversions_value": round(value, 2),
            "ctr": round(clicks / impressions, 4) if impressions else 0,
            "cpa": round(cost / conversions, 2) if conversions else 0,
            "roas": round(value / cost, 2) if cost else 0,
            "avg_cpc": round(
                int(metrics.get("average_cpc", 0) or 0) / 1_000_000, 2
            ),
        }
        if entity == "campaign":
            camp = row.get("campaign", {}) or {}
            mc = camp.get("maximize_conversions") or {}
            tc = camp.get("target_cpa") or {}
            tr = camp.get("target_roas") or {}
            mv = camp.get("maximize_conversion_value") or {}
            ts = camp.get("target_spend") or {}
            target_cpa_micros = int(
                mc.get("target_cpa_micros") or tc.get("target_cpa_micros") or 0
            )
            target_roas_val = float(tr.get("target_roas") or mv.get("target_roas") or 0)
            ceiling = int(ts.get("cpc_bid_ceiling_micros") or 0)
            item.update(
                {
                    "id": str(camp.get("id", "")),
                    "name": camp.get("name", ""),
                    "status": camp.get("status", ""),
                    "channel": camp.get("advertising_channel_type", ""),
                    "bidding_strategy_type": camp.get("bidding_strategy_type", ""),
                    "target_cpa": round(target_cpa_micros / 1_000_000, 2)
                    if target_cpa_micros
                    else None,
                    "target_roas": round(target_roas_val, 4) if target_roas_val else None,
                    "cpc_bid_ceiling": round(ceiling / 1_000_000, 2) if ceiling else None,
                }
            )
        elif entity == "ad":
            ad = row.get("ad_group_ad", {}).get("ad", {})
            item.update(
                {
                    "id": str(ad.get("id", "")),
                    "name": ad.get("name") or f"Ad {ad.get('id', '')}",
                    "status": row.get("ad_group_ad", {}).get("status", ""),
                    "campaign_id": str(row.get("campaign", {}).get("id", "") or ""),
                    "ad_group_id": str(row.get("ad_group", {}).get("id", "") or ""),
                    "campaign": row.get("campaign", {}).get("name", ""),
                    "ad_group": row.get("ad_group", {}).get("name", ""),
                }
            )
        elif entity == "keyword":
            criterion = row.get("ad_group_criterion", {})
            keyword = criterion.get("keyword", {})
            item.update(
                {
                    "criterion_id": str(criterion.get("criterion_id", "") or ""),
                    "campaign_id": str(row.get("campaign", {}).get("id", "") or ""),
                    "ad_group_id": str(row.get("ad_group", {}).get("id", "") or ""),
                    "text": keyword.get("text", ""),
                    "match_type": keyword.get("match_type", ""),
                    "status": criterion.get("status", ""),
                    "campaign": row.get("campaign", {}).get("name", ""),
                    "ad_group": row.get("ad_group", {}).get("name", ""),
                }
            )
        out.append(item)
    return out


def conversion_actions(client: GoogleAdsClient, customer_id: str) -> list[dict[str, Any]]:
    query = """
        SELECT
          conversion_action.id,
          conversion_action.name,
          conversion_action.type,
          conversion_action.status,
          conversion_action.category,
          conversion_action.origin,
          conversion_action.primary_for_goal,
          conversion_action.include_in_conversions_metric,
          conversion_action.counting_type
        FROM conversion_action
        WHERE conversion_action.status != 'REMOVED'
        ORDER BY conversion_action.name
    """
    rows = run_gaql(client, customer_id, query)
    items: list[dict[str, Any]] = []
    for row in rows:
        ca = row.get("conversion_action", {}) or {}
        items.append(
            {
                "id": str(ca.get("id", "") or ""),
                "name": ca.get("name", ""),
                "type": ca.get("type", ""),
                "status": ca.get("status", ""),
                "category": ca.get("category", ""),
                "origin": ca.get("origin", ""),
                "primary_for_goal": bool(ca.get("primary_for_goal", False)),
                "include_in_conversions_metric": bool(
                    ca.get("include_in_conversions_metric", False)
                ),
                "counting_type": ca.get("counting_type", ""),
            }
        )
    return items


def customer_conversion_goals(
    client: GoogleAdsClient, customer_id: str
) -> list[dict[str, Any]]:
    query = """
        SELECT
          customer_conversion_goal.category,
          customer_conversion_goal.origin,
          customer_conversion_goal.biddable
        FROM customer_conversion_goal
    """
    rows = run_gaql(client, customer_id, query)
    return [
        {
            "category": (row.get("customer_conversion_goal") or {}).get("category", ""),
            "origin": (row.get("customer_conversion_goal") or {}).get("origin", ""),
            "biddable": bool((row.get("customer_conversion_goal") or {}).get("biddable", False)),
            "level": "customer",
        }
        for row in rows
    ]


def campaign_conversion_goals(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_id: str | None = None,
) -> list[dict[str, Any]]:
    where = ["campaign.status != 'REMOVED'"]
    if campaign_id:
        where.append(f"campaign.id = {int(str(campaign_id).replace('-', ''))}")
    query = f"""
        SELECT
          campaign.id,
          campaign.name,
          campaign_conversion_goal.category,
          campaign_conversion_goal.origin,
          campaign_conversion_goal.biddable
        FROM campaign_conversion_goal
        WHERE {" AND ".join(where)}
    """
    rows = run_gaql(client, customer_id, query)
    return [
        {
            "campaign_id": str((row.get("campaign") or {}).get("id", "") or ""),
            "campaign": (row.get("campaign") or {}).get("name", ""),
            "category": (row.get("campaign_conversion_goal") or {}).get("category", ""),
            "origin": (row.get("campaign_conversion_goal") or {}).get("origin", ""),
            "biddable": bool((row.get("campaign_conversion_goal") or {}).get("biddable", False)),
            "level": "campaign",
        }
        for row in rows
    ]


def conversion_goal_configs(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_id: str | None = None,
) -> list[dict[str, Any]]:
    where = ["campaign.status != 'REMOVED'"]
    if campaign_id:
        where.append(f"campaign.id = {int(str(campaign_id).replace('-', ''))}")
    query = f"""
        SELECT
          campaign.id,
          campaign.name,
          conversion_goal_campaign_config.goal_config_level,
          conversion_goal_campaign_config.custom_conversion_goal,
          custom_conversion_goal.id,
          custom_conversion_goal.name
        FROM conversion_goal_campaign_config
        WHERE {" AND ".join(where)}
    """
    rows = run_gaql(client, customer_id, query)
    items: list[dict[str, Any]] = []
    for row in rows:
        cfg = row.get("conversion_goal_campaign_config") or {}
        custom = row.get("custom_conversion_goal") or {}
        items.append(
            {
                "campaign_id": str((row.get("campaign") or {}).get("id", "") or ""),
                "campaign": (row.get("campaign") or {}).get("name", ""),
                "goal_config_level": cfg.get("goal_config_level", ""),
                "custom_conversion_goal": cfg.get("custom_conversion_goal", ""),
                "custom_goal_id": str(custom.get("id", "") or ""),
                "custom_goal_name": custom.get("name", ""),
            }
        )
    return items


def custom_conversion_goals(client: GoogleAdsClient, customer_id: str) -> list[dict[str, Any]]:
    query = """
        SELECT
          custom_conversion_goal.id,
          custom_conversion_goal.name,
          custom_conversion_goal.status,
          custom_conversion_goal.conversion_actions
        FROM custom_conversion_goal
    """
    rows = run_gaql(client, customer_id, query)
    items: list[dict[str, Any]] = []
    for row in rows:
        g = row.get("custom_conversion_goal") or {}
        actions = g.get("conversion_actions") or []
        items.append(
            {
                "id": str(g.get("id", "") or ""),
                "name": g.get("name", ""),
                "status": g.get("status", ""),
                "conversion_actions": list(actions),
            }
        )
    return items


def conversion_goals_report(
    client: GoogleAdsClient,
    customer_id: str,
    *,
    campaign_id: str | None = None,
) -> dict[str, Any]:
    return {
        "conversion_actions": conversion_actions(client, customer_id),
        "customer_goals": customer_conversion_goals(client, customer_id),
        "campaign_goal_configs": conversion_goal_configs(
            client, customer_id, campaign_id=campaign_id
        ),
        "campaign_goals": campaign_conversion_goals(
            client, customer_id, campaign_id=campaign_id
        ),
        "custom_goals": custom_conversion_goals(client, customer_id),
        "note": (
            "Use set_conversion_action_primary / set_campaign_conversion_goal / "
            "create_custom_conversion_goal / set_campaign_goal_config to change goals. "
            "confirm required for mutations."
        ),
    }
