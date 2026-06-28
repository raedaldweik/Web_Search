import pytest

from news_mcp_server import tavily_client as tc


def test_host_of():
    assert tc._host_of("https://www.Reuters.com/world/x") == "reuters.com"
    assert tc._host_of("http://gov.ae") == "gov.ae"


def test_domain_allowed_with_approved_list(monkeypatch):
    monkeypatch.setattr(tc, "APPROVED_DOMAINS", ["gov.ae", "reuters.com"])
    monkeypatch.setattr(tc, "BLOCKED_DOMAINS", [])
    assert tc.domain_allowed("https://traffic.gov.ae/a")  # sub-domain matches
    assert tc.domain_allowed("https://reuters.com/x")
    assert tc.domain_allowed("https://www.reuters.com/x")  # www candidate normalised
    assert not tc.domain_allowed("https://example.com/x")


def test_domain_allowed_with_www_normalised_config():
    """An approved entry configured with www./full-URL still matches candidates.

    Mirrors how config._split_list normalises entries; a regression here would
    silently disable the whole allow-list.
    """
    from news_mcp_server.config import _split_list
    # config normalises "www.gov.ae" -> "gov.ae"
    assert _split_list("www.gov.ae") == ["gov.ae"]
    assert _split_list("https://www.gov.ae/news") == ["gov.ae"]


def test_domain_allowed_blocklist_wins(monkeypatch):
    monkeypatch.setattr(tc, "APPROVED_DOMAINS", [])
    monkeypatch.setattr(tc, "BLOCKED_DOMAINS", ["spam.com"])
    assert not tc.domain_allowed("https://spam.com/x")
    assert tc.domain_allowed("https://anything.com/x")


@pytest.mark.asyncio
async def test_search_intersects_include_with_approved(monkeypatch):
    captured = {}

    async def fake_post(path, payload):
        captured["path"] = path
        captured["payload"] = payload
        return {"results": []}

    monkeypatch.setattr(tc, "_post", fake_post)
    monkeypatch.setattr(tc, "APPROVED_DOMAINS", ["gov.ae", "reuters.com"])
    monkeypatch.setattr(tc, "BLOCKED_DOMAINS", ["spam.com"])

    # A caller asking for example.com (not approved) must be narrowed away.
    await tc.search("q", topic="news", include_domains=["example.com"])
    assert captured["path"] == "/search"
    assert captured["payload"]["include_domains"] == ["gov.ae", "reuters.com"]
    assert "spam.com" in captured["payload"]["exclude_domains"]


@pytest.mark.asyncio
async def test_search_allows_subdomain_narrowing_under_approved(monkeypatch):
    captured = {}

    async def fake_post(path, payload):
        captured["payload"] = payload
        return {"results": []}

    monkeypatch.setattr(tc, "_post", fake_post)
    monkeypatch.setattr(tc, "APPROVED_DOMAINS", ["gov.ae"])
    monkeypatch.setattr(tc, "BLOCKED_DOMAINS", [])
    # Narrowing to a sub-domain of an approved domain is allowed (not dropped).
    await tc.search("q", topic="news", include_domains=["traffic.gov.ae"])
    assert captured["payload"]["include_domains"] == ["traffic.gov.ae"]


@pytest.mark.asyncio
async def test_search_no_approved_list_passes_caller_includes(monkeypatch):
    captured = {}

    async def fake_post(path, payload):
        captured["payload"] = payload
        return {"results": []}

    monkeypatch.setattr(tc, "_post", fake_post)
    monkeypatch.setattr(tc, "APPROVED_DOMAINS", [])
    monkeypatch.setattr(tc, "BLOCKED_DOMAINS", [])
    await tc.search("q", topic="general", include_domains=["example.com"])
    assert captured["payload"]["include_domains"] == ["example.com"]
