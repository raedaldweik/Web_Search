# Deploying the News & Intelligence MCP to SAS Retrieval Agent Manager (RAM)

Same flow as the SAS Viya and TomTom MCPs: a container image is published to
GitHub Container Registry (GHCR), and RAM **runs the container itself** when you
register it as a **Container MCP Server** template — you do not host it
separately.

## 1. The image (GHCR)

`.github/workflows/build-and-push.yml` builds and pushes on every push to `main`
(and on a manual *Run workflow*):

```
ghcr.io/raedaldweik/web_search:latest
ghcr.io/raedaldweik/web_search:<commit-sha>
```

The image serves streamable HTTP on port **8140** at base path **`/mcp`**
(http-direct mode by default); `/health` stays open for probes.

### Make the package pullable by RAM

A newly created GHCR package is **private by default**. RAM can only pull it if
it has the same access as your other MCP packages. On GitHub:

> Profile → **Packages** → `web_search` → **Package settings** → set visibility
> to **Public**, *or* grant the same repository/Actions access you gave
> `sas-mcp-server`. Match whatever makes the SAS package pullable by RAM.

## 2. Register in RAM (Container MCP Server template)

RAM → **Code Templates → Tools → Container MCP Server**, then fill in:

**Settings**

| Field | Value |
|-------|-------|
| Name | `News Intelligence MCP` |
| Description | `Tavily-backed news & web search with approved-domain control` |
| Container image | `ghcr.io/raedaldweik/web_search:latest` |
| Arguments | *(empty — entrypoint defaults to http-direct)* |
| Transport | **HTTP** |
| Port | **8140** |
| Base Path | **/mcp** |
| Requested CPU | `1` |
| Requested Memory | `1Gi` |

**Authentication:** None (the Tavily key is supplied via env; RAM reaches
`/mcp` in-cluster).

**Environment Variables**

| Name | Value | Secret |
|------|-------|--------|
| `TAVILY_API_KEY` | your Tavily key (https://tavily.com) | ✅ |
| `APPROVED_DOMAINS` | optional allow-list, e.g. `gov.ae,thenationalnews.com,gulfnews.com,reuters.com` (empty = open web; sub-domains match) | |
| `BLOCKED_DOMAINS` | optional deny-list | |
| `DOMAIN_ENFORCE` | `true` (default) also blocks `read_article` outside the allow-list | |
| `DEFAULT_TIME_RANGE` | `week` (day/week/month/year) | |
| `MAX_RESULTS` | `8` | |

Only `TAVILY_API_KEY` is required; the rest have built-in defaults.

This is the same pattern as the SAS Viya MCP template (image
`ghcr.io/raedaldweik/sas-mcp-server:latest`, port `8134`, base path `/mcp`).

## 3. Build the agent + collection

1. Create a **collection** `news-intelligence-context` and upload the docs from
   the `prompts` repo → `news-intelligence-agent/collection/`.
2. Create an agent, attach the collection and this MCP tool.
3. Paste `prompts/news-intelligence-agent/system_prompt.md` into the agent
   instructions; keep `{context}` in the Retrieval Settings prompt (Top K 4–6).

Then point the custom NCGR UI (Finance_RAM_UI) at this agent and try:
*"What's new in Saudi government procurement this week?"*

## Tools exposed

`get_intelligence_scope`, `search_news`, `search_web`, `monitor_topic`,
`read_article`.

## Alternative: Code MCP Server (no container)

RAM's **Code MCP Server** can host the tools directly instead of a container:
paste `examples/ram_code_tool.py` into the `run.py` tab and
`examples/requirements.txt` into the `requirements.txt` tab, then set
`TAVILY_API_KEY` / `APPROVED_DOMAINS` on the template's Environment Variables.
(That single-file version exposes `search_news`, `search_web`, `read_article`.)
