from __future__ import annotations

from ads_optimizer.analyzer import analyze
from ads_optimizer.config import Settings
from ads_optimizer.models import AccountSnapshot, ActionType, Severity


def _settings(**overrides) -> Settings:
    data = {
        "google_ads_customer_id": "1234567890",
        "lookback_days": 30,
        "min_clicks": 20,
        "min_impressions": 100,
        "max_cpa": 30.0,
        "min_roas": 2.0,
        "min_ctr": 0.02,
        "waste_spend": 10.0,
    }
    data.update(overrides)
    return Settings(_env_file=None, **data)


def test_pauses_zero_conversion_keywords() -> None:
    snapshot = AccountSnapshot(
        campaigns=[],
        keywords=[
            {
                "campaign_id": "1",
                "campaign_status": "ENABLED",
                "bidding_strategy_type": "MANUAL_CPC",
                "channel": "SEARCH",
                "ad_group_id": "2",
                "criterion_id": "3",
                "text": "cheap junk",
                "status": "ENABLED",
                "bid": 1.0,
                "impressions": 1000,
                "clicks": 50,
                "cost": 40.0,
                "conversions": 0,
                "conversions_value": 0,
                "ctr": 0.05,
                "cpa": 0,
                "roas": 0,
                "quality_score": 5,
            }
        ],
        search_terms=[],
        ads=[],
    )
    recs = analyze(snapshot, _settings())
    assert any(r.action == ActionType.PAUSE_KEYWORD and r.severity == Severity.HIGH for r in recs)


def test_adds_negative_for_wasted_search_term() -> None:
    snapshot = AccountSnapshot(
        campaigns=[],
        keywords=[],
        search_terms=[
            {
                "campaign_id": "1",
                "campaign_status": "ENABLED",
                "ad_group_id": "2",
                "search_term": "free pdf",
                "status": "NONE",
                "impressions": 200,
                "clicks": 10,
                "cost": 25.0,
                "conversions": 0,
                "conversions_value": 0,
                "cpa": 0,
                "roas": 0,
                "ctr": 0.05,
            }
        ],
        ads=[],
    )
    recs = analyze(snapshot, _settings())
    assert any(r.action == ActionType.ADD_NEGATIVE for r in recs)


def test_skips_paused_campaign_without_traffic() -> None:
    snapshot = AccountSnapshot(
        campaigns=[],
        keywords=[
            {
                "campaign_id": "1",
                "campaign_status": "PAUSED",
                "bidding_strategy_type": "MAXIMIZE_CONVERSIONS",
                "channel": "SEARCH",
                "ad_group_id": "2",
                "criterion_id": "3",
                "text": "idle kw",
                "status": "ENABLED",
                "bid": 0.01,
                "impressions": 0,
                "clicks": 0,
                "cost": 0.0,
                "conversions": 0,
                "conversions_value": 0,
                "ctr": 0,
                "cpa": 0,
                "roas": 0,
                "quality_score": 0,
            }
        ],
        search_terms=[],
        ads=[],
    )
    recs = analyze(snapshot, _settings())
    assert recs == []


def test_includes_paused_campaign_with_spend() -> None:
    snapshot = AccountSnapshot(
        campaigns=[],
        keywords=[
            {
                "campaign_id": "1",
                "campaign_status": "PAUSED",
                "campaign_name": "Leads PL",
                "bidding_strategy_type": "MAXIMIZE_CONVERSIONS",
                "channel": "SEARCH",
                "ad_group_id": "2",
                "criterion_id": "3",
                "text": "transfer gdańsk lotnisko",
                "status": "ENABLED",
                "bid": 0.01,
                "impressions": 675,
                "clicks": 112,
                "cost": 273.0,
                "conversions": 2,
                "conversions_value": 0,
                "ctr": 0.16,
                "cpa": 136.5,
                "roas": 0,
                "quality_score": 0,
            }
        ],
        search_terms=[],
        ads=[],
    )
    recs = analyze(snapshot, _settings(max_cpa=50.0, min_clicks=50))
    assert any(r.action == ActionType.PAUSE_KEYWORD for r in recs)
    assert any("paused campaign" in r.reason.lower() for r in recs)


