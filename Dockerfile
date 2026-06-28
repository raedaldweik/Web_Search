FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base-builder

WORKDIR /app
COPY . .
RUN uv build

FROM python:3.12-slim-bookworm AS runner
ARG HOST_PORT=8140

RUN addgroup --system app && adduser --system --ingroup app --home /app app

COPY --from=base-builder /app/dist/ /install

WORKDIR /app
RUN python3 -m venv .venv \
    && /app/.venv/bin/pip install --no-cache-dir /install/*.whl \
    && rm -r /install

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"

USER app

EXPOSE ${HOST_PORT}
# Default to direct HTTP mode so the container is ready to be hosted by an MCP
# client such as SAS Retrieval Agent Manager. Override with MCP_MODE
# (http-direct|stdio) or by passing an explicit command.
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
