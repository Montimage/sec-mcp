"""AI-crawler rules and Content Signals in the landing site's robots.txt.

Issue #141 asks for ``Content-Signal`` directives declaring the site's
preferences for ``ai-train``, ``search`` and ``ai-input`` (guide:
isitagentready.com/.well-known/agent-skills/content-signals/SKILL.md, IETF
draft-romm-aipref-contentsignals). Issue #142 asks for explicit ``User-agent``
entries for AI crawlers (guide: …/agent-skills/ai-rules/SKILL.md) — a wildcard
``User-agent: *`` group alone is not sufficient.

These tests pin that surface in ``react-landing-page/public/robots.txt``:
every group carries a Content-Signal covering the three preference keys, the
values are well-formed yes/no tokens, and each crawler named by the guide has
an explicit User-agent entry.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROBOTS = REPO_ROOT / "react-landing-page" / "public" / "robots.txt"

# Preference keys the content-signals guide requires to be declared.
REQUIRED_SIGNAL_KEYS = {"ai-train", "search", "ai-input"}

# AI crawlers the ai-rules guide names; each needs an explicit User-agent.
GUIDE_AI_CRAWLERS = {
    "GPTBot",
    "OAI-SearchBot",
    "Claude-Web",
    "Google-Extended",
    "Amazonbot",
    "anthropic-ai",
    "Bytespider",
    "CCBot",
    "Applebot-Extended",
}


def _robots():
    assert ROBOTS.is_file(), "public/robots.txt must exist"
    return ROBOTS.read_text(encoding="utf-8")


def _groups(text):
    """Parse robots.txt into RFC 9309 groups incl. Content-Signal lines."""
    groups = []
    current = {"agents": [], "rules": [], "signals": []}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()  # strip comments
        if not line:
            continue
        field, sep, value = line.partition(":")
        assert sep, f"robots.txt line is not 'field: value': {raw!r}"
        field = field.strip().lower()
        if field == "user-agent":
            if current["rules"] or current["signals"]:
                groups.append(current)
                current = {"agents": [], "rules": [], "signals": []}
            current["agents"].append(value.strip())
        elif field in ("allow", "disallow"):
            current["rules"].append((field, value.strip()))
        elif field == "content-signal":
            current["signals"].append(value.strip())
        elif field == "sitemap":
            continue  # non-group record, asserted elsewhere
    groups.append(current)
    return [g for g in groups if g["agents"]]


def _signal_map(group):
    """Flatten a group's Content-Signal lines into {key: value}."""
    signals = {}
    for line in group["signals"]:
        for pair in line.split(","):
            key, sep, value = pair.partition("=")
            assert sep, f"Content-Signal pair is not 'key=value': {pair!r}"
            signals[key.strip().lower()] = value.strip().lower()
    return signals


def test_every_group_declares_required_content_signals():
    """Issue #141: ai-train, search and ai-input declared in each group."""
    groups = _groups(_robots())
    assert groups, "robots.txt must contain at least one user-agent group"
    for group in groups:
        signals = _signal_map(group)
        missing = REQUIRED_SIGNAL_KEYS - signals.keys()
        assert not missing, (
            f"group {group['agents']} lacks Content-Signal keys: {missing}"
        )


def test_content_signal_values_are_well_formed():
    """Content-Signal values must be yes/no tokens per the draft."""
    for group in _groups(_robots()):
        for key, value in _signal_map(group).items():
            assert value in ("yes", "no"), (
                f"Content-Signal {key}={value!r} is not a yes/no token"
            )


def test_content_signal_policy_is_permissive():
    """The site welcomes AI use — signals must read 'yes' (#141 policy)."""
    wildcard = next(
        g for g in _groups(_robots()) if "*" in g["agents"]
    )
    signals = _signal_map(wildcard)
    for key in REQUIRED_SIGNAL_KEYS:
        assert signals[key] == "yes", (
            f"wildcard Content-Signal {key} should be 'yes' — the site "
            "explicitly welcomes AI training, search and input"
        )


def test_ai_crawlers_from_guide_have_user_agent_entries():
    """Issue #142: every crawler named by the guide appears explicitly."""
    agents = {a for g in _groups(_robots()) for a in g["agents"]}
    missing = GUIDE_AI_CRAWLERS - agents
    assert not missing, f"missing AI-crawler User-agent entries: {missing}"


def test_ai_crawler_group_allows_crawling():
    """Issue #142: explicit AI entries carry an allow/disallow rule."""
    ai_group = next(
        (g for g in _groups(_robots()) if "GPTBot" in g["agents"]),
        None,
    )
    assert ai_group is not None, "robots.txt must have an AI-crawler group"
    assert ("allow", "/") in ai_group["rules"], (
        "the AI-crawler group must allow crawling ('Allow: /')"
    )
