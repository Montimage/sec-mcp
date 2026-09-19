"""Statistics and reporting half of ``HybridStorage``.

Every method delegates to the composed ``EntryIndex`` (in-memory counts)
or ``SQLiteStore`` (update history), so the numbers always reflect the same
snapshot the lookups use. Mixed into ``sec_mcp.storage_v2.HybridStorage``.
"""

from datetime import datetime
from typing import Dict, List


class StorageStatsMixin:
    """Entry counts, per-source stats, sampling and update-history queries.

    Resolves ``self._index``, ``self._db``, ``self._lock`` and
    ``self.count_entries`` on the ``HybridStorage`` instance it is mixed into.
    """

    def count_entries(self) -> int:
        """Get total count of all entries (instant from memory)."""
        return self._index.count()

    def get_source_counts(self) -> Dict[str, int]:
        """Count entries per source from memory."""
        return self._index.source_counts()

    def get_source_type_counts(self) -> Dict[str, dict]:
        """Get breakdown of domain/url/ip entries per source."""
        return self._index.source_type_counts()

    def get_active_sources(self) -> List[str]:
        """Get list of active sources."""
        return self._index.active_sources()

    def sample_entries(self, count: int = 10) -> List[str]:
        """Return a random sample of entries.

        Reservoir sampling over the in-memory pools: uniform selection with
        O(count) extra space, so sampling never materializes a list of all
        entries even on a multi-hundred-thousand-entry store.
        """
        with self._lock:
            return self._index.sample(count)

    def get_last_update(self) -> datetime:
        """Get timestamp of last update from database."""
        result = self._db.get_last_update()
        return datetime.fromisoformat(result) if result else datetime.min

    def get_last_update_per_source(self) -> Dict[str, str]:
        """Get last update timestamp for each source."""
        return self._db.get_last_update_per_source()

    def get_update_history(self, source: str = None, start: str = None, end: str = None) -> list:
        """Return update history records from database."""
        return self._db.get_update_history(source=source, start=start, end=end)

    def log_update(self, source: str, entry_count: int):
        """Log an update to the database."""
        self._db.log_update(source, entry_count)
