#!/usr/bin/env python3
"""Stdio MCP server for the News & Intelligence agent.

Lets an MCP client (Claude Desktop, VS Code, Cursor, the MCP Inspector, …)
launch the server on demand over stdio. The Tavily key is read from the
environment / .env.
"""

from fastmcp import FastMCP

from .config import TAVILY_API_KEY, logger
from .tools import register_tools

mcp = FastMCP("News & Intelligence MCP Server")
register_tools(mcp)


def main():
    if not TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY is not set — search tools will return an "
                       "error until it is configured.")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
