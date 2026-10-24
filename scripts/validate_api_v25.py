"""Validate GAQL + mutate field compatibility with Google Ads API v25."""

from __future__ import annotations

from ads_optimizer.config import load_settings
from ads_optimizer.client import build_client
from ads_optimizer.dates import date_range_clause
from ads_optimizer.service import AdsService, reset_service_cache


def main() -> None:
    settings = load_settings()
    client = build_client(settings=settings)
    reset_service_cache()
    svc = AdsService(settings)
    cid = svc.customer_id
    print("customer", cid, svc.status().get("account_name"))

    days = 7
    queries = {
        "campaigns": f"""
            SELECT campaign.id, campaign.name, campaign.status,
                   campaign.advertising_channel_type, campaign_budget.amount_micros,
                   metrics.impressions, metrics.clicks, metrics.cost_micros,
                   metrics.conversions, metrics.conversions_value, metrics.ctr,
                   metrics.average_cpc
            FROM campaign
            WHERE {date_range_clause(days)} AND campaign.status != 'REMOVED'
            LIMIT 5
        """,
        "keywords": f"""
            SELECT campaign.id, ad_group.id, ad_group_criterion.criterion_id,
                   ad_group_criterion.keyword.text, ad_group_criterion.status,
                   ad_group_criterion.effective_cpc_bid_micros,
                   metrics.impressions, metrics.clicks, metrics.cost_micros,
                   metrics.conversions, metrics.ctr
            FROM keyword_view
            WHERE {date_range_clause(days)}
              AND campaign.status != 'REMOVED'
              AND ad_group_criterion.status != 'REMOVED'
            LIMIT 5
        """,
        "search_terms": f"""
            SELECT campaign.id, ad_group.id, search_term_view.search_term,
                   search_term_view.status, metrics.impressions, metrics.clicks,
                   metrics.cost_micros, metrics.conversions
            FROM search_term_view
            WHERE {date_range_clause(days)} AND campaign.status != 'REMOVED'
            LIMIT 5
        """,
        "ads": f"""
            SELECT campaign.id, ad_group.id, ad_group_ad.ad.id, ad_group_ad.status,
                   metrics.impressions, metrics.clicks, metrics.cost_micros,
                   metrics.conversions, metrics.ctr
            FROM ad_group_ad
            WHERE {date_range_clause(days)}
              AND campaign.status != 'REMOVED'
              AND ad_group_ad.status != 'REMOVED'
            LIMIT 5
        """,
        "creatives": """
            SELECT campaign.name, ad_group.name, ad_group_ad.ad.id,
                   ad_group_ad.ad.type, ad_group_ad.status,
                   ad_group_ad.ad.final_urls,
                   ad_group_ad.ad.responsive_search_ad.headlines,
                   ad_group_ad.ad.responsive_search_ad.descriptions
            FROM ad_group_ad
            WHERE campaign.status != 'REMOVED' AND ad_group_ad.status != 'REMOVED'
            LIMIT 5
        """,
        "daily": f"""
            SELECT segments.date, metrics.impressions, metrics.clicks,
                   metrics.cost_micros, metrics.conversions, metrics.conversions_value
            FROM customer
            WHERE {date_range_clause(days)}
            ORDER BY segments.date
        """,
        "budget_lookup": """
            SELECT campaign.id, campaign.campaign_budget
            FROM campaign
            WHERE campaign.status != 'REMOVED'
            LIMIT 3
        """,
    }

    ga_service = client.get_service("GoogleAdsService")
    for name, query in queries.items():
        try:
            rows = list(ga_service.search(customer_id=cid, query=query))
            print(f"OK  GAQL {name:14} rows={len(rows)}")
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            short = next((ln for ln in msg.splitlines() if "message:" in ln), msg[:200])
            print(f"FAIL GAQL {name:14} {short}")

    # Field mask pattern
    op = client.get_type("CampaignOperation")
    op.update.resource_name = client.get_service("CampaignService").campaign_path(cid, "1")
    op.update.status = client.enums.CampaignStatusEnum.PAUSED
    op.update_mask.paths.append("status")
    print("OK  update_mask.paths", list(op.update_mask.paths))

    # Bidding oneofs
    camp = client.get_type("Campaign")
    assert not hasattr(camp, "start_date")
    assert hasattr(camp, "start_date_time")
    client.copy_from(camp.target_spend, client.get_type("TargetSpend"))
    print("OK  target_spend empty (Maximize Clicks)")
    camp2 = client.get_type("Campaign")
    camp2.manual_cpc.enhanced_cpc_enabled = False
    print("OK  manual_cpc.enhanced_cpc_enabled")
    camp3 = client.get_type("Campaign")
    client.copy_from(camp3.maximize_conversions, client.get_type("MaximizeConversions"))
    print("OK  maximize_conversions")

    print("DONE")


if __name__ == "__main__":
    main()