def test_smart_bidding_high_cpa_suggests_pause_not_lower_bid() -> None:
    snapshot = AccountSnapshot(
        campaigns=[],
        keywords=[
            {
                "campaign_id": "1",
                "campaign_status": "ENABLED",
                "bidding_strategy_type": "MAXIMIZE_CONVERSIONS",
                "channel": "SEARCH",
                "ad_group_id": "2",
                "criterion_id": "3",
                "text": "expensive kw",
                "status": "ENABLED",
                "bid": 0.01,
                "impressions": 675,
                "clicks": 112,
                "cost": 273.0,
                "conversions": 2,
                "conversions_value": 0,
                "ctr": 0.16,
                "cpa": 136.5,
                "roas": 0,
                "quality_score": 7,
            }
        ],
        search_terms=[],
        ads=[],
    )
    recs = analyze(snapshot, _settings(max_cpa=50.0, min_clicks=50))
    assert any(r.action == ActionType.PAUSE_KEYWORD for r in recs)
    assert not any(r.action == ActionType.LOWER_BID for r in recs)


def test_waste_by_spend_without_min_clicks() -> None:
    snapshot = AccountSnapshot(
        campaigns=[],
        keywords=[
            {
                "campaign_id": "1",
                "campaign_status": "ENABLED",
                "bidding_strategy_type": "MANUAL_CPC",
                "channel": "SEARCH",
                "ad_group_id": "2",
                "criterion_id": "9",
                "text": "transfery z lotniska",
                "status": "ENABLED",
                "bid": 1.0,
                "impressions": 200,
                "clicks": 33,
                "cost": 104.0,
                "conversions": 0,
                "conversions_value": 0,
                "ctr": 0.16,
                "cpa": 0,
                "roas": 0,
                "quality_score": 0,
            }
        ],
        search_terms=[],
        ads=[],
    )
    # min_clicks=50 would miss this under old rules; waste_spend*2=20 with 33 clicks
    recs = analyze(snapshot, _settings(min_clicks=50, waste_spend=20.0))
    assert any(r.action == ActionType.PAUSE_KEYWORD for r in recs)


def test_quality_score_review() -> None:
    snapshot = AccountSnapshot(
        campaigns=[],
        keywords=[
            {
                "campaign_id": "1",
                "campaign_status": "ENABLED",
                "bidding_strategy_type": "MANUAL_CPC",
                "channel": "SEARCH",
                "ad_group_id": "2",
                "criterion_id": "4",
                "text": "low qs",
                "status": "ENABLED",
                "bid": 1.0,
                "impressions": 500,
                "clicks": 40,
                "cost": 15.0,
                "conversions": 1,
                "conversions_value": 40,
                "ctr": 0.08,
                "cpa": 15.0,
                "roas": 2.6,
                "quality_score": 3,
            }
        ],
        search_terms=[],
        ads=[],
    )
    recs = analyze(snapshot, _settings(min_clicks=20, max_cpa=50.0))
    assert any(
        r.action == ActionType.REVIEW_CAMPAIGN and "Quality Score 3" in r.reason
        for r in recs
    )


def test_improve_rsa_and_empty_group() -> None:
    snapshot = AccountSnapshot(
        campaigns=[],
        keywords=[],
        search_terms=[],
        ads=[
            {
                "campaign_id": "1",
                "campaign_status": "ENABLED",
                "ad_group_id": "2",
                "ad_id": "10",
                "name": "RSA weak",
                "status": "ENABLED",
                "ad_strength": "POOR",
                "approval_status": "APPROVED",
                "impressions": 10,
                "clicks": 1,
                "cost": 2.0,
                "conversions": 0,
                "conversions_value": 0,
                "ctr": 0.1,
                "cpa": 0,
                "roas": 0,
            }
        ],
        ad_groups=[
            {
                "campaign_id": "1",
                "campaign_status": "ENABLED",
                "channel": "SEARCH",
                "ad_group_id": "99",
                "ad_group_name": "Empty Group",
                "status": "ENABLED",
                "ads_count": 0,
                "empty_ad_group": True,
            }
        ],
    )
    recs = analyze(snapshot, _settings())
    assert any(r.action == ActionType.IMPROVE_RSA for r in recs)
    assert any(r.action == ActionType.FILL_AD_GROUP for r in recs)


def test_tracking_too_many_in_metric() -> None:
    snapshot = AccountSnapshot(
        campaigns=[],
        keywords=[],
        search_terms=[],
        ads=[],
        conversion_actions=[
            {
                "id": str(i),
                "name": f"ev{i}",
                "status": "ENABLED",
                "primary_for_goal": i < 2,
                "include_in_conversions_metric": True,
            }
            for i in range(10)
        ],
    )
    recs = analyze(snapshot, _settings())
    assert any(r.action == ActionType.REVIEW_TRACKING for r in recs)
