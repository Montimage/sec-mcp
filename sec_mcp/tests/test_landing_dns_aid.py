"""DNS-AID platform-block documentation for the GitHub Pages landing site.

Issue #140 asks for DNS for AI Discovery (DNS-AID): ServiceMode
``SVCB``/``HTTPS`` records under ``_agents.montimage.github.io`` in a
DNSSEC-signed zone. That is impossible on GitHub Pages — ``github.io`` is
GitHub's own zone and delegates no DNS control to Pages sites, and this repo
configures no custom domain (``react-landing-page/public/CNAME`` does not
exist). Unlike a static-file fallback, DNS records cannot be expressed as
site files, so the scanner check reports ``fail`` until a custom domain is
adopted.

The in-repo deliverable is the documented status and runbook in
``docs/DEPLOYMENT.md`` ("Agent discovery (DNS-AID)"): it records the block,
names the prerequisite (custom domain + DNSSEC) and keeps the exact records
to publish when that prerequisite lands. These tests pin that note so the
constraint stays documented instead of being silently dropped.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = REPO_ROOT / "docs" / "DEPLOYMENT.md"
CNAME = REPO_ROOT / "react-landing-page" / "public" / "CNAME"
GUIDE_URL = "https://isitagentready.com/.well-known/agent-skills/dns-aid/SKILL.md"


def _deployment_text():
    assert DEPLOYMENT.is_file(), "docs/DEPLOYMENT.md must exist"
    return DEPLOYMENT.read_text(encoding="utf-8")


def _dns_aid_section(text):
    """Slice the 'Agent discovery (DNS-AID)' subsection out of DEPLOYMENT.md."""
    marker = "### Agent discovery (DNS-AID)"
    start = text.index(marker)
    tail = text[start + len(marker) :]
    end = tail.find("\n## ")
    return tail[:end] if end != -1 else tail


def test_no_custom_domain_is_configured():
    """The premise of the block: no CNAME means the site can only ever be
    served from ``*.github.io``, where DNS-AID records cannot be published."""
    assert not CNAME.exists(), (
        "public/CNAME now exists — a custom domain may be configured, so "
        "revisit the DNS-AID note in docs/DEPLOYMENT.md"
    )


def test_deployment_docs_record_dns_aid_block():
    text = _deployment_text()
    assert "DNS-AID" in text, "DEPLOYMENT.md must document DNS-AID"
    section = _dns_aid_section(text)
    assert "github.io" in section, "the note must name the github.io zone"
    assert "custom domain" in section.lower(), (
        "the note must name the prerequisite that unblocks the check"
    )


def test_dns_aid_note_keeps_the_records_runbook():
    section = _dns_aid_section(_deployment_text())
    for needle in ("_agents.", "SVCB", "HTTPS", "DNSSEC", GUIDE_URL):
        assert needle in section, f"DNS-AID note must keep {needle!r}"
