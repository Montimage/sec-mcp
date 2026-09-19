"""Markdown alternate surface of the GitHub Pages landing site.

Issue #139 asks for ``Accept: text/markdown`` content negotiation: a request
carrying that header should get a markdown rendition of the page with
``Content-Type: text/markdown``. GitHub Pages serves static files only — it
cannot inspect ``Accept:`` headers and cannot emit custom response headers
(``x-markdown-tokens`` included), so a negotiated response is impossible on
this host. The shipped fallback is a real markdown mirror at
``/sec-mcp/index.md`` (Pages serves ``.md`` as ``text/markdown``), advertised
through every in-document channel agents read: ``<link rel="alternate"
type="text/markdown">``, ``rel="service-doc"``, ``llms.txt``, the RFC 9727
api-catalog and the sitemap.

``index.md`` is hand-maintained, so the real risk is silent drift from the
React-rendered page it mirrors. These tests pin the mirror: it exists, it is
linked from ``<head>``, ``llms.txt`` and the sitemap, and its content stays in
sync with the JSX sources of record (feeds, Python API surface, MCP tools,
install commands, outbound links, title).
"""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LANDING = REPO_ROOT / "react-landing-page"
INDEX_HTML = LANDING / "index.html"
PUBLIC = LANDING / "public"
INDEX_MD = PUBLIC / "index.md"
LLMS_TXT = PUBLIC / "llms.txt"
SITEMAP = PUBLIC / "sitemap.xml"
CONFIG = REPO_ROOT / "sec_mcp" / "config.json"
COMPONENTS = LANDING / "src" / "components"
SITE_BASE = "https://montimage.github.io/sec-mcp"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


def _index_md():
    assert INDEX_MD.is_file(), "public/index.md must exist — it is the markdown mirror"
    return INDEX_MD.read_text(encoding="utf-8")


def _normalized(text):
    """Lowercase alphanumeric projection — feed names squash differently
    between config.json ('SpamhausDROP') and prose ('Spamhaus DROP')."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _jsx_names(component, marker):
    """Pull ``name: '…'`` entries out of the array starting at ``marker``."""
    source = (COMPONENTS / component).read_text(encoding="utf-8")
    start = source.index(marker)
    end = source.index("];", start)
    return re.findall(r"name:\s*'([a-zA-Z_]+)'", source[start:end])


def test_index_md_is_a_markdown_document():
    text = _index_md()
    assert text.startswith("# "), "index.md must open with an H1"
    assert "\n## " in text, "index.md must carry section headings"
    assert len(text) > 1000, "index.md should be a real rendition, not a stub"


def test_head_alternate_points_at_a_real_markdown_file():
    head = INDEX_HTML.read_text(encoding="utf-8")
    match = re.search(
        r'<link\s+rel="alternate"\s+type="text/markdown"\s+href="([^"]+)"', head
    )
    assert match, 'index.html must carry <link rel="alternate" type="text/markdown">'
    href = match.group(1)
    assert href.startswith("/sec-mcp/"), f"alternate href must be site-relative: {href}"
    target = PUBLIC / href[len("/sec-mcp/") :]
    assert target.is_file(), f"markdown alternate target missing: {href}"
    assert target.suffix == ".md", "the alternate rendition must be markdown"


def test_llms_txt_advertises_the_markdown_mirror():
    text = LLMS_TXT.read_text(encoding="utf-8")
    assert f"{SITE_BASE}/index.md" in text, (
        "llms.txt must link the markdown mirror so agents can discover it"
    )


def test_sitemap_lists_the_markdown_mirror():
    root = ET.fromstring(SITEMAP.read_text(encoding="utf-8"))
    locs = [el.text or "" for el in root.iter(f"{{{SITEMAP_NS}}}loc")]
    assert f"{SITE_BASE}/index.md" in locs, (
        "sitemap.xml must list the markdown mirror for crawler discovery"
    )


def test_index_md_h1_matches_the_page_title():
    head = INDEX_HTML.read_text(encoding="utf-8")
    og = re.search(r'property="og:title"\s+content="([^"]+)"', head)
    assert og, "index.html must carry an og:title"
    h1 = _index_md().splitlines()[0].lstrip("# ").strip()
    assert h1 == og.group(1), (
        f"index.md H1 {h1!r} drifted from the page title {og.group(1)!r}"
    )


def test_index_md_mirrors_every_blacklist_feed():
    """Every feed in sec_mcp/config.json must appear in the markdown table."""
    feeds = json.loads(CONFIG.read_text(encoding="utf-8"))["blacklist_sources"]
    body = _normalized(_index_md())
    missing = [name for name in feeds if _normalized(name) not in body]
    assert not missing, f"index.md dropped feeds present in config.json: {missing}"


def test_index_md_mirrors_the_python_api_surface():
    methods = _jsx_names("APIReference.jsx", "const METHODS")
    assert len(methods) >= 8, "APIReference.jsx METHODS array not parsed"
    text = _index_md()
    missing = [m for m in methods if not re.search(rf"`{m}\(", text)]
    assert not missing, f"index.md dropped API methods shown on the page: {missing}"


def test_index_md_mirrors_the_mcp_tool_surface():
    tools = _jsx_names("MCPServer.jsx", "const mcpTools")
    assert len(tools) >= 6, "MCPServer.jsx mcpTools array not parsed"
    text = _index_md()
    missing = [t for t in tools if not re.search(rf"`{t}\(", text)]
    assert not missing, f"index.md dropped MCP tools shown on the page: {missing}"


def test_index_md_carries_the_core_install_commands():
    text = _index_md()
    for command in ("pip install sec-mcp", "sec-mcp update", "sec-mcp check"):
        assert command in text, f"index.md must show the install flow: {command!r}"


def test_index_md_carries_the_footer_links():
    footer = (COMPONENTS / "Footer.jsx").read_text(encoding="utf-8")
    hrefs = re.findall(r"href:\s*'(https?://[^']+)'", footer)
    text = _index_md()
    missing = [h for h in hrefs if h not in text]
    assert not missing, f"index.md dropped links the page footer carries: {missing}"
