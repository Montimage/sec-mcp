import asyncio
import csv
import httpx
from datetime import datetime
import schedule
import threading
from typing import List, Dict
from .storage import Storage
from .utility import validate_input, setup_logging
import logging

class BlacklistUpdater:
    """Handles downloading and updating blacklists from various sources."""
    
    SOURCES = {
        "OpenPhish": "https://openphish.com/feed.txt",
        "PhishStats": "https://phishstats.info/phish_score.csv",
        "URLhaus": "https://urlhaus.abuse.ch/downloads/text/"
    }

    def __init__(self, storage: Storage):
        self.storage = storage
        setup_logging()
        self.logger = logging.getLogger("sec_mcp.update_blacklist")
        self._start_scheduler()

    def _start_scheduler(self):
        """Start the daily update scheduler in a background thread."""
        def run_scheduler():
            schedule.every().day.at("00:00").do(self.update_all)
            while True:
                schedule.run_pending()
                asyncio.run(asyncio.sleep(60))

        thread = threading.Thread(target=run_scheduler, daemon=True)
        thread.start()

    async def update_all(self):
        """Update blacklists from all sources."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            tasks = []
            for source, url in self.SOURCES.items():
                tasks.append(self._update_source(client, source, url))
            await asyncio.gather(*tasks)

    async def _update_source(self, client: httpx.AsyncClient, source: str, url: str):
        """Update blacklist from a single source."""
        try:
            response = await client.get(url)
            response.raise_for_status()
            content = response.text
            entries = []
            if source == "PhishStats":
                try:
                    reader = csv.DictReader(content.splitlines())
                    entries = [(row['url'], source) for row in reader if validate_input(row.get('url', ''))]
                except Exception as e:
                    self.logger.error(f"CSV parsing error for {source}: {e}")
                    return
            else:
                entries = [(line.strip(), source) for line in content.splitlines() 
                          if line.strip() and validate_input(line.strip())]
            if not entries:
                self.logger.warning(f"No valid entries found for {source} during update.")
            self.storage.add_entries(entries)
            self.storage.log_update(source, len(entries))
            self.logger.info(f"Updated {source}: {len(entries)} entries.")
        except httpx.RequestError as e:
            self.logger.error(f"Network error updating {source}: {e}")
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error updating {source}: {e.response.status_code}")
        except Exception as e:
            self.logger.error(f"Unexpected error updating {source}: {e}")

    def force_update(self):
        """Force an immediate update of all blacklists."""
        asyncio.run(self.update_all())
