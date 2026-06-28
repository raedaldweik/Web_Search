#!/bin/sh
# Selects which server to run inside the container.
#
#   MCP_MODE=http-direct  (default) — streamable HTTP. This is the mode used
#                                     when SAS Retrieval Agent Manager hosts
#                                     the container as a Container MCP Server.
#   MCP_MODE=stdio                  — stdio transport.
#
# An explicit command passed to the container overrides MCP_MODE entirely.
set -e

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

case "${MCP_MODE:-http-direct}" in
    http-direct) exec app-http-direct ;;
    stdio)       exec app-stdio ;;
    *)
        echo "Unknown MCP_MODE='${MCP_MODE}' (use http-direct|stdio)" >&2
        exit 1
        ;;
esac
