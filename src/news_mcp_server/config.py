"""Configuration for the News & Intelligence MCP server.

Everything is driven by environment variables so the same image can be
re-pointed at a new Tavily key or a new set of approved domains without a code
change — the model SAS Retrieval Agent Manager expects from a hosted MCP tool
server.
"""

import logging
import os
import ssl

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("news-mcp-server")


def _split_list(raw: str) -> list[str]:
    """Parse a comma/newline-separated env var into a clean lowercase list.

    Accepts bare domains (``example.com``) or URLs (``https://example.com/x``)
    and normalises both to a bare host. Blank entries are dropped.
    """
    if not raw:
        return []
    parts = raw.replace("\n", ",").split(",")
    out: list[str] = []
    for p in parts:
        host = p.strip().lower()
        if not host:
            continue
        # Allow users to paste full URLs; keep only the host portion.
        host = host.split("://", 1)[-1]
        host = host.split("/", 1)[0]
        host = host.lstrip("*.")  # treat "*.gov.ae" and "gov.ae" the same
        if host:
            out.append(host)
    # De-duplicate while preserving order.
    return list(dict.fromkeys(out))


# --- Tavily ---------------------------------------------------------------
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_BASE_URL = os.getenv("TAVILY_BASE_URL", "https://api.tavily.com").rstrip("/")

# --- Domain controls ------------------------------------------------------
# When APPROVED_DOMAINS is non-empty, searches are restricted to those domains
# and (unless DOMAIN_ENFORCE=false) reading an article from any other domain is
# refused. BLOCKED_DOMAINS is always excluded from results.
APPROVED_DOMAINS = _split_list(os.getenv("APPROVED_DOMAINS", ""))
BLOCKED_DOMAINS = _split_list(os.getenv("BLOCKED_DOMAINS", ""))
DOMAIN_ENFORCE = os.getenv("DOMAIN_ENFORCE", "true").lower() not in (
    "false", "0", "no",
)

# --- Search defaults ------------------------------------------------------
# How many results a search returns by default (callers can override per call).
MAX_RESULTS = int(os.getenv("MAX_RESULTS", "8"))
# "basic" (fast, cheaper) or "advanced" (deeper, better for hard questions).
DEFAULT_SEARCH_DEPTH = os.getenv("DEFAULT_SEARCH_DEPTH", "basic").lower()
# Default recency window for news searches: day | week | month | year.
DEFAULT_TIME_RANGE = os.getenv("DEFAULT_TIME_RANGE", "week").lower()
# Cap the characters of fetched article text so one long page can't overflow
# the agent's context window. 0 disables capping.
MAX_CONTENT_CHARS = int(os.getenv("MAX_CONTENT_CHARS", "8000"))
# Outbound request timeout (seconds).
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "30"))

# --- Server / transport ---------------------------------------------------
HOST_PORT = int(os.getenv("HOST_PORT", "8140"))
# Optional static API key protecting the direct HTTP endpoint. Clients send it
# as X-API-Key or Authorization: Bearer.
MCP_API_KEY = os.getenv("MCP_API_KEY", "")
# "http" (streamable HTTP, endpoint /mcp) or "sse" (Server-Sent Events).
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "http").lower()

# --- TLS ------------------------------------------------------------------
SSL_VERIFY = os.getenv("SSL_VERIFY", "true").lower() not in ("false", "0", "no")

if not SSL_VERIFY:
    # Disable SSL verification (e.g. behind a self-signed corporate proxy).
    import httpx

    if not getattr(httpx.AsyncClient.__init__, "_news_mcp_ssl_patched", False):
        _ssl_context = ssl.create_default_context()
        _ssl_context.check_hostname = False
        _ssl_context.verify_mode = ssl.CERT_NONE

        _orig_async_init = httpx.AsyncClient.__init__

        def _patched_async_init(self, *args, **kwargs):
            kwargs.setdefault("verify", _ssl_context)
            _orig_async_init(self, *args, **kwargs)

        _patched_async_init._news_mcp_ssl_patched = True
        httpx.AsyncClient.__init__ = _patched_async_init


VALID_TIME_RANGES = {"day", "week", "month", "year"}
VALID_SEARCH_DEPTHS = {"basic", "advanced"}
