"""Well-known agent-discovery manifests of the GitHub Pages landing site.

Issues #143–#146 and #148 (epic #135) ask for the machine-readable manifests
an agent-readiness scan looks for under ``/.well-known/``:

- ``agent-card.json``        — A2A Agent Card (name, version, interfaces,
  capabilities, skills)                                       (#143)
- ``agent-skills/index.json`` — agentskills.io discovery index listing skill
  artifacts with sha256 digests                               (#144)
- ``api-catalog``            — RFC 9727 linkset (extended to reference the new
  manifests)                                                  (#145)
- ``ai-catalog.json``        — ARD manifest (specVersion, host, entries that
  point at the sibling manifests)                             (#146)
- ``mcp/server-card.json``   — MCP Server Card (serverInfo, transport,
  capabilities), mirroring the root ``server.json``           (#148)

All files live under ``react-landing-page/public/.well-known/`` and deploy to
``/sec-mcp/.well-known/…``. These tests pin that every manifest parses,
carries the fields its guide requires, and that every same-origin URL it
advertises resolves to a real deployed asset.
"""

import hashlib
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LANDING = REPO_ROOT / "react-landing-page"
INDEX_HTML = LANDING / "index.html"
PUBLIC = LANDING / "public"
WELL_KNOWN = PUBLIC / ".well-known"
SITE_BASE = "https://montimage.github.io/sec-mcp"

AGENT_CARD = WELL_KNOWN / "agent-card.json"
SKILLS_INDEX = WELL_KNOWN / "agent-skills" / "index.json"
API_CATALOG = WELL_KNOWN / "api-catalog"
AI_CATALOG = WELL_KNOWN / "ai-catalog.json"
SERVER_CARD = WELL_KNOWN / "mcp" / "server-card.json"
ROOT_SERVER_JSON = REPO_ROOT / "server.json"
ROBOTS = PUBLIC / "robots.txt"

SKILLS_SCHEMA = "https://schemas.agentskills.io/discovery/0.2.0/schema.json"


def _json(path):
    assert path.is_file(), f"{path.relative_to(REPO_ROOT)} must exist"
    return json.loads(path.read_text(encoding="utf-8"))


def _catalog_links():
    """Flatten {anchor, rel, link} triples out of the RFC 9727 linkset."""
    for entry in _json(API_CATALOG)["linkset"]:
        for rel, links in entry.items():
            if rel == "anchor":
                continue
            for link in links:
                yield entry.get("anchor"), rel, link


def _public_target(href):
    """Map a same-origin site URL onto public/; None when not same-origin."""
    prefix = f"{SITE_BASE}/"
    if not href.startswith(prefix):
        return None
    rel = href[len(prefix) :]
    return PUBLIC / rel if rel else PUBLIC / "index.html"


# --- #143: A2A Agent Card -------------------------------------------------


def test_agent_card_identity_fields():
    card = _json(AGENT_CARD)
    for field in ("name", "version", "description"):
        assert card.get(field), f"agent-card.json must carry a non-empty {field!r}"


def test_agent_card_supported_interfaces():
    card = _json(AGENT_CARD)
    interfaces = card.get("supportedInterfaces")
    assert isinstance(interfaces, list) and interfaces, (
        "supportedInterfaces must be a non-empty list"
    )
    for iface in interfaces:
        assert iface.get("url", "").startswith("https://"), (
            "each interface needs a service URL"
        )
        assert iface.get("protocolBinding"), (
            "each interface needs a transport protocol binding"
        )
        target = _public_target(iface["url"])
        assert target is not None and target.is_file(), (
            f"interface URL must resolve to a deployed asset: {iface['url']}"
        )


def test_agent_card_capabilities_and_skills():
    card = _json(AGENT_CARD)
    assert isinstance(card.get("capabilities"), dict) and card["capabilities"], (
        "capabilities must be a non-empty object"
    )
    skills = card.get("skills")
    assert isinstance(skills, list) and skills, "skills must be a non-empty list"
    for skill in skills:
        for field in ("id", "name", "description"):
            assert skill.get(field), f"skill is missing {field!r}: {skill}"


# --- #144: agent skills discovery index ------------------------------------


def test_skills_index_schema_and_shape():
    doc = _json(SKILLS_INDEX)
    assert doc.get("$schema") == SKILLS_SCHEMA
    skills = doc.get("skills")
    assert isinstance(skills, list) and skills, "skills must be a non-empty list"
    for skill in skills:
        for field in ("name", "type", "description", "url", "digest"):
            assert skill.get(field), f"skill entry is missing {field!r}: {skill}"
        assert skill["type"] in ("skill-md", "archive")
        assert re.fullmatch(r"[a-z0-9-]+", skill["name"]), (
            f"skill name must be lowercase alphanumeric + hyphens: {skill['name']}"
        )


