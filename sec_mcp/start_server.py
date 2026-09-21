#!/usr/bin/env python3
"""Start the MCP server in persistent mode (stdio by default, or HTTP)."""

import argparse
import os
import sys

# Adjust sys.path to allow direct execution of this script
# This script is in /Users/montimage/workspace/montimage/sec-mcp/sec_mcp/
# The project root is /Users/montimage/workspace/montimage/sec-mcp/
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from sec_mcp.mcp_server import get_core, mcp
from sec_mcp.utility import load_config, setup_logging


def parse_args(argv=None) -> argparse.Namespace:
    """Parse the server command line (``argv`` defaults to ``sys.argv[1:]``)."""
    parser = argparse.ArgumentParser(
        prog="sec-mcp-server",
        description="Run the sec-mcp MCP server (stdio by default).",
    )
    parser.add_argument("--http", action="store_true",
                        help="serve streamable HTTP at http://HOST:PORT/mcp instead of stdio")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (default: 8000)")
    return parser.parse_args(argv)


def run_http(host: str, port: int, log_level: str) -> None:
    """Serve the CORS-wrapped streamable-HTTP app with uvicorn."""
    import uvicorn

    from sec_mcp.http_transport import build_http_app, build_transport_security

    app = build_http_app(host, build_transport_security(host, port))
    print(f"MCP Endpoint: http://{host}:{port}/mcp", file=sys.stderr)
    uvicorn.run(app, host=host, port=port, log_level=log_level.lower())


def main(argv=None):
    """Entrypoint for MCP server via console script."""
    args = parse_args(argv)
    log_level = load_config().get("log_level", "INFO")
    setup_logging(log_level)
    # Initialize storage, logging and the update scheduler before serving.
    get_core()
    if args.http:
        print("Starting MCP server with streamable HTTP transport...", file=sys.stderr)
        run_http(args.host, args.port, log_level)
    else:
        print("Starting MCP server with STDIO transport...", file=sys.stderr)
        mcp.run(transport='stdio')

if __name__ == "__main__":  # pragma: no cover — entrypoint guard
    main()
