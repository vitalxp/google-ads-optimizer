import inspect

from ads_optimizer.assets import add_callouts, add_sitelinks, add_structured_snippet, set_campaign_asset_status
from ads_optimizer.chat_agent import TOOLS, ChatAgent


def test_asset_tools_registered() -> None:
    names = {t["function"]["name"] for t in TOOLS}
    assert "get_campaign_assets" in names
    assert "add_sitelinks" in names
    assert "add_callouts" in names
    assert "add_structured_snippet" in names
    assert "set_campaign_asset_status" in names
    assert "sync_campaign_sitelinks" in names


def test_add_sitelinks_preview_only() -> None:
    class _Dummy:
        pass

    result = add_sitelinks(
        _Dummy(),  # type: ignore[arg-type]
        "1234567890",
        campaign_id="111",
        sitelinks=[
            {
                "link_text": "Kontakt",
                "final_url": "https://example.com/kontakt",
                "description1": "Napisz do nas",
                "description2": "Odpowiadamy szybko",
            }
        ],
        confirm=False,
    )
    assert result["needs_confirmation"] is True
    assert result["preview"]["count"] == 1
    assert result["preview"]["sitelinks"][0]["link_text"] == "Kontakt"


def test_add_callouts_preview_only() -> None:
    class _Dummy:
        pass

    result = add_callouts(
        _Dummy(),  # type: ignore[arg-type]
        "1234567890",
        campaign_id="111",
        callouts=["24/7 support", "Free shipping"],
        confirm=False,
    )
    assert result["needs_confirmation"] is True
    assert result["preview"]["count"] == 2


def test_structured_snippet_preview_only() -> None:
    class _Dummy:
        pass

    result = add_structured_snippet(
        _Dummy(),  # type: ignore[arg-type]
        "1234567890",
        campaign_id="111",
        header="Services",
        values=["Delivery", "Installation", "Support"],
        confirm=False,
    )
    assert result["needs_confirmation"] is True
    assert result["preview"]["header"] == "Services"


def test_agent_lists_assets_demo_or_live() -> None:
    agent = ChatAgent()
    out = agent.run_tool("get_campaign_assets", {"limit": 5})
    assert "items" in out


def test_unlink_defaults_to_paused() -> None:
    params = inspect.signature(set_campaign_asset_status).parameters
    assert params["status"].default == "PAUSED"


def test_removed_mapped_to_paused_in_preview() -> None:
    class _Dummy:
        pass

    result = set_campaign_asset_status(
        _Dummy(),  # type: ignore[arg-type]
        "1234567890",
        campaign_asset_resource_names=["customers/1234567890/campaignAssets/1~2"],
        status="REMOVED",
        confirm=False,
    )
    assert result["needs_confirmation"] is True
    assert result["preview"]["status"] == "PAUSED"
