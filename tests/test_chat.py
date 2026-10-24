from ads_optimizer.chat_agent import ChatAgent, TOOLS
from ads_optimizer.openrouter import CURATED_TOP20, OpenRouterClient, OpenRouterSettings


def test_tools_registered() -> None:
    names = {t["function"]["name"] for t in TOOLS}
    assert "get_overview" in names
    assert "confirm_pending_mutation" in names
    assert "get_search_terms" in names
    assert "apply_optimizations" in names
    assert "run_gaql" in names
    assert "search_knowledge" in names
    assert "get_knowledge" in names


def test_chat_agent_tools_demo() -> None:
    agent = ChatAgent()
    status = agent.run_tool("get_status", {})
    assert status["mode"] in {"demo", "live"}
    overview = agent.run_tool("get_overview", {"days": 7})
    assert "totals" in overview


def test_curated_top20() -> None:
    assert len(CURATED_TOP20) == 20
    client = OpenRouterClient(OpenRouterSettings(openrouter_api_key=""))
    models = client.list_top_models(20)
    assert len(models) == 20
    assert "id" in models[0]
