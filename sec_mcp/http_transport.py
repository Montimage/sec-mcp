"""HTTP transport: DNS-rebinding protection and the CORS-wrapped ASGI app.

Used by ``sec-mcp-server --http`` so a browser — the landing-page playground —
can reach the MCP server over streamable HTTP. Every setting is read from the
environment at call time, keeping ``import sec_mcp.http_transport`` side-effect
free.

Environment:
    SEC_MCP_CORS_ORIGINS      comma-separated allowed origins; ``*`` allows any
                              origin (never with credentials) and disables the
                              DNS-rebinding check.
    SEC_MCP_HTTP_AUTH_TOKEN   optional bearer token required on every request.
"""

import hmac
import ipaddress
import logging
import os
from typing import Any
from urllib.parse import urlparse

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Local Vite dev (3000) and preview (4173) servers, plus the published
# landing page on GitHub Pages.
DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:4173,http://127.0.0.1:4173,"
    "https://montimage.github.io"
)

_LOOPBACK_HOSTS = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
_LOOPBACK_ORIGINS = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]


def cors_origins() -> list[str]:
    """Return the configured CORS origins (``SEC_MCP_CORS_ORIGINS``)."""
    raw = os.environ.get("SEC_MCP_CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def auth_token() -> str | None:
    """Return the bearer token (``SEC_MCP_HTTP_AUTH_TOKEN``), or None when unset."""
    return os.environ.get("SEC_MCP_HTTP_AUTH_TOKEN") or None


class BearerAuthMiddleware:
    """Require ``Authorization: Bearer <token>`` on every HTTP request.

    Installed inside the CORS middleware, so preflight ``OPTIONS`` requests are
    still answered while the endpoint itself is guarded. Non-HTTP scopes
    (lifespan) pass straight through; the comparison is timing-safe and the
    scheme is matched case-insensitively (RFC 7235).
    """

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self._token = token.encode("utf-8")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        parts = HTTPConnection(scope).headers.get("authorization", "").split(None, 1)
        if (
            len(parts) == 2
            and parts[0].lower() == "bearer"
            and hmac.compare_digest(parts[1].encode("utf-8"), self._token)
        ):
            await self.app(scope, receive, send)
            return

        response = JSONResponse(
            {"detail": "Unauthorized"},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
        await response(scope, receive, send)


def is_loopback_host(host: str) -> bool:
    """True when *host* binds loopback only — ``localhost``, ::1, 127.0.0.0/8."""
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        # A DNS name is treated as non-loopback: the warning is the safe default.
        return False


def build_transport_security(host: str, port: int) -> TransportSecuritySettings:
    """Build the DNS-rebinding allow-lists for HTTP mode.

    Loopback Host/Origin values are always allowed; configured origins are
    allowed as Origins and their host parts as Host targets; a non-loopback
    bind host is added to the Host list. An explicit ``*`` disables the check,
    mirroring the allow-all CORS opt-in.
    """
    origins = cors_origins()
    if "*" in origins:
        logger.warning("SEC_MCP_CORS_ORIGINS='*': DNS rebinding protection disabled")
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=False, allowed_hosts=[], allowed_origins=[]
        )

    allowed_hosts = list(_LOOPBACK_HOSTS)
    if not is_loopback_host(host):
        allowed_hosts.append(f"{host}:*")
    # A trusted origin's hostname is allowed on any port: the UI and the MCP
    # endpoint commonly share a host but not a port (e.g. :4173 and :8001).
    for origin in origins:
        hostname = urlparse(origin).hostname
        if hostname:
            allowed_hosts.append(f"[{hostname}]:*" if ":" in hostname else f"{hostname}:*")

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(dict.fromkeys(allowed_hosts)),
        allowed_origins=_LOOPBACK_ORIGINS + origins,
    )


def build_http_app(host: str, transport_security: TransportSecuritySettings) -> Starlette:
    """Build the streamable-HTTP ASGI app (``/mcp``) wrapped in CORS.

    Credentials are never allowed and ``Mcp-Session-Id`` is exposed so a
    browser client can keep its session. When ``SEC_MCP_HTTP_AUTH_TOKEN`` is
    set, bearer auth guards every request; binding a non-loopback host
    without it logs a warning.
    """
    from .mcp_server import mcp

    app: Starlette = mcp.streamable_http_app(host=host, transport_security=transport_security)

    token = auth_token()
    if token:
        # Registered before CORS: Starlette builds the last-added middleware
        # outermost, so CORS keeps answering preflights ahead of auth.
        app.add_middleware(BearerAuthMiddleware, token=token)
        logger.info("Bearer-token authentication enabled (SEC_MCP_HTTP_AUTH_TOKEN)")
    elif not is_loopback_host(host):
        logger.warning(
            "SEC_MCP_HTTP_AUTH_TOKEN is unset while binding non-loopback host %r: "
            "the MCP endpoint accepts unauthenticated requests from the network. "
            "Set SEC_MCP_HTTP_AUTH_TOKEN or put an authenticating proxy in front.",
            host,
        )

    origins = cors_origins()
    cors_kwargs: dict[str, Any] = {
        "allow_credentials": False,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
        "expose_headers": ["Mcp-Session-Id"],
    }
    if "*" in origins:
        cors_kwargs["allow_origin_regex"] = r".*"
    else:
        cors_kwargs["allow_origins"] = origins
    app.add_middleware(CORSMiddleware, **cors_kwargs)
    return app
