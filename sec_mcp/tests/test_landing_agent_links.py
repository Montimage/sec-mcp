"""Agent-discovery link surface of the GitHub Pages landing site.

GitHub Pages cannot emit custom HTTP response headers, so the ``Link:``
headers the agent-readiness check asks for (issue #136) are serialized as
HTML ``<link>`` elements — the RFC 8288 in-document serialization — plus an
RFC 9727 ``.well-known/api-catalog`` linkset document. These tests pin that
surface: the relations exist in ``<head>``, the catalog parses and points at
deployed assets, and the published copy of the MCP server manifest stays in
sync with the canonical ``server.json`` at the repo root.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LANDING = REPO_ROOT / "react-landing-page"
INDEX_HTML = LANDING / "index.html"
PUBLIC = LANDING / "public"
SITE_BASE = "https://montimage.github.io/sec-mcp"


def _head():
    return INDEX_HTML.read_text(encoding="utf-8")


def _catalog():
    path = PUBLIC / ".well-known" / "api-catalog"
    assert path.is_file(), "public/.well-known/api-catalog must exist"
    return json.loads(path.read_text(encoding="utf-8"))


def test_head_links_to_api_catalog():
    assert (
        'rel="api-catalog" href="/sec-mcp/.well-known/api-catalog"' in _head()
    )


def test_head_links_to_service_desc_and_doc():
    head = _head()
    assert 'rel="service-desc"' in head
    assert 'href="/sec-mcp/server.json"' in head
    assert 'rel="service-doc"' in head
    assert 'href="/sec-mcp/index.md"' in head


def test_head_keeps_describedby_and_markdown_alternate():
    head = _head()
    assert 'rel="describedby" href="/sec-mcp/llms.txt"' in head
    assert 'rel="alternate" type="text/markdown" href="/sec-mcp/index.md"' in head


def test_api_catalog_is_valid_linkset():
    doc = _catalog()
    linkset = doc.get("linkset")
    assert isinstance(linkset, list) and linkset, "linkset must be a non-empty list"
    anchors = [entry.get("anchor") for entry in linkset]
    assert f"{SITE_BASE}/" in anchors


def test_api_catalog_carries_rfc9727_profile_and_relations():
    doc = _catalog()
    profile_hrefs = [
        link["href"]
        for entry in doc["linkset"]
        for link in entry.get("profile", [])
    ]
    assert "https://www.rfc-editor.org/info/rfc9727" in profile_hrefs
    service = next(
        entry for entry in doc["linkset"] if entry.get("anchor") == f"{SITE_BASE}/"
    )
    assert service["service-desc"][0]["href"] == f"{SITE_BASE}/server.json"
    assert any(
        link["href"] == f"{SITE_BASE}/index.md" for link in service["service-doc"]
    )
    assert any(
        link["href"] == f"{SITE_BASE}/llms.txt" for link in service["describedby"]
    )


def test_api_catalog_same_origin_targets_exist_in_public():
    """Every same-origin catalog target must be a real deployed asset."""
    site_prefix = f"{SITE_BASE}/"
    for entry in _catalog()["linkset"]:
        for rel, links in entry.items():
            if rel == "anchor":
                continue
            for link in links:
                href = link["href"]
                if not href.startswith(site_prefix):
                    continue
                rel_path = href[len(site_prefix):]
                assert rel_path == "" or (PUBLIC / rel_path).is_file(), (
                    f"catalog target missing from public/: {href}"
                )


def test_deployed_server_json_matches_root():
    deployed = PUBLIC / "server.json"
    assert deployed.is_file(), "public/server.json must exist"
    assert json.loads(deployed.read_text(encoding="utf-8")) == json.loads(
        (REPO_ROOT / "server.json").read_text(encoding="utf-8")
    )
