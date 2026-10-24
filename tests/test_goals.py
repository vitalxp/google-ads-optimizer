from ads_optimizer.analytics import create_conversion_event, create_google_ads_link, status
from ads_optimizer.chat_agent import TOOLS, ChatAgent
from ads_optimizer.goals import (
    create_custom_conversion_goal,
    set_campaign_goal_config,
    set_conversion_action_primary,
)
from ads_optimizer.knowledge_base import get_article, load_articles


def test_goal_and_ga_tools_registered() -> None:
    names = {t["function"]["name"] for t in TOOLS}
    assert "get_conversion_goals" in names
    assert "set_conversion_action_primary" in names
    assert "set_campaign_conversion_goal" in names
    assert "create_custom_conversion_goal" in names
    assert "set_conversion_action_value" in names
    assert "get_customer_tracking" in names
    assert "set_customer_auto_tagging" in names
    assert "ga_overview" in names
    assert "ga_list_properties" in names
    assert "ga_create_conversion_event" in names
    assert "ga_delete_conversion_event" in names
    assert "ga_create_google_ads_link" in names


def test_conversion_action_value_preview() -> None:
    from ads_optimizer.goals import set_conversion_action_value

    class _Dummy:
        pass

    result = set_conversion_action_value(
        _Dummy(),  # type: ignore[arg-type]
        "1234567890",
        conversion_action_id="99",
        default_value=0,
        always_use_default_value=True,
        default_currency_code="PLN",
        confirm=False,
    )
    assert result["needs_confirmation"] is True
    assert result["preview"]["action"] == "set_conversion_action_value"


def test_ga_delete_conversion_event_preview() -> None:
    from ads_optimizer.analytics import delete_conversion_event

    # Force path that skips live list: resource_name provided
    result = delete_conversion_event(
        resource_name="properties/1/conversionEvents/2",
        event_name="page_view",
        property_id="538015447",
        confirm=False,
    )
    assert result["needs_confirmation"] is True
    assert result["preview"]["action"] == "ga_delete_conversion_event"


def test_conversion_action_primary_preview_only() -> None:
    class _Dummy:
        pass

    result = set_conversion_action_primary(
        _Dummy(),  # type: ignore[arg-type]
        "1234567890",
        conversion_action_id="99",
        primary_for_goal=False,
        confirm=False,
    )
    assert result["needs_confirmation"] is True
    assert result["preview"]["primary_for_goal"] is False


def test_campaign_goal_config_preview_only() -> None:
    class _Dummy:
        pass

    result = set_campaign_goal_config(
        _Dummy(),  # type: ignore[arg-type]
        "1234567890",
        campaign_id="111",
        goal_config_level="CUSTOMER",
        confirm=False,
    )
    assert result["needs_confirmation"] is True
    assert result["preview"]["goal_config_level"] == "CUSTOMER"


def test_custom_conversion_goal_preview_only() -> None:
    class _Dummy:
        pass

    result = create_custom_conversion_goal(
        _Dummy(),  # type: ignore[arg-type]
        "1234567890",
        name="Leads only",
        conversion_action_ids=["10", "20"],
        campaign_id="111",
        confirm=False,
    )
    assert result["needs_confirmation"] is True
    assert result["preview"]["conversion_action_ids"] == ["10", "20"]


def test_ga_mutate_preview_only() -> None:
    preview = create_conversion_event(
        event_name="generate_lead",
        property_id="123456789",
        confirm=False,
    )
    assert preview["needs_confirmation"] is True
    assert preview["preview"]["event_name"] == "generate_lead"

    link = create_google_ads_link(
        customer_id="1234567890",
        property_id="123456789",
        confirm=False,
    )
    assert link["needs_confirmation"] is True
    assert link["preview"]["customer_id"] == "123-456-7890"


def test_analytics_status_shape() -> None:
    st = status()
    assert "configured" in st
    assert "property_id" in st
    assert "property_configured" in st
    assert "needs_scope" in st


def test_agent_conversion_goals_demo() -> None:
    agent = ChatAgent()
    out = agent.run_tool("get_conversion_goals", {})
    assert "conversion_actions" in out


def test_knowledge_has_goals_and_analytics() -> None:
    ids = {a.id for a in load_articles()}
    assert "conversion-goals" in ids
    assert "google-analytics" in ids
    article = get_article("conversion-goals")
    assert article is not None
    assert "set_conversion_action_primary" in article.body
