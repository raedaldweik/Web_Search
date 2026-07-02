"""Tool behaviour tests. The Tavily network layer is stubbed so these run
offline. Tools are registered on a fake MCP that just records the functions."""

import pytest

from news_mcp_server import tools as tools_mod


class FakeMCP:
    """Captures functions registered via @mcp.tool() so we can call them."""

    def __init__(self):
        self.funcs = {}

    def tool(self):
        def deco(fn):
            self.funcs[fn.__name__] = fn
            return fn
        return deco


@pytest.fixture
def registered():
    mcp = FakeMCP()
    tools_mod.register_tools(mcp)
    return mcp.funcs


SAMPLE = {
    "answer": "an answer",
    "results": [
        {"title": "T1", "url": "https://reuters.com/a", "content": "c1",
         "published_date": "2026-06-27", "score": 0.9},
        {"title": "T2", "url": "https://gov.ae/b", "content": "c2",
         "published_date": "2026-06-28", "score": 0.8},
    ],
}


@pytest.mark.asyncio
async def test_search_news_shapes_results(registered, monkeypatch):
    async def fake_search(query, **kw):
        assert kw["topic"] == "news"
        return SAMPLE

    monkeypatch.setattr(tools_mod, "search", fake_search)
    out = await registered["search_news"](None, "saudi procurement")
    assert out["query"] == "saudi procurement"
    assert len(out["articles"]) == 2
    a = out["articles"][0]
    assert a["source"] == "reuters.com"
    assert set(a) >= {"title", "url", "source", "published_date", "snippet"}


@pytest.mark.asyncio
async def test_search_web_includes_answer(registered, monkeypatch):
    async def fake_search(query, **kw):
        assert kw["topic"] == "general"
        assert kw["include_answer"] is True
        return SAMPLE

    monkeypatch.setattr(tools_mod, "search", fake_search)
    out = await registered["search_web"](None, "what is NCGR")
    assert out["answer"] == "an answer"
    assert len(out["sources"]) == 2


@pytest.mark.asyncio
async def test_monitor_topic_dedupes_and_sorts(registered, monkeypatch):
    async def fake_search(query, **kw):
        return SAMPLE  # same two urls returned for every angle

    monkeypatch.setattr(tools_mod, "search", fake_search)
    out = await registered["monitor_topic"](
        None, "road safety", angles=["regulation", "technology"])
    # Two angles return the same 2 urls -> deduped to 2.
    assert out["article_count"] == 2
    # Newest first.
    dates = [a["published_date"] for a in out["articles"]]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.asyncio
async def test_read_article_blocks_unapproved_domain(registered, monkeypatch):
    monkeypatch.setattr(tools_mod, "DOMAIN_ENFORCE", True)
    monkeypatch.setattr(tools_mod, "APPROVED_DOMAINS", ["gov.ae"])
    monkeypatch.setattr(tools_mod, "domain_allowed", lambda url: False)
    out = await registered["read_article"](None, "https://example.com/x")
    assert "error" in out and "approved domains" in out["error"]


@pytest.mark.asyncio
async def test_read_article_returns_content(registered, monkeypatch):
    async def fake_extract(urls, **kw):
        return {"results": [{"raw_content": "full article text"}]}

    monkeypatch.setattr(tools_mod, "domain_allowed", lambda url: True)
    monkeypatch.setattr(tools_mod, "extract", fake_extract)
    out = await registered["read_article"](None, "https://gov.ae/x")
    assert out["content"] == "full article text"
    assert out["source"] == "gov.ae"


@pytest.mark.asyncio
async def test_read_article_rejects_bad_url(registered):
    out = await registered["read_article"](None, "not-a-url")
    assert "error" in out
