"""
Shared MCP instance module.

This module provides a shared FastMCP instance that can be imported by both
the server module and tool modules without creating cyclic imports.
"""

import os

from mcp.server.fastmcp import FastMCP  # pylint: disable=import-error

from intervals_mcp_server.api.client import setup_api_client

# FastMCP passes its own defaults for host/port/path explicitly, which override the
# FASTMCP_* environment variables, so read them here. PORT is set by Cloud Run.
mcp: FastMCP = FastMCP(  # pylint: disable=invalid-name
    "intervals-icu",
    lifespan=setup_api_client,
    host=os.getenv("FASTMCP_HOST", "127.0.0.1"),
    port=int(os.getenv("PORT") or os.getenv("FASTMCP_PORT") or "8000"),
    streamable_http_path=os.getenv("FASTMCP_STREAMABLE_HTTP_PATH", "/mcp"),
)
