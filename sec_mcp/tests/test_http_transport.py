"""Tests for the streamable-HTTP transport behind ``sec-mcp-server --http`` (#162)."""

import asyncio
import logging

import pytest
from starlette.testclient import TestClient

from sec_mcp import http_transport, start_server
from sec_mcp.http_transport import (
    DEFAULT_CORS_ORIGINS,
    BearerAuthMiddleware,
    build_http_app,
    build_transport_security,
    is_loopback_host,
)

ORIGIN = "http://localhost:3000"
MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
    "Origin": ORIGIN,
}
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "0"},
    },
}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("SEC_MCP_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("SEC_MCP_HTTP_AUTH_TOKEN", raising=False)


def _client(app):
    # The loopback base URL keeps the Host header inside the DNS-rebinding
    # allow-list (TestClient defaults to "testserver").
    return TestClient(app, base_url="http://127.0.0.1:8000")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def test_default_origins_cover_local_vite_and_github_pages():
    origins = http_transport.cors_origins()
    assert origins == DEFAULT_CORS_ORIGINS.split(",")
    assert "https://montimage.github.io" in origins
    assert "http://localhost:3000" in origins


def test_origins_are_parsed_from_env(monkeypatch):
    monkeypatch.setenv("SEC_MCP_CORS_ORIGINS", " https://a.example , ,http://b.example:9000 ")
    assert http_transport.cors_origins() == ["https://a.example", "http://b.example:9000"]


def test_auth_token_empty_is_unset(monkeypatch):
    assert http_transport.auth_token() is None
    monkeypatch.setenv("SEC_MCP_HTTP_AUTH_TOKEN", "")
    assert http_transport.auth_token() is None
    monkeypatch.setenv("SEC_MCP_HTTP_AUTH_TOKEN", "s3cret")
    assert http_transport.auth_token() == "s3cret"


@pytest.mark.parametrize(
    "host, expected",
    [("localhost", True), ("LOCALHOST", True), ("127.0.0.1", True), ("127.8.8.8", True),
     ("::1", True), ("0.0.0.0", False), ("10.0.0.5", False), ("intranet.local", False)],
)
def test_is_loopback_host(host, expected):
    assert is_loopback_host(host) is expected


# ---------------------------------------------------------------------------
# DNS-rebinding transport security
# ---------------------------------------------------------------------------

def test_transport_security_loopback_bind():
    sec = build_transport_security("127.0.0.1", 8000)
    assert sec.enable_dns_rebinding_protection is True
    assert sec.allowed_hosts[:3] == ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    assert "http://localhost:*" in sec.allowed_origins
    assert "https://montimage.github.io" in sec.allowed_origins
    # Configured origins contribute their hostname on any port.
    assert "montimage.github.io:*" in sec.allowed_hosts
    assert "localhost:3000" not in sec.allowed_hosts
    assert len(sec.allowed_hosts) == len(set(sec.allowed_hosts))


def test_transport_security_non_loopback_bind_adds_host(monkeypatch):
    monkeypatch.setenv("SEC_MCP_CORS_ORIGINS", "https://ui.example")
    sec = build_transport_security("0.0.0.0", 8000)
    assert "0.0.0.0:*" in sec.allowed_hosts
    assert "ui.example:*" in sec.allowed_hosts
    assert sec.allowed_origins[-1] == "https://ui.example"


def test_transport_security_origin_host_allowed_on_other_ports(monkeypatch):
    # UI on :4173, MCP endpoint on :8001 of the same LAN host (Host header differs by port).
    monkeypatch.setenv("SEC_MCP_CORS_ORIGINS", "http://192.168.0.120:4173,http://[fd00::1]:4173")
    sec = build_transport_security("0.0.0.0", 8001)
    assert "192.168.0.120:*" in sec.allowed_hosts
    assert "[fd00::1]:*" in sec.allowed_hosts


def test_transport_security_wildcard_disables_protection(monkeypatch, caplog):
    monkeypatch.setenv("SEC_MCP_CORS_ORIGINS", "*")
    with caplog.at_level(logging.WARNING, logger="sec_mcp.http_transport"):
        sec = build_transport_security("127.0.0.1", 8000)
    assert sec.enable_dns_rebinding_protection is False
    assert sec.allowed_hosts == [] and sec.allowed_origins == []
    assert "DNS rebinding protection disabled" in caplog.text


# ---------------------------------------------------------------------------
# Bearer auth middleware
# ---------------------------------------------------------------------------

async def _ok_app(scope, receive, send):
    if scope["type"] == "http":
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})
    else:
        scope["passed"] = True