def test_skills_index_digests_match_artifacts():
    """Each digest must be the sha256 of the on-disk artifact it names."""
    for skill in _json(SKILLS_INDEX)["skills"]:
        algo, _, hexdigest = skill["digest"].partition(":")
        assert algo == "sha256" and re.fullmatch(r"[0-9a-f]{64}", hexdigest), (
            f"digest must be 'sha256:{{hex}}': {skill['digest']}"
        )
        artifact = _public_target(skill["url"])
        assert artifact is not None and artifact.is_file(), (
            f"skill artifact must deploy from public/: {skill['url']}"
        )
        actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
        assert actual == hexdigest, (
            f"digest for {skill['name']} is stale — recompute sha256 of {artifact.name}"
        )


# --- #145: API catalog (extension over the #136 linkset) --------------------


def test_api_catalog_references_new_manifests():
    hrefs = {link["href"] for _, _, link in _catalog_links()}
    service_desc = {
        link["href"] for _, rel, link in _catalog_links() if rel == "service-desc"
    }
    describedby = {
        link["href"] for _, rel, link in _catalog_links() if rel == "describedby"
    }
    assert f"{SITE_BASE}/.well-known/mcp/server-card.json" in service_desc
    assert f"{SITE_BASE}/.well-known/agent-card.json" in service_desc
    assert f"{SITE_BASE}/.well-known/ai-catalog.json" in describedby
    assert f"{SITE_BASE}/.well-known/agent-skills/index.json" in describedby
    assert f"{SITE_BASE}/server.json" in hrefs, "existing service-desc must stay"


# --- #146: ARD manifest ------------------------------------------------------


def test_ai_catalog_header_fields():
    doc = _json(AI_CATALOG)
    assert isinstance(doc.get("specVersion"), str) and doc["specVersion"]
    host = doc.get("host")
    assert isinstance(host, dict), "host must be an object"
    assert host.get("displayName"), "host.displayName is required"
    assert host.get("identifier"), "host.identifier is required"


def test_ai_catalog_entries_are_wellformed():
    doc = _json(AI_CATALOG)
    entries = doc.get("entries")
    assert isinstance(entries, list) and entries, "entries must be non-empty"
    for entry in entries:
        assert entry.get("identifier", "").startswith(
            "urn:air:montimage.github.io:"
        ), f"entry identifier must be a urn:air under our host: {entry}"
        assert entry.get("displayName"), f"entry missing displayName: {entry}"
        assert entry.get("type"), f"entry missing type media type: {entry}"
        # spec §3.4: exactly one of url / data.
        assert ("url" in entry) != ("data" in entry), (
            f"entry must carry exactly one of url/data: {entry}"
        )
        queries = entry.get("representativeQueries")
        assert isinstance(queries, list) and 2 <= len(queries) <= 5, (
            f"entry needs 2–5 representativeQueries: {entry}"
        )


def test_ai_catalog_entry_urls_resolve_to_deployed_assets():
    for entry in _json(AI_CATALOG)["entries"]:
        if "url" not in entry:
            continue
        target = _public_target(entry["url"])
        assert target is not None and target.is_file(), (
            f"catalog entry URL must resolve to a deployed asset: {entry['url']}"
        )


# --- #148: MCP Server Card ---------------------------------------------------


def test_server_card_required_fields():
    card = _json(SERVER_CARD)
    info = card.get("serverInfo")
    assert isinstance(info, dict), "serverInfo must be an object"
    assert info.get("name") and info.get("version"), (
        "serverInfo needs name and version"
    )
    transport = card.get("transport")
    assert isinstance(transport, dict) and transport.get("endpoint"), (
        "transport must declare an endpoint"
    )
    capabilities = card.get("capabilities")
    assert isinstance(capabilities, dict) and capabilities, (
        "capabilities must be a non-empty object"
    )


def test_server_card_mirrors_root_server_json():
    card = _json(SERVER_CARD)
    root = _json(ROOT_SERVER_JSON)
    assert card["name"] == root["name"]
    assert card["version"] == root["version"]
    assert card["serverInfo"]["version"] == root["version"]
    assert card["description"] == root["description"]


def test_server_card_declares_stdio_transport():
    card = _json(SERVER_CARD)
    transport = card["transport"]
    assert transport.get("type") == "stdio", (
        "sec-mcp serves MCP over stdio only — no remote endpoint may be claimed"
    )
    assert transport.get("command") and isinstance(transport.get("args"), list)


# --- shared surface: HTML link + robots.txt agentmap -------------------------


def test_head_links_to_ai_catalog():
    head = INDEX_HTML.read_text(encoding="utf-8")
    assert 'rel="ai-catalog"' in head, "index.html must link the ARD manifest"
    assert 'href="/sec-mcp/.well-known/ai-catalog.json"' in head


def test_robots_txt_carries_agentmap_directive():
    text = ROBOTS.read_text(encoding="utf-8")
    assert (
        f"Agentmap: {SITE_BASE}/.well-known/ai-catalog.json" in text
    ), "robots.txt must carry the ARD Agentmap directive"
