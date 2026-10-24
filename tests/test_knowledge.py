from ads_optimizer.chat_agent import TOOLS, ChatAgent
from ads_optimizer.knowledge_base import get_article, list_catalog, load_articles, search_knowledge


def test_knowledge_articles_loaded() -> None:
    articles = load_articles()
    assert len(articles) >= 10
    ids = {a.id for a in articles}
    assert "bidding-strategies" in ids
    assert "search-campaign-launch" in ids
    assert "agent-operating-rules" in ids


def test_search_knowledge_ranks_relevant() -> None:
    results = search_knowledge("ставки tCPA обучение", limit=3)
    assert results
    assert any(r["id"] == "bidding-strategies" for r in results)


def test_get_knowledge_full_body() -> None:
    article = get_article("keywords-match-negatives")
    assert article is not None
    assert "Exact" in article.body
    assert "Broad" in article.body


def test_knowledge_tools_on_agent() -> None:
    names = {t["function"]["name"] for t in TOOLS}
    assert "search_knowledge" in names
    assert "get_knowledge" in names
    assert "list_knowledge" in names

    agent = ChatAgent()
    listed = agent.run_tool("list_knowledge", {})
    assert len(listed["articles"]) >= 8
    found = agent.run_tool("search_knowledge", {"query": "RSA заголовки", "limit": 3})
    assert found["results"]
    full = agent.run_tool("get_knowledge", {"id": found["results"][0]["id"]})
    assert "body" in full
    assert full["id"]


def test_catalog_excludes_index_page() -> None:
    ids = {row["id"] for row in list_catalog()}
    assert "index" not in ids
