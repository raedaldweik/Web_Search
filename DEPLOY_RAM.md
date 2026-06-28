# Deploying the News & Intelligence MCP to SAS Retrieval Agent Manager (RAM)

Same flow as the SAS Viya and TomTom MCPs: a container image is published to
GitHub Container Registry (GHCR), you run it somewhere RAM can reach, then
register its URL in RAM as a **Remote MCP server**.

## 1. The image (GHCR)

`.github/workflows/build-and-push.yml` builds and pushes on every push to `main`
(and on a manual *Run workflow*):

```
ghcr.io/raedaldweik/web_search:latest
ghcr.io/raedaldweik/web_search:<commit-sha>
```

The package is private by default — `docker login ghcr.io` with a GitHub PAT
(scope `read:packages`) to pull it.

## 2. Run the container

The image serves **streamable HTTP** on port `8140` at path `/mcp` (http-direct
mode by default). `/health` stays open for probes.

```bash
docker run -d --name news-mcp -p 8140:8140 \
  -e TAVILY_API_KEY=<your-tavily-key> \
  -e APPROVED_DOMAINS=gov.ae,thenationalnews.com,gulfnews.com,reuters.com \
  -e MCP_API_KEY=<a-random-string> \
  ghcr.io/raedaldweik/web_search:latest
```

| Env var | Purpose |
|---------|---------|
| `TAVILY_API_KEY` | **Required.** Free key from https://tavily.com |
| `APPROVED_DOMAINS` | Optional allow-list; empty = open web. Sub-domains match (`gov.ae` ⇒ `traffic.gov.ae`) |
| `BLOCKED_DOMAINS` | Optional deny-list |
| `DOMAIN_ENFORCE` | `true` (default) also blocks `read_article` outside the allow-list |
| `DEFAULT_TIME_RANGE` | `week` (day/week/month/year) |
| `MAX_RESULTS` | `8` |
| `MCP_API_KEY` | Optional static key protecting `/mcp` (sent as `X-API-Key` or `Authorization: Bearer`) |

Smoke-test it:

```bash
curl -s http://localhost:8140/health
```

## 3. Register in RAM

In RAM → add a **Remote MCP server**:

| Field | Value |
|-------|-------|
| Transport | **Streamable HTTP** |
| URL | `http://<news-mcp-host>:8140/mcp` |
| Authentication | If you set `MCP_API_KEY`: header `X-API-Key: <key>` (or `Authorization: Bearer <key>`). Otherwise **None**. |

This is the same pattern as the SAS MCP (`:8134/mcp`) and TomTom MCP (`:3000/mcp`).

## 4. Build the agent + collection

1. Create a **collection** `news-intelligence-context` and upload the docs from
   the `prompts` repo → `news-intelligence-agent/collection/`.
2. Create an agent, attach the collection and this MCP server.
3. Paste `prompts/news-intelligence-agent/system_prompt.md` into the agent
   instructions; keep `{context}` in the Retrieval Settings prompt (Top K 4–6).

Then point the custom RTA UI (Roads_RAM_UI) at this agent and try:
*"What's new in road-safety regulation this week?"*

## Alternative: Code MCP Server (no hosting)

If you'd rather not run a container, RAM's **Code MCP Server** can host the
tools directly: paste `examples/ram_code_tool.py` into the `run.py` tab and
`examples/requirements.txt` into the `requirements.txt` tab, then set
`TAVILY_API_KEY` / `APPROVED_DOMAINS` on the template's Environment Variables.
(That single-file version exposes `search_news`, `search_web`, `read_article`;
the container additionally exposes `monitor_topic` and `get_intelligence_scope`.)
