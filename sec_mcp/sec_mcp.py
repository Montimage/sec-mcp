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

class SecMCP:
    def __init__(self):
        self.storage = Storage()
        self.updater = BlacklistUpdater(self.storage)

    def check(self, value: str) -> CheckResult:
        """Check a single value against the blacklist."""
        if self.storage.is_blacklisted(value):
            source = self.storage.get_blacklist_source(value)
            return CheckResult(
                blacklisted=True,
                explanation=f"Blacklisted by {source}"
            )
        return CheckResult(
            blacklisted=False,
            explanation="Not blacklisted"
        )

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
