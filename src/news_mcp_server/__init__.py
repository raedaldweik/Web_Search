"""News & Intelligence MCP server.

A small, focused Model Context Protocol server that gives an agent the ability
to search the web and the news for current events, monitor topics over time,
and read the full text of a specific article — powered by the Tavily API.

It is designed to back the "News & Intelligence Agent" in SAS Retrieval Agent
Manager (RAM): point it at a Tavily key, optionally restrict it to a set of
approved domains, and attach it to an agent as a Container MCP Server.
"""

__version__ = "0.1.0"
