"""robots.txt and sitemap.xml of the GitHub Pages landing site.

Issue #137 asks for a valid RFC 9309 ``/robots.txt`` with explicit
``User-agent`` groups and allow/disallow rules; issue #138 asks for a
``/sitemap.xml`` listing canonical URLs, kept updated on publish and
referenced from ``robots.txt``. Both files live in
``react-landing-page/public/`` and deploy to ``/sec-mcp/…``. These tests pin
that surface: the robots groups are well-formed, the sitemap parses and
carries the canonical URL, the ``Sitemap:`` line points at it, and the
prerender build step re-stamps ``<lastmod>`` so the deployed sitemap stays
fresh.
"""

import re
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LANDING = REPO_ROOT / "react-landing-page"
PUBLIC = LANDING / "public"
ROBOTS = PUBLIC / "robots.txt"
SITEMAP = PUBLIC / "sitemap.xml"
PRERENDER = LANDING / "scripts" / "prerender.mjs"
SITE_BASE = "https://montimage.github.io/sec-mcp"
SITEMAP_URL = f"{SITE_BASE}/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


def _robots():
    assert ROBOTS.is_file(), "public/robots.txt must exist"
    return ROBOTS.read_text(encoding="utf-8")


def _sitemap_root():
    assert SITEMAP.is_file(), "public/sitemap.xml must exist"
    return ET.fromstring(SITEMAP.read_text(encoding="utf-8"))


def _groups(text):
    """Parse robots.txt into RFC 9309 groups: user-agent lines + rules."""
    groups = []
    current = {"agents": [], "rules": []}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()  # strip comments
        if not line:
            continue
        field, sep, value = line.partition(":")
        assert sep, f"robots.txt line is not 'field: value': {raw!r}"
        field = field.strip().lower()
        if field == "user-agent":
            if current["rules"]:  # a group ends when agents restart
                groups.append(current)
                current = {"agents": [], "rules": []}
            current["agents"].append(value.strip())
        elif field in ("allow", "disallow"):
            current["rules"].append((field, value.strip()))
        elif field == "sitemap":
            continue  # non-group record, asserted separately
    groups.append(current)
    return [g for g in groups if g["agents"]]


def test_robots_txt_is_plain_text_with_wildcard_allow():
    text = _robots()
    assert "\x00" not in text, "robots.txt must be plain text"
    groups = _groups(text)
    assert groups, "robots.txt must contain at least one user-agent group"
    wildcard = next(
        (g for g in groups if "*" in g["agents"]),
        None,
    )
    assert wildcard is not None, "robots.txt must have a 'User-agent: *' group"
    assert ("allow", "/") in wildcard["rules"], (
        "the wildcard group must allow crawling ('Allow: /')"
    )


def test_robots_txt_groups_all_carry_rules():
    for group in _groups(_robots()):
        assert group["rules"], (
            f"group {group['agents']} has no Allow/Disallow rules (RFC 9309)"
        )


def test_robots_txt_references_sitemap():
    assert f"Sitemap: {SITEMAP_URL}" in _robots(), (
        f"robots.txt must carry 'Sitemap: {SITEMAP_URL}'"
    )


def test_sitemap_is_valid_xml_with_sitemaps_namespace():
    root = _sitemap_root()
    assert root.tag == f"{{{SITEMAP_NS}}}urlset"


def test_sitemap_lists_canonical_url():
    locs = [
        el.text or "" for el in _sitemap_root().iter(f"{{{SITEMAP_NS}}}loc")
    ]
    assert f"{SITE_BASE}/" in locs, "sitemap must list the canonical site URL"
    for loc in locs:
        assert loc.startswith(f"{SITE_BASE}/"), (
            f"sitemap <loc> is outside the site base: {loc}"
        )


def test_sitemap_lastmod_is_a_valid_recent_date():
    lastmods = [
        el.text or "" for el in _sitemap_root().iter(f"{{{SITEMAP_NS}}}lastmod")
    ]
    assert lastmods, "every <url> should carry a <lastmod>"
    for value in lastmods:
        parsed = date.fromisoformat(value)  # raises on malformed/empty dates
        assert parsed <= date.today(), f"lastmod in the future: {value}"


def test_prerender_stamps_sitemap_lastmod_on_build():
    """Issue #138 requires the sitemap to stay updated on publish."""
    script = PRERENDER.read_text(encoding="utf-8")
    assert "sitemap.xml" in script, (
        "prerender.mjs must write dist/sitemap.xml at build time"
    )
    assert re.search(r"lastmod", script), (
        "prerender.mjs must refresh <lastmod> with the build date"
    )
