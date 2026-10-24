from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ads_optimizer.models import ActionType, Recommendation, Severity
from ads_optimizer.setup_guide import setup_payload


def demo_accounts() -> list[dict[str, str]]:
    return [
        {"id": "1234567890", "resource_name": "customers/1234567890", "name": "Demo Brand"},
        {"id": "0987654321", "resource_name": "customers/0987654321", "name": "Demo Shop"},
    ]


def demo_account_meta() -> dict[str, Any]:
    return {
        "id": "1234567890",
        "name": "Demo Brand",
        "currency_code": "USD",
        "time_zone": "Europe/Moscow",
        "demo": True,
    }


def demo_campaigns() -> list[dict[str, Any]]:
    return [
        {
            "id": "101",
            "name": "Search — Brand",
            "status": "ENABLED",
            "channel": "SEARCH",
            "impressions": 42000,
            "clicks": 3100,
            "cost": 1850.0,
            "conversions": 210,
            "conversions_value": 12600,
            "ctr": 0.0738,
            "cpa": 8.81,
            "roas": 6.81,
            "avg_cpc": 0.6,
        },
        {
            "id": "102",
            "name": "Search — Non-Brand",
            "status": "ENABLED",
            "channel": "SEARCH",
            "impressions": 88000,
            "clicks": 4200,
            "cost": 5200.0,
            "conversions": 95,
            "conversions_value": 7600,
            "ctr": 0.0477,
            "cpa": 54.74,
            "roas": 1.46,
            "avg_cpc": 1.24,
        },
        {
            "id": "103",
            "name": "Performance Max — Catalog",
            "status": "ENABLED",
            "channel": "PERFORMANCE_MAX",
            "impressions": 210000,
            "clicks": 6800,
            "cost": 4100.0,
            "conversions": 160,
            "conversions_value": 11200,
            "ctr": 0.0324,
            "cpa": 25.63,
            "roas": 2.73,
            "avg_cpc": 0.6,
        },
        {
            "id": "104",
            "name": "Display — Remarketing",
            "status": "PAUSED",
            "channel": "DISPLAY",
            "impressions": 150000,
            "clicks": 900,
            "cost": 640.0,
            "conversions": 12,
            "conversions_value": 720,
            "ctr": 0.006,
            "cpa": 53.33,
            "roas": 1.13,
            "avg_cpc": 0.71,
        },
    ]


def demo_keywords() -> list[dict[str, Any]]:
    return [
        {
            "text": "buy running shoes",
            "match_type": "PHRASE",
            "status": "ENABLED",
            "campaign_id": "1",
            "ad_group_id": "11",
            "campaign": "Search — Non-Brand",
            "ad_group": "Running",
            "impressions": 12000,
            "clicks": 680,
            "cost": 920.0,
            "conversions": 28,
            "conversions_value": 2100,
            "ctr": 0.0567,
            "cpa": 32.86,
            "roas": 2.28,
            "avg_cpc": 1.35,
        },
        {
            "text": "free shoes pdf",
            "match_type": "BROAD",
            "status": "ENABLED",
            "campaign_id": "1",
            "ad_group_id": "11",
            "campaign": "Search — Non-Brand",
            "ad_group": "Running",
            "impressions": 9000,
            "clicks": 410,
            "cost": 380.0,
            "conversions": 0,
            "conversions_value": 0,
            "ctr": 0.0456,
            "cpa": 0,
            "roas": 0,
            "avg_cpc": 0.93,
        },
        {
            "text": "demo brand official",
            "match_type": "EXACT",
            "status": "ENABLED",
            "campaign_id": "2",
            "ad_group_id": "21",
            "campaign": "Search — Brand",
            "ad_group": "Brand",
            "impressions": 8000,
            "clicks": 1200,
            "cost": 420.0,
            "conversions": 95,
            "conversions_value": 5700,
            "ctr": 0.15,
            "cpa": 4.42,
            "roas": 13.57,
            "avg_cpc": 0.35,
        },
    ]


def demo_ads() -> list[dict[str, Any]]:
    return [
        {
            "id": "501",
            "name": "RSA — Brand Core",
            "status": "ENABLED",
            "campaign_id": "2",
            "ad_group_id": "21",
            "campaign": "Search — Brand",
            "ad_group": "Brand",
            "impressions": 18000,
            "clicks": 1600,
            "cost": 780.0,
            "conversions": 120,
            "conversions_value": 7200,
            "ctr": 0.0889,
            "cpa": 6.5,
            "roas": 9.23,
            "avg_cpc": 0.49,
        },
        {
            "id": "502",
            "name": "RSA — Generic Weak",
            "status": "ENABLED",
            "campaign_id": "1",
            "ad_group_id": "11",
            "campaign": "Search — Non-Brand",
            "ad_group": "Running",
            "impressions": 22000,
            "clicks": 420,
            "cost": 610.0,
            "conversions": 4,
            "conversions_value": 280,
            "ctr": 0.0191,
            "cpa": 152.5,
            "roas": 0.46,
            "avg_cpc": 1.45,
        },
    ]


