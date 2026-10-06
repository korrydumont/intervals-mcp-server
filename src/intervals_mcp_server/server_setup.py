"""
Server setup and initialization for Intervals.icu MCP Server.

This module handles transport configuration and server startup logic.
"""

import hmac
import json
import os
import logging

import uvicorn
from mcp.server.fastmcp import FastMCP  # pylint: disable=import-error

from intervals_mcp_server.utils.types import TransportAliases

logger = logging.getLogger("intervals_icu_mcp_server")

LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")
MIN_AUTH_TOKEN_LENGTH = 32


class BearerTokenMiddleware:  # pylint: disable=too-few-public-methods
    """ASGI middleware that rejects HTTP requests without the expected bearer token."""

    def __init__(self, app, token: str) -> None:
        self.app = app
        self.expected = f"Bearer {token}".encode()

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http":
            supplied = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(supplied, self.expected):
                body = json.dumps({"error": "unauthorized"}).encode()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode()),
                            (b"www-authenticate", b"Bearer"),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


def _get_auth_token(host: str) -> str | None:
    """
    Read MCP_AUTH_TOKEN. Refuse to serve on a non-loopback host without one.

    Raises:
        ValueError: If the token is missing on a public host, or too short.
    """
    token = os.getenv("MCP_AUTH_TOKEN", "")
    if not token:
        if host not in LOOPBACK_HOSTS:
            raise ValueError(
                f"MCP_AUTH_TOKEN must be set when serving on non-loopback host {host!r}."
            )
        return None
    if len(token) < MIN_AUTH_TOKEN_LENGTH:
        raise ValueError(f"MCP_AUTH_TOKEN must be at least {MIN_AUTH_TOKEN_LENGTH} characters.")
    return token


def setup_transport() -> TransportAliases:
    """
    Setup and validate the MCP transport configuration.

    Reads MCP_TRANSPORT environment variable and validates it against
    supported transport types.

    Returns:
        TransportAliases: The selected transport type.

    Raises:
        ValueError: If the transport type is not supported.
    """
    transport_env = os.getenv("MCP_TRANSPORT", TransportAliases.STDIO.value).lower()
    try:
        transport_alias = TransportAliases(transport_env)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in TransportAliases)
        raise ValueError(f"Unsupported MCP_TRANSPORT value. Use one of: {allowed}.") from exc

    # Map HTTP to STREAMABLE_HTTP
    selected_transport = (
        TransportAliases.STREAMABLE_HTTP
        if transport_alias == TransportAliases.HTTP
        else transport_alias
    )

    return selected_transport


def start_server(mcp_instance: FastMCP, transport: TransportAliases) -> None:
    """
    Start the MCP server with the specified transport.

    Args:
        mcp_instance (FastMCP): The FastMCP server instance to start.
        transport (TransportAliases): The transport type to use.
    """
    host = mcp_instance.settings.host
    port = mcp_instance.settings.port

    if transport == TransportAliases.STDIO:
        logger.info("Starting MCP server with stdio transport.")
        mcp_instance.run()
    elif transport == TransportAliases.SSE:
        mount_path = os.getenv("MCP_SSE_MOUNT_PATH")
        logger.info(
            "Starting MCP server with SSE transport at http://%s:%s%s (messages: %s).",
            host,
            port,
            mcp_instance.settings.sse_path,
            mcp_instance.settings.message_path,
        )
        mcp_instance.run(transport="sse", mount_path=mount_path)
    else:  # STREAMABLE_HTTP
        token = _get_auth_token(host)
        logger.info(
            "Starting MCP server with Streamable HTTP transport at http://%s:%s%s (bearer auth %s).",
            host,
            port,
            mcp_instance.settings.streamable_http_path,
            "enabled" if token else "disabled",
        )
        if token is None:
            mcp_instance.run(transport="streamable-http")
            return
        app = BearerTokenMiddleware(mcp_instance.streamable_http_app(), token)
        uvicorn.run(app, host=host, port=port, log_level=mcp_instance.settings.log_level.lower())
