from ads_optimizer.keyword_planner import resolve_language, resolve_locations
from ads_optimizer.chat_agent import TOOLS


def test_resolve_locations_country_codes() -> None:
    assert resolve_locations(["PL", "US"]) == ["2616", "2840"]


def test_resolve_language() -> None:
    assert resolve_language("pl") == "1030"
    assert resolve_language("en") == "1000"


def test_keyword_ideas_tool_registered() -> None:
    names = {t["function"]["name"] for t in TOOLS}
    assert "generate_keyword_ideas" in names
