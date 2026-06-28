"""MCP tool definitions for the News & Intelligence agent.

A deliberately small tool set: discover the assistant's scope, search the news,
search the wider web for background, monitor a topic across several angles, and
read the full text of a single article. Every result is trimmed to what an LLM
actually needs (title, source, date, snippet, url) so responses stay compact.
"""

from typing import Optional

from fastmcp import Context

from .config import (
    APPROVED_DOMAINS,
    BLOCKED_DOMAINS,
    DEFAULT_SEARCH_DEPTH,
    DEFAULT_TIME_RANGE,
    DOMAIN_ENFORCE,
    MAX_CONTENT_CHARS,
    MAX_RESULTS,
    VALID_SEARCH_DEPTHS,
    VALID_TIME_RANGES,
    logger,
)
from .tavily_client import TavilyError, domain_allowed, extract, search


def _host(url: str) -> str:
    host = (url or "").strip().lower().split("://", 1)[-1].split("/", 1)[0]
    return host[4:] if host.startswith("www.") else host


def _truncate(text: str, limit: int = MAX_CONTENT_CHARS) -> str:
    if not text or limit <= 0 or len(text) <= limit:
        return text or ""
    return (
        f"{text[:limit]}\n\n...[truncated {len(text) - limit} characters — "
        f"read_article on a narrower section or ask a more specific question "
        f"for the rest]..."
    )


def _shape_results(results: list[dict]) -> list[dict]:
    """Reduce raw Tavily hits to the fields the agent needs."""
    shaped = []
    for r in results or []:
        shaped.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "source": _host(r.get("url", "")),
            "published_date": r.get("published_date"),
            "snippet": _truncate(r.get("content", ""), 600),
            "relevance": round(r.get("score", 0.0), 3) if r.get("score") else None,
        })
    return shaped


def _normalise_depth(value: Optional[str]) -> str:
    v = (value or DEFAULT_SEARCH_DEPTH).lower()
    return v if v in VALID_SEARCH_DEPTHS else "basic"


def _normalise_range(value: Optional[str]) -> Optional[str]:
    if value is None:
        return DEFAULT_TIME_RANGE if DEFAULT_TIME_RANGE in VALID_TIME_RANGES else "week"
    v = value.lower()
    if v in ("", "all", "any", "none"):
        return None
    return v if v in VALID_TIME_RANGES else "week"