@pytest.mark.parametrize(
    "header, status",
    [("Bearer s3cret", 200), ("bearer s3cret", 200), ("BEARER s3cret", 200),
     ("Bearer wrong", 401), ("Basic s3cret", 401), ("s3cret", 401), (None, 401)],
)
def test_bearer_auth(header, status):
    client = TestClient(BearerAuthMiddleware(_ok_app, token="s3cret"))
    headers = {"Authorization": header} if header else {}
    response = client.get("/mcp", headers=headers)
    assert response.status_code == status
    if status == 401:
        assert response.json() == {"detail": "Unauthorized"}
        assert response.headers["www-authenticate"] == "Bearer"


def test_bearer_auth_passes_non_http_scopes():
    scope = {"type": "lifespan"}
    asyncio.run(BearerAuthMiddleware(_ok_app, token="s3cret")(scope, None, None))
    assert scope["passed"] is True


# ---------------------------------------------------------------------------
# The ASGI app: CORS + a real MCP handshake over HTTP
# ---------------------------------------------------------------------------

def test_cors_preflight_allowed_origin():
    app = build_http_app("127.0.0.1", build_transport_security("127.0.0.1", 8000))
    response = _client(app).options("/mcp", headers={
        "Origin": ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,mcp-session-id",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert "access-control-allow-credentials" not in response.headers


def test_cors_preflight_rejects_unknown_origin():
    app = build_http_app("127.0.0.1", build_transport_security("127.0.0.1", 8000))
    response = _client(app).options("/mcp", headers={
        "Origin": "https://evil.example",
        "Access-Control-Request-Method": "POST",
    })
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_wildcard_reflects_any_origin(monkeypatch):
    monkeypatch.setenv("SEC_MCP_CORS_ORIGINS", "*")
    app = build_http_app("127.0.0.1", build_transport_security("127.0.0.1", 8000))
    response = _client(app).options("/mcp", headers={
        "Origin": "https://anywhere.example",
        "Access-Control-Request-Method": "POST",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://anywhere.example"


def test_initialize_and_list_tools_over_http():
    app = build_http_app("127.0.0.1", build_transport_security("127.0.0.1", 8000))
    with _client(app) as client:
        response = client.post("/mcp", json=INITIALIZE, headers=MCP_HEADERS)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == ORIGIN
        assert "mcp-session-id" in response.headers["access-control-expose-headers"].lower()
        assert '"serverInfo"' in response.text and "sec-mcp" in response.text

        session = {"Mcp-Session-Id": response.headers["mcp-session-id"],
                   "Mcp-Protocol-Version": "2025-06-18"}
        client.post("/mcp", headers={**MCP_HEADERS, **session},
                    json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools = client.post("/mcp", headers={**MCP_HEADERS, **session},
                            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert tools.status_code == 200
        assert '"check_batch"' in tools.text


def test_auth_token_guards_endpoint_but_not_preflight(monkeypatch, caplog):
    monkeypatch.setenv("SEC_MCP_HTTP_AUTH_TOKEN", "s3cret")
    with caplog.at_level(logging.INFO, logger="sec_mcp.http_transport"):
        app = build_http_app("127.0.0.1", build_transport_security("127.0.0.1", 8000))
    assert "Bearer-token authentication enabled" in caplog.text
    with _client(app) as client:
        preflight = client.options("/mcp", headers={
            "Origin": ORIGIN, "Access-Control-Request-Method": "POST"})
        assert preflight.status_code == 200
        denied = client.post("/mcp", json=INITIALIZE, headers=MCP_HEADERS)
        assert denied.status_code == 401
        # CORS stays outermost, so the browser can read the 401.
        assert denied.headers["access-control-allow-origin"] == ORIGIN
        allowed = client.post("/mcp", json=INITIALIZE,
                              headers={**MCP_HEADERS, "Authorization": "Bearer s3cret"})
        assert allowed.status_code == 200


def test_non_loopback_without_token_warns(caplog):
    with caplog.at_level(logging.WARNING, logger="sec_mcp.http_transport"):
        build_http_app("0.0.0.0", build_transport_security("0.0.0.0", 8000))
    assert "SEC_MCP_HTTP_AUTH_TOKEN is unset" in caplog.text


def test_loopback_without_token_does_not_warn(caplog):
    with caplog.at_level(logging.WARNING, logger="sec_mcp.http_transport"):
        build_http_app("127.0.0.1", build_transport_security("127.0.0.1", 8000))
    assert "SEC_MCP_HTTP_AUTH_TOKEN" not in caplog.text


# ---------------------------------------------------------------------------
# start_server command line
# ---------------------------------------------------------------------------

def test_parse_args_defaults_to_stdio():
    args = start_server.parse_args([])
    assert (args.http, args.host, args.port) == (False, "127.0.0.1", 8000)


def test_parse_args_http_flags():
    args = start_server.parse_args(["--http", "--host", "0.0.0.0", "--port", "9001"])
    assert (args.http, args.host, args.port) == (True, "0.0.0.0", 9001)


def test_parse_args_rejects_bad_port():
    with pytest.raises(SystemExit) as exc:
        start_server.parse_args(["--port", "nope"])
    assert exc.value.code == 2


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        start_server.parse_args(["--help"])
    assert exc.value.code == 0
    assert "--http" in capsys.readouterr().out


def test_main_http_runs_uvicorn(monkeypatch, capsys):
    calls = {}
    monkeypatch.setattr(start_server, "setup_logging", lambda level: None)
    monkeypatch.setattr(start_server, "get_core", lambda: calls.setdefault("core", True))
    monkeypatch.setattr(start_server.mcp, "run",
                        lambda **kw: pytest.fail("stdio must not run in --http mode"))
    import uvicorn

    def fake_run(app, host, port, log_level):
        calls.update(app=app, host=host, port=port, log_level=log_level)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    start_server.main(["--http", "--port", "8123"])

    assert calls["core"] is True
    assert (calls["host"], calls["port"], calls["log_level"]) == ("127.0.0.1", 8123, "info")
    assert calls["app"] is not None
    err = capsys.readouterr()
    assert "http://127.0.0.1:8123/mcp" in err.err
    assert err.out == ""


@pytest.fixture
def clean_env(monkeypatch):
    # ensure_token exports the token; keep that write out of the real environment.
    monkeypatch.setattr(start_server.os, "environ", {})


def test_ensure_token_generates_for_network_bind(clean_env, capsys):
    token = start_server.ensure_token("0.0.0.0")
    assert token and len(token) >= 32
    assert http_transport.auth_token() == token
    err = capsys.readouterr().err
    assert f"#token={token}" in err


@pytest.mark.parametrize("host,no_auth,preset", [
    ("127.0.0.1", False, None),   # loopback: no token needed
    ("0.0.0.0", True, None),      # explicit --no-auth
    ("0.0.0.0", False, "mine"),   # operator-supplied token wins
])
def test_ensure_token_skips(clean_env, capsys, host, no_auth, preset):
    if preset:
        start_server.os.environ["SEC_MCP_HTTP_AUTH_TOKEN"] = preset
    assert start_server.ensure_token(host, no_auth) is None
    assert http_transport.auth_token() == preset
    assert capsys.readouterr().err == ""


def test_parse_args_no_auth_flag():
    assert start_server.parse_args(["--http", "--no-auth"]).no_auth is True
    assert start_server.parse_args([]).no_auth is False
