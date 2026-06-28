# News & Intelligence MCP Server

A small, focused [Model Context Protocol](https://modelcontextprotocol.io) (MCP)
server that gives an agent the ability to **search the news**, **search the wider
web**, **monitor a topic** across several angles, and **read the full text of a
single article** — powered by the [Tavily](https://tavily.com) API.

It is built to back the **News & Intelligence Agent** in SAS Retrieval Agent
Manager (RAM): give it a Tavily key, optionally restrict it to a set of
**approved domains**, and attach it to a RAM agent as a *Container MCP Server*.

---

## Tools

| Tool | What it does |
|------|--------------|
| `get_intelligence_scope` | Reports the approved/blocked domains and search defaults. Call this first. |
| `search_news` | Searches recent **news** for a topic. Recency window: day/week/month/year. |
| `search_web` | Searches the wider **web** for background, returns a synthesized answer + sources. |
| `monitor_topic` | Runs one news search per *angle* and merges them into a de-duplicated, newest-first digest. |
| `read_article` | Fetches the cleaned full text of a single article URL (subject to the domain policy). |

Every result is trimmed to what an LLM needs — title, source, published date, a
short snippet, and the URL — so responses stay compact.

## The "approved domains" feature

Set `APPROVED_DOMAINS` to a comma/newline-separated allow-list and the server
will:

- restrict **every search** to those domains, and
- (unless `DOMAIN_ENFORCE=false`) refuse `read_article` on any other domain.

Sub-domains match automatically, so `gov.ae` also allows `traffic.gov.ae`.
A per-call `include_domains` argument can only *narrow* the policy, never widen
it. `BLOCKED_DOMAINS` is always excluded. Leave `APPROVED_DOMAINS` empty to
search the open web.

```bash
APPROVED_DOMAINS=gov.ae,thenationalnews.com,reuters.com,gulfnews.com
BLOCKED_DOMAINS=
DOMAIN_ENFORCE=true
```

## Configuration

All configuration is via environment variables — see [`.env.sample`](.env.sample).
The only required variable is `TAVILY_API_KEY`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `TAVILY_API_KEY` | — | **Required.** Tavily key from https://tavily.com |
| `APPROVED_DOMAINS` | _(empty)_ | Allow-list; empty = open web |
| `BLOCKED_DOMAINS` | _(empty)_ | Deny-list, always excluded |
| `DOMAIN_ENFORCE` | `true` | Block `read_article` outside the allow-list |
| `MAX_RESULTS` | `8` | Default results per search |
| `DEFAULT_SEARCH_DEPTH` | `basic` | `basic` or `advanced` |
| `DEFAULT_TIME_RANGE` | `week` | `day`/`week`/`month`/`year` |
| `MAX_CONTENT_CHARS` | `8000` | Cap on fetched article text (0 = no cap) |
| `HOST_PORT` | `8140` | HTTP listen port |
| `MCP_API_KEY` | _(empty)_ | Protect the HTTP endpoint (X-API-Key / Bearer) |
| `MCP_TRANSPORT` | `http` | `http` (`/mcp`) or `sse` (`/sse`) |
| `MCP_MODE` | `http-direct` | Container mode: `http-direct` or `stdio` |
| `SSL_VERIFY` | `true` | Set `false` behind a self-signed proxy |

## Run it

### Local (stdio — for Claude Desktop / VS Code / MCP Inspector)

```bash
uv venv && uv pip install -e .
cp .env.sample .env   # set TAVILY_API_KEY
uv run app-stdio
```

### Local (HTTP)

```bash
uv run app-http-direct      # serves /mcp on HOST_PORT (default 8140)
curl localhost:8140/health
```

### Docker (the way RAM hosts it)

```bash
docker build -t news-mcp .
docker run -p 8140:8140 --env-file .env news-mcp
```

The container defaults to `http-direct` mode and exposes:

- `GET /health` — liveness probe (open, no key required)
- `POST /mcp` — the MCP endpoint (protected by `MCP_API_KEY` if set)

## Attaching to a RAM agent

In SAS Retrieval Agent Manager you can attach this two ways:

1. **Container MCP Server** (recommended) — build and host the Docker image,
   then point RAM at `https://<host>/mcp`, setting the `MCP_API_KEY` header if
   configured.
2. **Code MCP Server** — paste a self-contained single-file version. See
   [`examples/ram_code_tool.py`](examples/ram_code_tool.py) and
   [`examples/requirements.txt`](examples/requirements.txt).

Then give the agent a collection (RAG) and a system prompt — see the
`news-intelligence-agent` folder in the `prompts` repository.

## Tests

```bash
uv run pytest          # offline; the Tavily network layer is stubbed
```
