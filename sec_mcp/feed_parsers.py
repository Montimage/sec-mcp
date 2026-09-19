"""Per-source feed parsers for ``sec_mcp.update_blacklist.BlacklistUpdater``.

One parser per feed format, dispatched by source name; anything unregistered
falls back to ``_parse_generic``. Every parser returns a list of
``(url, ip, date, score, source)`` tuples — or ``None`` to abort the update —
so ``BlacklistUpdater._update_source`` can treat feeds uniformly.
"""

import csv
from datetime import datetime
from ipaddress import ip_address, summarize_address_range

from .utility import validate_input


class FeedParser:
    """Feed parsing half of BlacklistUpdater.

    Holds a reference to the updater for its ``logger`` and configured
    limits, so the parser methods behave exactly as they did when they lived
    on the updater itself.
    """

    def __init__(self, updater):
        self._updater = updater
        self.logger = updater.logger

    @property
    def max_range_addresses(self) -> int:
        """Live read of the updater's configured range-size cap."""
        return self._updater.max_range_addresses

    def parse(self, source: str, content: str):
        """Dispatch to the per-source parser registered in ``_PARSERS``.

        Returns a list of ``(url, ip, date, score, source)`` tuples, or
        ``None`` when the parser fails and the update must be aborted.
        """
        parser = self._PARSERS.get(source, FeedParser._parse_generic)
        try:
            return parser(self, source, content)
        except Exception as e:  # noqa: BLE001 — a failed parser must abort this source, never the whole update
            self.logger.error(f"Parsing error for {source}: {e}. Raw content head: {content[:300]}")
            return None

    @staticmethod
    def dedupe(entries):
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
                except (ValueError, TypeError):
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
