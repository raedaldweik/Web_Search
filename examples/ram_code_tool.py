"""Single-file News & Intelligence tools for SAS RAM "Code MCP Server".

Paste this into the run.py tab of a Code MCP Server template in SAS Retrieval
Agent Manager, and paste examples/requirements.txt into the requirements.txt
tab. It is a self-contained equivalent of the packaged server in this repo —
use it when you want the tools without building/hosting the Docker image.

Configure via environment variables on the template:
    TAVILY_API_KEY      (required)  Tavily key from https://tavily.com
    APPROVED_DOMAINS    (optional)  comma-separated allow-list (e.g. gov.ae,reuters.com)
    BLOCKED_DOMAINS     (optional)  comma-separated deny-list
    DEFAULT_TIME_RANGE  (optional)  day | week | month | year  (default week)
    MAX_RESULTS         (optional)  default 8
"""

import os

import httpx
from fastmcp import Context, FastMCP

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
BASE_URL = "https://api.tavily.com"


def _split(raw: str) -> list[str]:
    out = []
    for p in (raw or "").replace("\n", ",").split(","):
        h = p.strip().lower().split("://")[-1].split("/")[0].lstrip("*.")
        if h:
            out.append(h)
    return list(dict.fromkeys(out))


APPROVED = _split(os.getenv("APPROVED_DOMAINS", ""))
BLOCKED = _split(os.getenv("BLOCKED_DOMAINS", ""))
TIME_RANGE = os.getenv("DEFAULT_TIME_RANGE", "week").lower()
MAX_RESULTS = int(os.getenv("MAX_RESULTS", "8"))

mcp = FastMCP("News & Intelligence MCP Server")


def _host(url: str) -> str:
    h = (url or "").lower().split("://")[-1].split("/")[0]
    return h[4:] if h.startswith("www.") else h


def _allowed(url: str) -> bool:
    h = _host(url)
    if BLOCKED and any(h == d or h.endswith("." + d) for d in BLOCKED):
        return False
    if APPROVED and not any(h == d or h.endswith("." + d) for d in APPROVED):
        return False
    return True


async def _post(path: str, payload: dict) -> dict:
    if not TAVILY_API_KEY:
        return {"error": "TAVILY_API_KEY is not set."}
    headers = {"Authorization": f"Bearer {TAVILY_API_KEY}"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{BASE_URL}{path}", headers=headers, json=payload)
    if r.status_code >= 400:
        return {"error": f"Tavily error {r.status_code}: {r.text[:300]}"}
    return r.json()


def _shape(results: list) -> list:
    out = []
    for x in results or []:
        out.append({
            "title": x.get("title", ""),
            "url": x.get("url", ""),
            "source": _host(x.get("url", "")),
            "published_date": x.get("published_date"),
            "snippet": (x.get("content") or "")[:600],
        })
    return out


def _domains_payload(payload: dict) -> dict:
    if APPROVED:
        payload["include_domains"] = APPROVED
    if BLOCKED:
        payload["exclude_domains"] = BLOCKED
    return payload


@mcp.tool()
async def search_news(ctx: Context, query: str, time_range: str = "",
                      max_results: int = 0) -> dict:
    """Search recent news for a topic. time_range: day|week|month|year."""
    payload = _domains_payload({
        "query": query, "topic": "news",
        "max_results": max_results or MAX_RESULTS,
        "time_range": (time_range or TIME_RANGE),
    })
    data = await _post("/search", payload)
    if "error" in data:
        return data
    return {"query": query, "articles": _shape(data.get("results", []))}


@mcp.tool()
async def search_web(ctx: Context, query: str, max_results: int = 0) -> dict:
    """Search the wider web for background; returns an answer plus sources."""
    payload = _domains_payload({
        "query": query, "topic": "general",
        "max_results": max_results or MAX_RESULTS, "include_answer": True,
    })
    data = await _post("/search", payload)
    if "error" in data:
        return data
    return {"query": query, "answer": data.get("answer"),
            "sources": _shape(data.get("results", []))}


@mcp.tool()
async def read_article(ctx: Context, url: str) -> dict:
    """Fetch the cleaned full text of a single article URL."""
    if "://" not in url:
        return {"error": "Provide a full URL including http(s)://"}
    if not _allowed(url):
        return {"error": f"{_host(url)} is outside the approved domains."}
    data = await _post("/extract", {"urls": [url]})
    if "error" in data:
        return data
    results = data.get("results") or []
    if not results:
        return {"error": "Could not extract article.", "url": url}
    txt = results[0].get("raw_content") or results[0].get("content", "")
    return {"url": url, "source": _host(url), "content": txt[:8000]}
