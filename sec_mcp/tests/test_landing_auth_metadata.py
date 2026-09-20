"""Agent-authentication metadata of the GitHub Pages landing site.

Issues #147–#150 (epic #135) ask for the agent-auth discovery surface the
isitagentready.com guides describe:

- ``auth.md``                               — Auth.md statement for agent
  registration; with no OAuth metadata available the guide requires it to be
  self-contained (audience, registration endpoints, supported methods,
  credential use)                                                    (#147)
- ``.well-known/oauth-protected-resource``  — RFC 9728 Protected Resource
  Metadata; ``authorization_servers`` is the empty list because no
  authorization server exists                                        (#150)
- ``.well-known/oauth-authorization-server`` / ``openid-configuration`` —
  deliberately NOT published: RFC 8414 / OIDC discovery metadata describes a
  live issuer, and sec-mcp runs none, so any such document would fabricate
  endpoints; the decision is recorded in ``docs/DEPLOYMENT.md``        (#149)

All files live under ``react-landing-page/public/`` and deploy to
``/sec-mcp/…``. These tests pin that the published documents parse, carry
the fields their specs require, describe the no-auth posture truthfully (no
fabricated endpoints), stay cross-linked from the api-catalog and llms.txt,
and that ``docs/DEPLOYMENT.md`` keeps the rationale for the absent AS
metadata.
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LANDING = REPO_ROOT / "react-landing-page"
PUBLIC = LANDING / "public"
WELL_KNOWN = PUBLIC / ".well-known"
DEPLOYMENT = REPO_ROOT / "docs" / "DEPLOYMENT.md"
SITE_BASE = "https://montimage.github.io/sec-mcp"

AUTH_MD = PUBLIC / "auth.md"
PRM = WELL_KNOWN / "oauth-protected-resource"
API_CATALOG = WELL_KNOWN / "api-catalog"
LLMS_TXT = PUBLIC / "llms.txt"


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


# --- #147: auth.md -----------------------------------------------------------


def test_auth_md_served_from_site_root():
    assert AUTH_MD.is_file(), "public/auth.md must exist — it deploys to /sec-mcp/auth.md"
    first_heading = next(
        line for line in AUTH_MD.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    assert first_heading.startswith("# ") and "auth.md" in first_heading, (
        "auth.md must open with an H1 containing 'auth.md' (guide requirement)"
    )


def test_auth_md_is_a_self_contained_no_auth_statement():
    """The guide's no-OAuth path: identify the audience, document registration
    endpoints (none), list supported methods (none), explain credential use."""
    text = AUTH_MD.read_text(encoding="utf-8").lower()
    assert re.search(r"audience.*agent|agent.*audience", text, re.S), (
        "auth.md must identify the agent audience"
    )
    assert "no remote http api" in text or "no protected" in text, (
        "auth.md must state there is no protected HTTP surface"
    )
    assert re.search(r"nothing to register|no registration|no .*provisioning", text), (
        "auth.md must document that no registration/provisioning endpoint exists"
    )
    assert re.search(r"supported methods.*none|- \*\*none\*\*", text, re.S), (
        "auth.md must list supported methods (none)"
    )
    assert "no credentials" in text, "auth.md must explain credential use (none)"


def test_auth_md_references_protected_resource_metadata():
    text = AUTH_MD.read_text(encoding="utf-8")
    assert "/.well-known/oauth-protected-resource" in text, (
        "auth.md must point agents at the RFC 9728 metadata document"
    )
    assert "oauth-authorization-server" in text, (
        "auth.md must state that no AS metadata is published (and why)"
    )


# --- #150: RFC 9728 Protected Resource Metadata -------------------------------


def test_prm_is_valid_rfc9728_document():
    prm = _json(PRM)
    assert prm.get("resource") == f"{SITE_BASE}/", (
        "resource must be the deployed service identifier URL (https)"
    )
    assert isinstance(prm.get("authorization_servers"), list), (
        "authorization_servers must be a JSON array of issuer identifiers"
    )
    assert isinstance(prm.get("scopes_supported"), list)
    assert isinstance(prm.get("bearer_methods_supported"), list)


def test_prm_declares_no_authorization_servers():
    """The truthful statement for a service with no auth: zero issuers."""
    prm = _json(PRM)
    assert prm["authorization_servers"] == [], (
        "authorization_servers must be empty — fabricating an issuer would lie"
    )
    assert prm["bearer_methods_supported"] == []


def test_prm_fabricates_no_oauth_endpoints():
    """No endpoint keys may appear anywhere in the document — none exist."""
    text = PRM.read_text(encoding="utf-8")
    for field in (
        "authorization_endpoint",
        "token_endpoint",
        "jwks_uri",
        "registration_endpoint",
        "issuer",
    ):
        assert f'"{field}"' not in text, f"PRM must not fabricate {field!r}"


def test_prm_documentation_resolves_to_deployed_auth_md():
    doc_url = _json(PRM).get("resource_documentation")
    assert doc_url == f"{SITE_BASE}/auth.md", (
        "resource_documentation must point at the deployed auth.md"
    )
    rel = doc_url[len(f"{SITE_BASE}/") :]
    assert (PUBLIC / rel).is_file(), f"resource_documentation must deploy: {doc_url}"


# --- #149: no authorization-server metadata (honest 404) -----------------------


def test_no_authorization_server_metadata_is_published():
    """RFC 8414 / OIDC discovery docs describe a live issuer; sec-mcp has none,
    so the well-known paths must 404 rather than serve fabricated metadata.
    Revisit if a real authorization server is ever added."""
    for name in ("oauth-authorization-server", "openid-configuration"):
        assert not (WELL_KNOWN / name).exists(), (
            f"{name} now exists — only publish it once a real issuer exists "
            "(see 'Agent authentication' in docs/DEPLOYMENT.md)"
        )


def test_deployment_docs_record_the_no_auth_posture():
    text = DEPLOYMENT.read_text(encoding="utf-8")
    assert "### Agent authentication" in text, (
        "DEPLOYMENT.md must carry the agent-authentication note"
    )
    for needle in (
        "auth.md",
        "oauth-protected-resource",
        "oauth-authorization-server",
        "authorization server",
    ):
        assert needle in text, f"DEPLOYMENT.md must document {needle!r}"
    assert re.search(r"no authorization server", text, re.I), (
        "the note must state plainly that no authorization server exists"
    )


# --- shared surface: api-catalog + llms.txt cross-links ------------------------


def test_api_catalog_references_auth_metadata():
    links = {(rel, link["href"]) for _, rel, link in _catalog_links()}
    assert ("service-doc", f"{SITE_BASE}/auth.md") in links
    assert ("describedby", f"{SITE_BASE}/.well-known/oauth-protected-resource") in links


def test_llms_txt_links_auth_md():
    text = LLMS_TXT.read_text(encoding="utf-8")
    assert f"{SITE_BASE}/auth.md" in text, (
        "llms.txt must link auth.md so agents can discover it"
    )
