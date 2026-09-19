"""Structural checks for the MCP Registry metadata file ``server.json``.

These tests intentionally avoid network access: they verify the local file's
shape (required keys, name pattern, registry pointer) rather than fetching the
remote JSON Schema. Issue #39.
"""

import json
import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_JSON = REPO_ROOT / "server.json"
PYPROJECT = REPO_ROOT / "pyproject.toml"

NAME_PATTERN = re.compile(r"^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$")


def _load():
    return json.loads(SERVER_JSON.read_text(encoding="utf-8"))


def _project_version():
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]


def test_server_json_exists_and_is_valid_json():
    assert SERVER_JSON.is_file(), "server.json must exist at the repo root"
    doc = _load()
    assert isinstance(doc, dict)


def test_required_top_level_fields():
    doc = _load()
    # Required by the 2025-12-11 ServerDetail schema.
    for field in ("name", "description", "version"):
        assert doc.get(field), f"server.json missing required field: {field}"
    assert len(doc["description"]) <= 100
    assert NAME_PATTERN.match(doc["name"])


def test_registry_namespace_name():
    assert _load()["name"] == "io.github.montimage/sec-mcp"


def test_pypi_package_points_at_published_release():
    doc = _load()
    packages = doc.get("packages")
    assert isinstance(packages, list) and packages, "server.json needs a packages array"
    pkg = packages[0]
    assert pkg["registryType"] == "pypi"
    assert pkg["identifier"] == "sec-mcp"
    assert pkg["version"] == _project_version()
    assert doc["version"] == pkg["version"]
    assert pkg["transport"] == {"type": "stdio"}


def test_runtime_runs_sec_mcp_server_via_uvx():
    pkg = _load()["packages"][0]
    assert pkg.get("runtimeHint") == "uvx"
    args = pkg.get("runtimeArguments", [])
    rendered = []
    for arg in args:
        if arg.get("type") == "named":
            rendered.extend([arg["name"], arg["value"]])
        else:
            rendered.append(arg["value"])
    # uvx --from sec-mcp sec-mcp-server
    assert rendered == ["--from", "sec-mcp", "sec-mcp-server"]


def test_readme_carries_mcp_name_marker():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "mcp-name: io.github.montimage/sec-mcp" in readme
