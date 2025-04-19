from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from .storage import Storage
from .update_blacklist import BlacklistUpdater

@dataclass
class CheckResult:
    blacklisted: bool
    explanation: str

    def to_json(self):
        return {
            "is_safe": not self.blacklisted,
            "explain": self.explanation
        }

@dataclass
class StatusInfo:
    entry_count: int
    last_update: datetime
    sources: List[str]
    server_status: str

    def to_json(self):
        return {
            "entry_count": self.entry_count,
            "last_update": self.last_update.isoformat(),
            "sources": self.sources,
            "server_status": self.server_status
        }

import os
import json

class SecMCP:
    def __init__(self, db_path=None):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        with open(config_path) as f:
            config = json.load(f)
        self.storage = Storage(db_path=db_path)
        self.updater = BlacklistUpdater(self.storage)

    def check(self, value: str) -> CheckResult:
        """Check a single value (domain, URL, or IP) against the blacklist, following rules:
        - If a domain is blacklisted, all URLs from that domain or its subdomains are considered blacklisted.
        - If a URL is blacklisted, its domain is NOT considered blacklisted.
        """
        value = value.strip()
        if self.is_ip(value):
            if self.storage.is_ip_blacklisted(value):
                src = self.storage.get_ip_blacklist_source(value)
                return CheckResult(True, f"Blacklisted IP by {src}")
            return CheckResult(False, "Not blacklisted")
        elif self.is_url(value):
            # 1. If the URL itself is blacklisted, return blacklisted (do NOT check domain as blacklisted by URL)
            if self.storage.is_url_blacklisted(value):
                src = self.storage.get_url_blacklist_source(value)
                return CheckResult(True, f"Blacklisted URL by {src}")
            # 2. If the domain or any parent domain is blacklisted, the URL is also blacklisted
            domain = self.extract_domain(value)
            if domain and self.storage.is_domain_blacklisted(domain):
                src = self.storage.get_domain_blacklist_source(domain)
                return CheckResult(True, f"Blacklisted domain by {src}")
            return CheckResult(False, "Not blacklisted")
        elif self.is_domain(value):
            # Only consider domain entries, not URLs
            if self.storage.is_domain_blacklisted(value):
                src = self.storage.get_domain_blacklist_source(value)
                return CheckResult(True, f"Blacklisted domain by {src}")
            return CheckResult(False, "Not blacklisted")
        else:
            return CheckResult(False, "Invalid input type")

    # Note: When adding, only add a domain if it is explicitly blacklisted as a domain; do not add a domain just because a URL is blacklisted.

    def check_domain(self, domain: str) -> CheckResult:
        """Check a domain (and parent domains) against the domain blacklist.
        - Do NOT consider URLs from this domain as evidence of blacklisting the domain.
        """
        if self.storage.is_domain_blacklisted(domain):
            src = self.storage.get_domain_blacklist_source(domain)
            return CheckResult(True, f"Blacklisted domain by {src}")
        return CheckResult(False, "Not blacklisted")

    def check_url(self, url: str) -> CheckResult:
        """Check a URL against the URL and domain blacklist, following rules:
        - If the URL itself is blacklisted, return blacklisted.
        - If the domain or any parent domain is blacklisted, the URL is blacklisted.
        - If only the URL is blacklisted, do NOT consider the domain blacklisted.
        """
        if self.storage.is_url_blacklisted(url):
            src = self.storage.get_url_blacklist_source(url)
            return CheckResult(True, f"Blacklisted URL by {src}")
        domain = self.extract_domain(url)
        if domain and self.storage.is_domain_blacklisted(domain):
            src = self.storage.get_domain_blacklist_source(domain)
            return CheckResult(True, f"Blacklisted domain by {src}")
        return CheckResult(False, "Not blacklisted")

    # Note: When adding, only add a domain if it is explicitly blacklisted as a domain; do not add a domain just because a URL is blacklisted.

    def check_ip(self, ip: str) -> CheckResult:
        """Check an IP against the IP blacklist."""
        if self.storage.is_ip_blacklisted(ip):
            src = self.storage.get_ip_blacklist_source(ip)
            return CheckResult(True, f"Blacklisted IP by {src}")
        return CheckResult(False, "Not blacklisted")

    def check_batch(self, values: List[str]) -> List[CheckResult]:
        """Check multiple values against the blacklist."""
        return [self.check(value) for value in values]

    @staticmethod
    def is_url(value: str) -> bool:
        import re
        return bool(re.match(r'^https?://', value, re.IGNORECASE))

    @staticmethod
    def is_ip(value: str) -> bool:
        import ipaddress
        try:
            ipaddress.ip_address(value)
            return True
        except Exception:
            return False

    @staticmethod
    def is_domain(value: str) -> bool:
        # Heuristic: must not be a URL, must contain at least one dot, and not end with a dot
        if SecMCP.is_url(value) or SecMCP.is_ip(value):
            return False
        value = value.strip()
        return '.' in value and not value.endswith('.')

    @staticmethod
    def extract_domain(url: str) -> Optional[str]:
        import re
        # Remove scheme
        url = re.sub(r'^https?://', '', url, flags=re.IGNORECASE)
        # Remove path/query/fragment
        url = url.split('/', 1)[0].split(':')[0]
        return url if '.' in url else None

    def check_batch(self, values: List[str]) -> List[CheckResult]:
        """Check multiple values against the blacklist."""
        return [self.check(value) for value in values]

    def get_status(self) -> StatusInfo:
        """Get current status of the blacklist service."""
        return StatusInfo(
            entry_count=self.storage.count_entries(),
            last_update=self.storage.get_last_update(),
            sources=self.storage.get_active_sources(),
            server_status="Running (STDIO)"
        )

    def update(self) -> None:
        """Force an immediate update of all blacklists."""
        self.updater.force_update()

    def sample(self, count: int = 10) -> List[str]:
        """Return a random sample of blacklist entries for testing."""
        return self.storage.sample_entries(count)
