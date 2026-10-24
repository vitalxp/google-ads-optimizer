from ads_optimizer.campaign_ops import add_negative_keywords
from ads_optimizer.chat_agent import TOOLS, ChatAgent


def test_negative_tools_registered() -> None:
    names = {t["function"]["name"] for t in TOOLS}
    assert "add_negative_keywords" in names
    assert "get_negative_keywords" in names
    assert "set_keyword_status" in names
    assert "set_ad_status" in names
    assert "update_campaign_bidding" in names
    assert "rename_ad_group" in names


def test_rename_ad_group_preview() -> None:
    from ads_optimizer.campaign_ops import rename_ad_group

    class _Dummy:
        pass

    result = rename_ad_group(
        _Dummy(),  # type: ignore[arg-type]
        "1234567890",
        ad_group_id="204438742452",
        name="Gdańsk–Ustka (new)",
        confirm=False,
    )
    assert result["needs_confirmation"] is True
    assert result["preview"]["action"] == "rename_ad_group"
    assert result["preview"]["ad_group_id"] == "204438742452"
    assert result["preview"]["name"] == "Gdańsk–Ustka (new)"


def test_create_ad_group_with_rsa_preview() -> None:
    from ads_optimizer.campaign_ops import create_ad_group_with_rsa

    class _Dummy:
        pass

    result = create_ad_group_with_rsa(
        _Dummy(),  # type: ignore[arg-type]
        "1234567890",
        campaign_id="111",
        ad_group_name="Gdańsk–Władysławowo",
        final_url="https://example.com/transfer",
        headlines=["H1", "H2", "H3"],
        descriptions=["D1 long enough", "D2 long enough"],
        keywords=[{"text": "transfer gdansk", "match_type": "PHRASE"}],
        confirm=False,
    )
    assert result["needs_confirmation"] is True
    assert result["preview"]["action"] == "create_ad_group_with_rsa"
    assert result["preview"]["ad_group_name"] == "Gdańsk–Władysławowo"


def test_create_ad_group_with_rsa_tool_registered() -> None:
    names = {t["function"]["name"] for t in TOOLS}
    assert "create_ad_group_with_rsa" in names


def test_set_ad_status_preview() -> None:
    from ads_optimizer.campaign_ops import set_ad_status

    class _Dummy:
        pass

    result = set_ad_status(
        _Dummy(),  # type: ignore[arg-type]
        "123",
        ads=[{"ad_group_id": "10", "ad_id": "20", "name": "RSA"}],
        status="PAUSED",
        confirm=False,
    )
    assert result["needs_confirmation"] is True
    assert result["preview"]["count"] == 1
    assert result["preview"]["status"] == "PAUSED"


def test_update_campaign_bidding_preview() -> None:
    from ads_optimizer.campaign_ops import update_campaign_bidding

    class _Dummy:
        pass

    result = update_campaign_bidding(
        _Dummy(),  # type: ignore[arg-type]
        "123",
        campaign_id="999",
        bidding="maximize_conversions",
        target_cpa=45.0,
        confirm=False,
    )
    assert result["needs_confirmation"] is True
    assert result["preview"]["bidding"] == "maximize_conversions"
    assert result["preview"]["target_cpa"] == 45.0


def test_apply_bidding_maximize_clicks_leaf_mask() -> None:
    """Updates must use leaf field mask, not parent target_spend."""
    from ads_optimizer.campaign_ops import apply_bidding_scheme
    from tests.helpers import dummy_ads_client

    client = dummy_ads_client()
    operation = client.get_type("CampaignOperation")
    campaign = operation.update
    mask = apply_bidding_scheme(client, campaign, bidding="maximize_clicks")
    assert mask == "target_spend.cpc_bid_ceiling_micros"
    mask2 = apply_bidding_scheme(
        client, campaign, bidding="maximize_clicks", cpc_bid_ceiling=2.5
    )
    assert mask2 == "target_spend.cpc_bid_ceiling_micros"
    assert campaign.target_spend.cpc_bid_ceiling_micros == 2_500_000
    mask3 = apply_bidding_scheme(client, campaign, bidding="maximize_conversions")
    assert mask3 == "maximize_conversions.target_cpa_micros"


def test_add_negative_keywords_preview_only() -> None:
    class _Dummy:
        pass

    result = add_negative_keywords(
        _Dummy(),  # type: ignore[arg-type]
        "123",
        campaign_id="999",
        negatives=[{"text": "free", "match_type": "EXACT"}],
        confirm=False,
    )
    assert result["needs_confirmation"] is True
    assert result["preview"]["count"] == 1
    assert result["preview"]["level"] == "campaign"


def test_agent_runs_negative_list_demo() -> None:
    agent = ChatAgent()
    # May be live or demo depending on env; tool must not crash
    out = agent.run_tool("get_negative_keywords", {"limit": 5})
    assert "items" in out