def demo_creatives() -> list[dict[str, Any]]:
    return [
        {
            "campaign": "Search — Brand",
            "ad_group": "Brand",
            "campaign_id": "2",
            "ad_group_id": "21",
            "ad_id": "501",
            "name": "RSA — Brand Core",
            "type": "RESPONSIVE_SEARCH_AD",
            "status": "ENABLED",
            "ad_strength": "GOOD",
            "action_items": [],
            "needs_improvement": False,
            "final_urls": ["https://example.com"],
            "headlines": [
                "Demo Brand Official Site",
                "Free Shipping Today",
                "Shop New Arrivals",
            ],
            "descriptions": [
                "Discover the latest collection with fast delivery.",
                "Trusted by 50k+ customers. Shop now.",
            ],
            "headline_count": 3,
            "description_count": 2,
        },
        {
            "campaign": "Search — Non-Brand",
            "ad_group": "Running",
            "campaign_id": "1",
            "ad_group_id": "11",
            "ad_id": "502",
            "name": "RSA — Generic Weak",
            "type": "RESPONSIVE_SEARCH_AD",
            "status": "ENABLED",
            "ad_strength": "POOR",
            "action_items": [
                "Add more unique headlines",
                "Include popular keywords in your headlines",
                "Try unpinning some assets",
            ],
            "needs_improvement": True,
            "final_urls": ["https://example.com/running"],
            "headlines": ["Running Shoes Sale", "Best Price Online", "Order Today"],
            "descriptions": [
                "Browse running shoes for every terrain.",
                "Limited-time offers on top models.",
            ],
            "headline_count": 3,
            "description_count": 2,
        },
    ]


def demo_trend(days: int = 30) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    start = date.today() - timedelta(days=days - 1)
    for i in range(days):
        d = start + timedelta(days=i)
        cost = 280 + (i % 7) * 35 + (i % 3) * 12
        conversions = 8 + (i % 5) * 2
        value = conversions * 62
        clicks = 180 + (i % 6) * 20
        impressions = clicks * 18
        out.append(
            {
                "date": d.isoformat(),
                "impressions": impressions,
                "clicks": clicks,
                "cost": float(cost),
                "conversions": float(conversions),
                "conversions_value": float(value),
                "roas": round(value / cost, 2),
            }
        )
    return out


def demo_recommendations() -> list[dict[str, Any]]:
    recs = [
        Recommendation(
            action=ActionType.PAUSE_KEYWORD,
            severity=Severity.HIGH,
            entity_type="keyword",
            entity_id="free shoes pdf",
            entity_name="free shoes pdf",
            reason="Spend 380.00 with 410 clicks and 0 conversions.",
            metrics={"cost": 380, "clicks": 410, "conversions": 0},
            campaign_id="102",
            ad_group_id="1",
        ),
        Recommendation(
            action=ActionType.ADD_NEGATIVE,
            severity=Severity.HIGH,
            entity_type="search_term",
            entity_id="cheap knockoff shoes",
            entity_name="cheap knockoff shoes",
            reason="Wasted spend on irrelevant query with 0 conversions.",
            metrics={"cost": 95, "clicks": 40, "conversions": 0},
            campaign_id="102",
        ),
        Recommendation(
            action=ActionType.LOWER_BID,
            severity=Severity.MEDIUM,
            entity_type="keyword",
            entity_id="buy running shoes",
            entity_name="buy running shoes",
            reason="CPA 32.86 exceeds target — suggest -20% bid.",
            metrics={"cpa": 32.86, "roas": 2.28},
            campaign_id="102",
        ),
        Recommendation(
            action=ActionType.RAISE_BID,
            severity=Severity.LOW,
            entity_type="keyword",
            entity_id="demo brand official",
            entity_name="demo brand official",
            reason="Strong ROAS 13.57 — suggest +15% bid.",
            metrics={"roas": 13.57, "cpa": 4.42},
            campaign_id="101",
        ),
    ]
    return [
        {
            "action": r.action.value,
            "severity": r.severity.value,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "entity_name": r.entity_name,
            "reason": r.reason,
            "metrics": r.metrics,
            "campaign_id": r.campaign_id,
            "ad_group_id": r.ad_group_id,
        }
        for r in recs
    ]


def demo_overview(days: int = 30) -> dict[str, Any]:
    camps = demo_campaigns()
    trend = demo_trend(days)
    totals = {
        "impressions": sum(c["impressions"] for c in camps),
        "clicks": sum(c["clicks"] for c in camps),
        "cost": round(sum(c["cost"] for c in camps), 2),
        "conversions": round(sum(c["conversions"] for c in camps), 2),
        "conversions_value": round(sum(c["conversions_value"] for c in camps), 2),
    }
    totals["ctr"] = round(totals["clicks"] / totals["impressions"], 4) if totals["impressions"] else 0
    totals["cpa"] = (
        round(totals["cost"] / totals["conversions"], 2) if totals["conversions"] else 0
    )
    totals["roas"] = (
        round(totals["conversions_value"] / totals["cost"], 2) if totals["cost"] else 0
    )
    from ads_optimizer.setup_guide import setup_payload

    return {
        "account": demo_account_meta(),
        "days": days,
        "totals": totals,
        "trend": trend,
        "campaigns": camps,
        "recommendations": demo_recommendations(),
        "setup": setup_payload(),
    }
