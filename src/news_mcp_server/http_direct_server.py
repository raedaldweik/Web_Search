#!/usr/bin/env python3
"""HTTP MCP server for the News & Intelligence agent.

Serves the MCP protocol over streamable HTTP so it can be hosted as a Container
MCP Server in SAS Retrieval Agent Manager (RAM). The server holds the Tavily
key itself, so MCP clients do not perform any OAuth. The endpoint can optionally
be protected with a static API key via ``MCP_API_KEY`` (sent as ``X-API-Key``
or ``Authorization: Bearer``).
"""

import uvicorn
from fastmcp import FastMCP
from starlette.responses import JSONResponse

from .config import (
    APPROVED_DOMAINS,
    HOST_PORT,
    MCP_API_KEY,
    MCP_TRANSPORT,
    TAVILY_API_KEY,
    logger,
)
from .tools import register_tools

mcp = FastMCP("News & Intelligence MCP Server")
register_tools(mcp)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({
        "status": "healthy",
        "service": "news-intelligence-mcp",
        "tavily_key_configured": bool(TAVILY_API_KEY),
        "approved_domains": len(APPROVED_DOMAINS),
    })


class ApiKeyMiddleware:
    """ASGI middleware that rejects HTTP requests lacking the API key.

    Accepts the key via ``X-API-Key: <key>`` or ``Authorization: Bearer <key>``.
    ``/health`` stays open so liveness probes work without credentials.
    """

    def __init__(self, app, api_key: str):
        self.app = app
        self.api_key = api_key

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") == "/health":
            return await self.app(scope, receive, send)

        headers = {k.decode().lower(): v.decode(errors="ignore")
                   for k, v in scope.get("headers", [])}
        provided = headers.get("x-api-key", "")
        if not provided:
            parts = headers.get("authorization", "").split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                provided = parts[1]
        if provided != self.api_key:
            response = JSONResponse({"error": "invalid or missing API key"},
                                    status_code=401)
            return await response(scope, receive, send)
        return await self.app(scope, receive, send)


def build_app():
    """Build the ASGI app, wrapping with API key auth when configured."""
    if MCP_TRANSPORT not in ("http", "sse"):
        raise ValueError(
            f"MCP_TRANSPORT must be 'http' or 'sse', got '{MCP_TRANSPORT}'")
    if not TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY is not set — search tools will return an "
                       "error until it is configured.")
    logger.info("Serving MCP over '%s' transport (endpoint: /%s)",
                MCP_TRANSPORT, "mcp" if MCP_TRANSPORT == "http" else "sse")
    app = mcp.http_app(transport=MCP_TRANSPORT)
    if MCP_API_KEY:
        logger.info("API key protection enabled (MCP_API_KEY is set)")
        return ApiKeyMiddleware(app, MCP_API_KEY)
    logger.warning("MCP_API_KEY is not set — the MCP endpoint is unauthenticated.")
    return app


def main():
    uvicorn.run(build_app(), host="0.0.0.0", port=HOST_PORT)


if __name__ == "__main__":
    main()