def register_tools(mcp) -> None:
    """Register all News & Intelligence tools on *mcp*."""

    if APPROVED_DOMAINS:
        logger.info(
            "Domain policy ACTIVE: %d approved domain(s); enforce=%s; %d blocked",
            len(APPROVED_DOMAINS), DOMAIN_ENFORCE, len(BLOCKED_DOMAINS),
        )
    elif BLOCKED_DOMAINS:
        logger.info("Domain policy: %d blocked domain(s); no approved allow-list",
                    len(BLOCKED_DOMAINS))

    # ------------------------------------------------------------------
    @mcp.tool()
    async def get_intelligence_scope(ctx: Context) -> dict:
        """Return this assistant's news/intelligence scope and search defaults.

        Call this first. It reports whether the assistant is restricted to a set
        of approved domains (an allow-list), which domains are blocked, and the
        default recency window and result count the search tools use. If no
        approved domains are configured, the assistant may search the open web.
        """
        logger.info("--- TOOL USED: get_intelligence_scope ---")
        return {
            "approved_domains": APPROVED_DOMAINS,
            "blocked_domains": BLOCKED_DOMAINS,
            "domain_allow_list_active": bool(APPROVED_DOMAINS),
            "reading_outside_approved_blocked": bool(APPROVED_DOMAINS and DOMAIN_ENFORCE),
            "default_time_range": DEFAULT_TIME_RANGE,
            "default_max_results": MAX_RESULTS,
            "notes": (
                "Searches are limited to approved_domains when that list is "
                "non-empty. When it is empty, the open web is searched except "
                "for blocked_domains."
            ),
        }

    # ------------------------------------------------------------------
    @mcp.tool()
    async def search_news(
        ctx: Context,
        query: str,
        time_range: Optional[str] = None,
        max_results: Optional[int] = None,
        search_depth: Optional[str] = None,
    ) -> dict:
        """Search recent NEWS for a topic and return ranked articles.

        Use this for current events, announcements, regulations, and emerging
        trends. ``time_range`` is one of day | week | month | year (default from
        configuration). Pass an empty string to drop the recency filter. Results
        are restricted to the assistant's approved domains when configured.

        Returns a list of articles with title, source, published_date, a short
        snippet, and the url (pass a url to ``read_article`` for the full text).
        """
        logger.info("--- TOOL USED: search_news (%s) ---", query)
        try:
            data = await search(
                query,
                topic="news",
                max_results=max_results or MAX_RESULTS,
                search_depth=_normalise_depth(search_depth),
                time_range=_normalise_range(time_range),
                include_answer=False,
            )
        except TavilyError as e:
            return {"error": str(e), "query": query, "articles": []}
        return {
            "query": query,
            "time_range": _normalise_range(time_range) or "any",
            "articles": _shape_results(data.get("results", [])),
        }

    # ------------------------------------------------------------------
    @mcp.tool()
    async def search_web(
        ctx: Context,
        query: str,
        max_results: Optional[int] = None,
        search_depth: Optional[str] = None,
    ) -> dict:
        """Search the wider WEB for background and context (not just news).

        Use this for definitions, reference material, company/organisation
        background, or anything that is not strictly recent news. Returns a
        short synthesized ``answer`` plus supporting sources. Respects the
        assistant's approved/blocked domains.
        """
        logger.info("--- TOOL USED: search_web (%s) ---", query)
        try:
            data = await search(
                query,
                topic="general",
                max_results=max_results or MAX_RESULTS,
                search_depth=_normalise_depth(search_depth),
                time_range=None,
                include_answer=True,
            )
        except TavilyError as e:
            return {"error": str(e), "query": query, "sources": []}
        return {
            "query": query,
            "answer": data.get("answer"),
            "sources": _shape_results(data.get("results", [])),
        }

    # ------------------------------------------------------------------
    @mcp.tool()
    async def monitor_topic(
        ctx: Context,
        topic: str,
        angles: Optional[list[str]] = None,
        time_range: Optional[str] = None,
        per_angle: int = 4,
    ) -> dict:
        """Build a multi-angle news digest for a topic — good for monitoring.

        Runs one news search per angle (e.g. ["regulation", "technology",
        "safety"]) and merges the results into a single de-duplicated digest,
        newest first. If ``angles`` is omitted, a single search on ``topic`` is
        run. Use this to scan an area of interest in one call rather than many.
        """
        logger.info("--- TOOL USED: monitor_topic (%s) ---", topic)
        rng = _normalise_range(time_range)
        queries = [f"{topic} {a}".strip() for a in (angles or [""])]
        seen: set[str] = set()
        digest: list[dict] = []
        errors: list[str] = []
        for q in queries:
            try:
                data = await search(
                    q, topic="news", max_results=per_angle,
                    search_depth=_normalise_depth(None), time_range=rng,
                )
            except TavilyError as e:
                errors.append(f"{q}: {e}")
                continue
            for art in _shape_results(data.get("results", [])):
                key = art["url"]
                if key and key not in seen:
                    seen.add(key)
                    art["matched_angle"] = q
                    digest.append(art)
        # Newest first when dates are present; undated items sink to the bottom.
        digest.sort(key=lambda a: a.get("published_date") or "", reverse=True)
        result = {"topic": topic, "time_range": rng or "any",
                  "article_count": len(digest), "articles": digest}
        if errors:
            result["errors"] = errors
        return result

    # ------------------------------------------------------------------
    @mcp.tool()
    async def read_article(ctx: Context, url: str) -> dict:
        """Fetch the cleaned full text of a single article by URL.

        Use this after a search to read a promising result in depth. If the
        assistant has an approved-domain allow-list and enforcement is on,
        reading a URL outside that list is refused. Long pages are truncated to
        keep the response within the model's context window.
        """
        logger.info("--- TOOL USED: read_article (%s) ---", url)
        if not url or "://" not in url:
            return {"error": "Provide a full URL including http(s)://", "url": url}
        if DOMAIN_ENFORCE and not domain_allowed(url):
            allowed = ", ".join(APPROVED_DOMAINS) if APPROVED_DOMAINS else "(none)"
            return {
                "error": (
                    f"{_host(url)} is outside this assistant's approved domains "
                    f"and cannot be read. Approved domains: {allowed}."
                ),
                "url": url,
            }
        try:
            data = await extract([url])
        except TavilyError as e:
            return {"error": str(e), "url": url}
        results = data.get("results") or []
        if not results:
            failed = data.get("failed_results") or []
            reason = failed[0].get("error") if failed else "no content returned"
            return {"error": f"Could not extract article: {reason}", "url": url}
        first = results[0]
        return {
            "url": url,
            "source": _host(url),
            "content": _truncate(first.get("raw_content") or first.get("content", "")),
        }
