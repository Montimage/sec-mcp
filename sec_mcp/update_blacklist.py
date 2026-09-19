import asyncio
import csv
import json
import logging
import os
import re
import threading
import time
import traceback
from datetime import datetime, timedelta
from ipaddress import ip_address, summarize_address_range
from urllib.parse import urlparse

import httpx
import schedule
from platformdirs import user_cache_dir

from .storage import Storage
from .utility import setup_logging, validate_input


def _feed_cache_dir() -> str:
    override = os.environ.get("MCP_CACHE_DIR")
    if override:
        return override
    return user_cache_dir("sec-mcp", "montimage")


class BlacklistUpdater:
    """Handles downloading and updating blacklists from various sources."""
    
    # Sources loaded from config.json

    def __init__(self, storage: Storage, config_path: str = None):
        self.storage = storage
        setup_logging()
        self.logger = logging.getLogger("sec_mcp.update_blacklist")
        # Load blacklist sources from config.json
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
        with open(config_path, "r") as f:
            config = json.load(f)
        self.sources = config.get("blacklist_sources", {})
        def _limit(key, default):
            try:
                return int(config.get(key, default))
            except (TypeError, ValueError):
                return default
        self.max_feed_bytes = max(1, _limit("max_feed_bytes", 64 * 1024 * 1024))
        self.min_feed_entries = max(0, _limit("min_feed_entries", 1))
        self.max_feed_entries = max(self.min_feed_entries, _limit("max_feed_entries", 500000))
        self.max_range_addresses = max(1, _limit("max_range_addresses", 1 << 16))
        # Minimum seconds between forced updates; a second force_update inside
        # the window is refused without starting any download. 0 disables.
        self.min_update_interval = max(0, _limit("min_update_interval_seconds", 300))
        self._last_force_update = None  # monotonic timestamp of the last attempt
        self._force_update_lock = threading.Lock()
        # Optional sync callable (source, index, total) invoked per source by
        # update_all; the MCP layer uses it to forward progress notifications.
        self.progress_callback = None
        if os.environ.get("MCP_DISABLE_SCHEDULER") != "1":
            self._ensure_scheduler()

    _scheduler = None
    _scheduler_thread = None
    _scheduler_stop = None
    _scheduler_lock = threading.Lock()

    def _ensure_scheduler(self):
        """Register the shared daily job and start the loop thread once.

        The first constructed updater owns the job; later constructions reuse
        it so only one scheduled update exists per process.
        """
        cls = type(self)
        with cls._scheduler_lock:
            if cls._scheduler is None:
                cls._scheduler = schedule.Scheduler()
            if not cls._scheduler.jobs:
                cls._scheduler.every().day.at("00:00").do(
                    lambda: asyncio.run(self.update_all())
                )
            if cls._scheduler_thread is None or not cls._scheduler_thread.is_alive():
                cls._scheduler_stop = threading.Event()
                cls._scheduler_thread = threading.Thread(
                    target=cls._scheduler_loop, daemon=True
                )
                cls._scheduler_thread.start()

    @classmethod
    def _scheduler_loop(cls):
        while True:
            stop = cls._scheduler_stop
            if stop is None or stop.wait(60):
                return
            scheduler = cls._scheduler
            if scheduler is None:
                return
            cls._scheduler_tick(scheduler)

    @classmethod
    def _scheduler_tick(cls, scheduler):
        try:
            scheduler.run_pending()
        except Exception as e:
            logging.getLogger("sec_mcp.update_blacklist").error(
                f"Scheduled update run failed: {e}"
            )

    @classmethod
    def stop(cls):
        """Stop the shared scheduler thread and clear its job; idempotent."""
        with cls._scheduler_lock:
            if cls._scheduler_stop is not None:
                cls._scheduler_stop.set()
            thread = cls._scheduler_thread
            if (
                thread is not None
                and thread.is_alive()
                and thread is not threading.current_thread()
            ):
                thread.join(timeout=5)
            if cls._scheduler is not None:
                cls._scheduler.clear()
            cls._scheduler = None
            cls._scheduler_thread = None
            cls._scheduler_stop = None

    @classmethod
    def scheduler_alive(cls) -> bool:
        """Whether the shared scheduler loop thread is actually running."""
        thread = cls._scheduler_thread
        return bool(thread is not None and thread.is_alive())

    async def update_all(self):
        """Update blacklists from all sources."""
        # Use follow_redirects to allow redirect handling
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            tasks = []
            total = len(self.sources)
            for index, (source, url) in enumerate(self.sources.items(), 1):
                callback = self.progress_callback
                if callback is not None:
                    try:
                        callback(source, index, total)
                    except Exception:
                        self.logger.debug(f"Progress callback failed for {source}")
                tasks.append(self._update_source(client, source, url))
            await asyncio.gather(*tasks)

    def _read_cached_feed(self, filename: str):
        """Return fresh cached feed bytes, or None to force a download.

        Blocking filesystem work — callers inside coroutines must offload via
        ``asyncio.to_thread`` so the event loop never stalls on disk I/O.
        """
        if not os.path.exists(filename):
            return None
        file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(filename))
        if file_age >= timedelta(days=1):
            return None
        with open(filename, "rb") as f:
            cached = f.read(self.max_feed_bytes + 1)
        if len(cached) > self.max_feed_bytes:
            return None
        return cached

    def _write_feed_cache(self, filename: str, content: str):
        """Persist downloaded feed content to the source cache file.

        Blocking filesystem work — callers inside coroutines must offload via
        ``asyncio.to_thread`` so the event loop never stalls on disk I/O.
        """
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)

    def _is_domain_blacklisted(self, url: str) -> bool:
        """Check if the domain of a URL is blacklisted."""
        try:
            domain = urlparse(url).netloc or urlparse('//' + url).netloc
            if domain and self.storage.is_domain_blacklisted(domain):
                self.logger.debug(f"Domain {domain} is already blacklisted, skipping URL: {url}")
                return True
        except Exception as e:
            self.logger.warning(f"Failed to parse URL {url}: {e}")
        return False

    async def _update_source(self, client: httpx.AsyncClient, source: str, url: str):
        """Update blacklist from a single source."""
        if not url.lower().startswith("https://"):
            self.logger.warning(f"Rejecting non-HTTPS blacklist source {source}: {url}")
            return
        try:
            filename = self._feed_cache_filename(source, url)
            content, use_cache = await self._fetch_feed(client, source, url, filename)
            entries = self._parse_feed(source, content)
            if entries is None:
                return
            deduped_entries = self._dedupe_entries(entries)

            if deduped_entries:
                self.logger.info(f"First 5 parsed entries for {source}: {deduped_entries[:5]}")
            else:
                self.logger.warning(f"No valid entries found for {source} during update.")

            # Sanity-check entry count; an implausible feed is rejected wholesale
            # so existing data is kept rather than replaced by corrupt content.
            if not (self.min_feed_entries <= len(deduped_entries) <= self.max_feed_entries):
                self.logger.warning(
                    f"Rejecting {source}: {len(deduped_entries)} entries outside "
                    f"[{self.min_feed_entries}, {self.max_feed_entries}]; keeping existing data."
                )
                return

            # Only persist freshly downloaded content once it passes sanity
            # checks, so corrupt payloads never poison the cache.
            if not use_cache:
                await asyncio.to_thread(self._write_feed_cache, filename, content)

            # Single atomic insert: either the whole feed lands or nothing does.
            # The SQLite writes are offloaded so the event loop stays responsive.
            await asyncio.to_thread(self.storage.add_entries, deduped_entries)
            await asyncio.to_thread(self.storage.log_update, source, len(deduped_entries))
            self.logger.info(f"Updated {source}: {len(deduped_entries)} entries.")

        except Exception as e:
            self.logger.error(f"Failed to update {source}: {e}")
            self.logger.debug(traceback.format_exc())

    def _feed_cache_filename(self, source: str, url: str) -> str:
        """Return the per-source feed cache path, confined to the cache dir."""
        cache_dir = _feed_cache_dir()
        safe_source = re.sub(r"[^\w.-]", "_", source, flags=re.ASCII)
        extension = ".csv" if url.endswith('.csv') else ".txt"
        return os.path.join(cache_dir, f"{safe_source}{extension}")

    async def _fetch_feed(self, client: httpx.AsyncClient, source: str, url: str, filename: str):
        """Return ``(content, use_cache)``: fresh cached content or a download.

        Blocking cache reads are offloaded so the event loop never stalls;
        downloads abort as soon as ``max_feed_bytes`` is exceeded.
        """
        cached = await asyncio.to_thread(self._read_cached_feed, filename)
        if cached is not None:
            return cached.decode("utf-8", errors="replace"), True
        chunks = []
        downloaded = 0
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                downloaded += len(chunk)
                if downloaded > self.max_feed_bytes:
                    raise ValueError(f"{source} feed exceeds max_feed_bytes ({self.max_feed_bytes}); aborting download")
                chunks.append(chunk)
        return b"".join(chunks).decode("utf-8", errors="replace"), False

    def _parse_feed(self, source: str, content: str):
        """Dispatch to the per-source parser registered in ``_PARSERS``.

        Returns a list of ``(url, ip, date, score, source)`` tuples, or
        ``None`` when the parser fails and the update must be aborted.
        """
        parser = self._PARSERS.get(source, BlacklistUpdater._parse_generic)
        try:
            return parser(self, source, content)
        except Exception as e:
            self.logger.error(f"Parsing error for {source}: {e}. Raw content head: {content[:300]}")
            return None

    @staticmethod
    def _dedupe_entries(entries):
        """Drop duplicate entries, keyed by IP when present else by URL."""
        seen = set()
        deduped_entries = []
        for entry in entries:
            url_val, ip_val, date_val, score_val, source = entry
            key = ip_val if ip_val else url_val  # Use IP if available, otherwise URL
            if key and key not in seen:
                seen.add(key)
                deduped_entries.append(entry)
        return deduped_entries

    def _parse_phishstats(self, source: str, content: str):
        """Parse the PhishStats CSV feed (comment lines precede the header)."""
        lines = content.splitlines()
        data_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]
        if len(data_lines) < 2:  # Need at least a header and one data row
            self.logger.warning(f"No data (or only header) found for PhishStats after stripping comments. Content head: {content[:300]}")
            return None
        reader = csv.DictReader(data_lines)  # Uses the first line of data_lines as fieldnames
        now_str = datetime.now().isoformat(sep=' ', timespec='seconds')
        entries = []
        first5 = []
        for idx, row_dict in enumerate(reader):
            url_val = row_dict.get('url', '').strip()
            ip_val = row_dict.get('ip', '').strip() or None  # Ensures empty string becomes None
            # PhishStats format can be 'YYYY-MM-DD HH:MM:SS'; use it as is if
            # present, or default to now_str.
            date_val = row_dict.get('date', '').strip() or now_str
            score_str = row_dict.get('score', '').strip()
            try:
                score_val = float(score_str) if score_str else 8.0
            except ValueError:
                self.logger.warning(f"Could not parse score '{score_str}' for {source} at row {idx+1}, using default 8.0. Row: {row_dict}")
                score_val = 8.0
            if idx < 5:  # For debugging
                first5.append({'date': date_val, 'score': score_val, 'url': url_val, 'ip': ip_val})
            if url_val:  # Must have a URL at least
                entries.append((url_val, ip_val, date_val, score_val, source))
        if first5:
            self.logger.debug(f"PhishStats first 5 parsed rows: {first5}")
        return entries

    def _parse_phishtank(self, source: str, content: str):
        """Parse the PhishTank CSV feed."""
        data_lines = [line for line in content.splitlines() if line.strip()]
        reader = csv.DictReader(data_lines)
        entries = []
        first5 = []
        for idx, row in enumerate(reader):
            url_val = row.get("url", "").strip()
            date_val = row.get("submission_time", "").replace("T", " ").split("+")[0] if row.get("submission_time") else ""
            score_val = 8
            target_val = row.get("target", "")
            ip_val = None  # PhishTank doesn't provide direct IP
            if idx < 5:
                first5.append({'date': date_val, 'score': score_val, 'url': url_val, 'target': target_val})
            if url_val:
                entries.append((url_val, ip_val, date_val, score_val, source))
        if first5:
            self.logger.debug(f"PhishTank first 5 parsed rows: {first5}")
        return entries

    def _parse_spamhausdrop(self, source: str, content: str):
        """Parse the Spamhaus DROP list (';'-delimited network entries)."""
        now_str = datetime.now().isoformat(sep=' ', timespec='seconds')
        entries = []
        first5 = []
        for idx, line in enumerate(content.splitlines()):
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            # Extract the network mask (before the first ';')
            netmask = line.split(';')[0].strip()
            if not netmask:
                continue
            ip_val = netmask
            url_val = None
            if idx < 5:
                first5.append({'ip_network': ip_val, 'date': now_str, 'score': 8})
            entries.append((url_val, ip_val, now_str, 8, source))
        if first5:
            self.logger.debug(f"SpamhausDROP first 5 parsed rows: {first5}")
        return entries

    def _parse_dshield(self, source: str, content: str):
        """Parse the DShield tab-delimited block list into CIDR entries."""
        now_str = datetime.now().isoformat(sep=' ', timespec='seconds')
        entries = []
        first5 = []
        for idx, line in enumerate(content.splitlines()):
            line = line.strip()
            # Skip header lines and empty lines
            if not line or line.startswith('#') or line.startswith('Start') or line.startswith('('):
                continue
            # Parse tab-delimited fields: Start, End, Netmask, ...
            fields = line.split('\t')
            if len(fields) < 3:  # Ensure at least IP range start, end, and subnet
                continue
            # Store the range as CIDR networks so lookups cover
            # every address in the block, not just the start.
            try:
                start_ip = ip_address(fields[0].strip())
                end_ip = ip_address(fields[1].strip())
                networks = list(summarize_address_range(start_ip, end_ip))
            except (ValueError, TypeError):
                continue
            # Reject implausibly broad ranges (e.g. a corrupt
            # 0.0.0.0-255.255.255.255 row would blacklist everything).
            if int(end_ip) - int(start_ip) + 1 > self.max_range_addresses:
                continue
            for network in networks:
                ip_val = str(network.network_address) if network.num_addresses == 1 else str(network)
                if idx < 5:
                    first5.append({'ip': ip_val, 'date': now_str, 'score': 8})
                entries.append((None, ip_val, now_str, 8, source))
        if first5:
            self.logger.info(f"Dshield first 5 parsed entries: {first5}")
        return entries

    def _parse_cinsscore(self, source: str, content: str):
        """Parse the CINS Score list — one IP address per line."""
        now_str = datetime.now().isoformat(sep=' ', timespec='seconds')
        entries = []
        first5 = []
        for idx, line in enumerate(content.splitlines()):
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            # Each line contains a single IP address
            ip_val = line
            if idx < 5:
                first5.append({'ip': ip_val, 'date': now_str, 'score': 8})
            entries.append((None, ip_val, now_str, 8, source))
        if first5:
            self.logger.info(f"CINSSCORE first 5 parsed entries: {first5}")
        return entries

    def _parse_ip_or_domain_lines(self, source: str, content: str):
        """Parse a line-per-entry feed mixing IPs and bare domains/URLs."""
        now_str = datetime.now().isoformat(sep=' ', timespec='seconds')
        entries = []
        first5 = []
        for idx, line in enumerate(content.splitlines()):
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            # Each line should contain an IP address or domain
            entry = line
            # Determine if the entry is an IP address
            try:
                ip_address(entry)
                ip_val = entry
                url_val = None
            except ValueError:
                # If not an IP, treat as domain/URL
                if not entry.startswith(('http://', 'https://')):
                    url_val = f"http://{entry}"
                else:
                    url_val = entry
                ip_val = None
            if idx < 5:
                first5.append({'ip': ip_val, 'url': url_val, 'date': now_str, 'score': 8})
            entries.append((url_val, ip_val, now_str, 8, source))
        if first5:
            self.logger.info(f"{source} first 5 parsed entries: {first5}")
        return entries

    def _parse_generic(self, source: str, content: str):
        """Fallback parser: validated lines, CSV-ish or bare IP/URL values."""
        now_str = datetime.now().isoformat(sep=' ', timespec='seconds')
        entries = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or not validate_input(line):
                continue
            # Try to parse fields if CSV, else treat as single value (IP or URL)
            if ',' in line:
                parts = [p.strip() for p in line.split(',')]
                url_val = parts[0] if parts else None
                ip_val = parts[1] if len(parts) > 1 else None
                date_val = parts[2] if len(parts) > 2 and parts[2] else now_str
                try:
                    score_val = float(parts[3]) if len(parts) > 3 and parts[3] else 8
                except Exception:
                    score_val = 8
            else:
                # Determine if the single value is an IP address or URL
                try:
                    # Try parsing as IP address
                    ip_address(line)
                    url_val = None
                    ip_val = line
                except ValueError:
                    # If not an IP, treat as URL
                    # Add http:// prefix if neither http:// nor https:// is present
                    if not line.startswith(('http://', 'https://')):
                        url_val = f"http://{line}"
                    else:
                        url_val = line
                    ip_val = None
                date_val = now_str
                score_val = 8
            entries.append((url_val, ip_val, date_val, score_val, source))
        return entries

    # One parser per source — dispatch table keyed by the source name used in
    # config.json. Feeds sharing a format map to the same parser; anything not
    # listed falls back to ``_parse_generic``.
    _PARSERS = {
        "PhishStats": _parse_phishstats,
        "PhishTank": _parse_phishtank,
        "SpamhausDROP": _parse_spamhausdrop,
        "Dshield": _parse_dshield,
        "CINSSCORE": _parse_cinsscore,
        "EmergingThreats": _parse_ip_or_domain_lines,
        "FeodoTracker": _parse_ip_or_domain_lines,
        "BlocklistDE": _parse_ip_or_domain_lines,
    }

    def force_update(self):
        """Force an immediate update of all blacklists.

        Rate limited: a second call within ``min_update_interval`` seconds of
        the previous attempt is refused before any download starts, returning
        ``{"updated": False, "reason": ...}``. A successful dispatch returns
        ``{"updated": True}``.
        """
        now = time.monotonic()
        with self._force_update_lock:
            last = self._last_force_update
            if last is not None and now - last < self.min_update_interval:
                remaining = self.min_update_interval - (now - last)
                return {
                    "updated": False,
                    "reason": (
                        f"rate limited: last update started "
                        f"{now - last:.0f}s ago; retry in {remaining:.0f}s "
                        f"(min interval {self.min_update_interval}s)"
                    ),
                }
            self._last_force_update = now
        asyncio.run(self.update_all())
        return {"updated": True}
