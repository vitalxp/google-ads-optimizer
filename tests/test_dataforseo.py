from ads_optimizer.chat_agent import TOOLS
from ads_optimizer.dataforseo import DataForSeoClient, LOCATION_CODES


def test_location_resolve() -> None:
    assert DataForSeoClient.resolve_location("PL") == LOCATION_CODES["PL"]
    assert DataForSeoClient.resolve_location("2840") == 2840


def test_dataforseo_tools_registered() -> None:
    names = {t["function"]["name"] for t in TOOLS}
    assert "dataforseo_keywords_for_keywords" in names
    assert "dataforseo_search_volume" in names
    assert "dataforseo_keywords_for_site" in names
