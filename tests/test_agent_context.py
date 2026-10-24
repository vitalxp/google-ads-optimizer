import json

from ads_optimizer.agent_context import (
    CORE_TOOLS,
    detect_tool_groups,
    filter_tools,
    selected_tool_names,
    slim_tool_result,
    trim_messages_for_llm,
)
from ads_optimizer.chat_agent import TOOLS, _compact_tool_result


def test_compact_creatives_full_text_when_filtered() -> None:
    payload = {
        "items": [
            {
                "ad_id": "820826832453",
                "ad_group_id": "202287916987",
                "campaign": "Fleet",
                "ad_group": "Ford Tourneo Minivan 7 Miejsc",
                "status": "ENABLED",
                "headlines": [f"H{i} 8 miejsc" for i in range(15)],
                "descriptions": [
                    "D0 do 8 osób",
                    "D1 ok",
                    "D2 ok",
                    "D3 ok",
                ],
                "final_urls": ["https://example.com"],
            }
        ],
        "filters": {"ad_group_id": "202287916987"},
        "full_text": True,
        "total": 1,
    }
    out = _compact_tool_result("get_creatives", payload)
    assert out["full_text"] is True
    row = out["items"][0]
    assert row["ad_id"] == "820826832453"
    assert len(row["headlines"]) == 15
    assert len(row["descriptions"]) == 4
    assert "headlines_sample" not in row


def test_slim_ads_keeps_empty_groups() -> None:
    items = [
        {
            "ad_id": str(i),
            "ad_group_id": str(100 + i),
            "campaign": "C",
            "ad_group": f"G{i}",
            "status": "ENABLED",
            "cost": float(i),
            "empty_ad_group": False,
        }
        for i in range(40)
    ]
    items.append(
        {
            "ad_id": "",
            "ad_group_id": "204438742452",
            "campaign": "Search | PL | Routes — Kurorty",
            "ad_group": "Gdańsk–Ustka",
            "status": "NO_AD",
            "cost": 0,
            "empty_ad_group": True,
            "name": "(нет объявления)",
        }
    )
    slim = slim_tool_result("get_ads", {"items": items})
    assert any(r.get("ad_group_id") == "204438742452" for r in slim["items"])
    assert slim["empty_ad_groups"] == 1


def test_detect_groups_assets_and_goals() -> None:
    assert "assets" in detect_tool_groups("Добавь sitelinks на кампанию")
    assert "goals" in detect_tool_groups("Покажи primary conversion goals")
    assert "analytics" in detect_tool_groups("GA4 статистика каналов")
    assert "campaign_mutate" in detect_tool_groups("смени bidding на maximize clicks")


def test_confirm_expands_mutate_groups() -> None:
    groups = detect_tool_groups("да, подтверждаю")
    assert "assets" in groups
    assert "goals" in groups
    assert "campaign_mutate" in groups


def test_filter_tools_smaller_than_full() -> None:
    msgs = [{"role": "user", "content": "Сделай обзор аккаунта"}]
    subset = filter_tools(TOOLS, msgs)
    names = {(t.get("function") or {}).get("name") for t in subset}
    assert CORE_TOOLS <= names
    assert len(subset) < len(TOOLS)
    assert "add_sitelinks" not in names
    assert "ga_overview" not in names


def test_filter_tools_includes_assets_when_needed() -> None:
    msgs = [{"role": "user", "content": "Добавь sitelinks и callouts"}]
    names = selected_tool_names(msgs)
    assert "add_sitelinks" in names
    assert "add_callouts" in names
    assert "get_campaign_assets" in names


def test_used_tools_expand_groups() -> None:
    msgs = [{"role": "user", "content": "обзор"}]
    names = selected_tool_names(msgs, used_tools={"add_sitelinks"})
    assert "add_sitelinks" in names
    assert "get_campaign_assets" in names


def test_trim_messages_compresses_older() -> None:
    messages = []
    for i in range(20):
        messages.append({"role": "user", "content": f"q{i} " + ("x" * 50)})
        messages.append({"role": "assistant", "content": f"a{i}"})
    trimmed = trim_messages_for_llm(messages, keep_recent=6)
    assert len(trimmed) < len(messages)
    assert "compressed" in trimmed[0]["content"].lower()
    assert trimmed[-1]["content"].startswith("a")


def test_slim_campaigns_and_goals() -> None:
    camps = {
        "items": [
            {"id": str(i), "name": f"c{i}", "cost": float(i), "status": "ENABLED"}
            for i in range(40)
        ]
    }
    slim = slim_tool_result("get_campaigns", camps)
    assert slim["truncated"] is True
    assert len(slim["items"]) == 25
    assert slim["items"][0]["id"] == "39"

    goals = {
        "conversion_actions": [{"id": str(i), "name": f"a{i}", "extra": "drop"} for i in range(5)],
        "customer_goals": [],
        "campaign_goals": [],
        "campaign_goal_configs": [],
        "custom_goals": [],
    }
    g = slim_tool_result("get_conversion_goals", goals)
    assert "extra" not in g["conversion_actions"][0]
    assert g["conversion_actions"][0]["name"] == "a0"


def test_slim_gaql_rows() -> None:
    payload = {
        "rows": [{"campaign": {"name": "x"}, "metrics": {"clicks": i}} for i in range(40)]
    }
    slim = slim_tool_result("run_gaql", payload)
    assert slim["truncated"] is True
    assert len(slim["rows"]) == 25


def test_tools_json_still_complete() -> None:
    names = {t["function"]["name"] for t in TOOLS}
    assert len(names) >= 50
    # routing must not drop schema definitions from registry
    assert json.dumps(TOOLS)
