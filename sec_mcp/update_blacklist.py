import asyncio
import csv
import httpx
import json
import os
from datetime import datetime
import schedule
import threading
from typing import List, Dict
from .storage import Storage
from .utility import validate_input, setup_logging
import logging

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
        # Use follow_redirects to allow redirect handling
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            tasks = []
            for source, url in self.sources.items():
                tasks.append(self._update_source(client, source, url))
            await asyncio.gather(*tasks)

    async def _update_source(self, client: httpx.AsyncClient, source: str, url: str):
        """Update blacklist from a single source."""
        import os
        import time
        from datetime import datetime, timedelta
        try:
            os.makedirs("downloads", exist_ok=True)
            filename = os.path.join("downloads", f"{source}.txt" if not url.endswith('.csv') else f"{source}.csv")
            use_cache = False
            if os.path.exists(filename):
                mtime = os.path.getmtime(filename)
                file_age = datetime.now() - datetime.fromtimestamp(mtime)
                if file_age < timedelta(days=1):
                    use_cache = True
            if use_cache:
                with open(filename, "r", encoding="utf-8", errors='ignore') as f:
                    content = f.read()
            else:
                response = await client.get(url)
                response.raise_for_status()
                content = response.text
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)
            entries = []
            
            # Source-specific parsing logic
            if source == "PhishStats":
                try:
                    # Skip comment lines and use the first non-comment line as header
                    lines = content.splitlines()
                    # Skip all comment lines; treat all remaining as data (date, score, url, ip)
                    data_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]
                    if not data_lines:
                        raise ValueError("No CSV data found for PhishStats")
                    reader = csv.reader(data_lines)
                    first5 = []
                    for idx, row in enumerate(reader):
                        if len(row) < 3:
                            continue  # skip incomplete rows
                        date_val = row[0].strip()
                        score_val = float(row[1].strip()) if row[1].strip() else 8
                        url_val = row[2].strip()
                        ip_val = row[3].strip() if len(row) > 3 else None
                        if idx < 5:
                            first5.append({'date': date_val, 'score': score_val, 'url': url_val, 'ip': ip_val})
                        if url_val:
                            entries.append((url_val, ip_val, date_val, score_val, source))
                    if first5:
                        self.logger.debug(f"PhishStats first 5 parsed rows: {first5}")
                except Exception as e:
                    self.logger.error(f"CSV parsing error for {source}: {e}. Raw content head: {content[:300]}")
                    return
            elif source == "PhishTank":
                try:
                    lines = content.splitlines()
                    data_lines = [line for line in lines if line.strip()]
                    reader = csv.DictReader(data_lines)
                    first5 = []
                    for idx, row in enumerate(reader):
                        url_val = row.get("url", "").strip()
                        date_val = row.get("submission_time", "").replace("T", " ").split("+")[0] if row.get("submission_time") else ""
                        score_val = 8
                        target_val = row.get("target", "")
                        # Optionally: use target_val for tagging or notes
                        ip_val = None  # PhishTank doesn't provide direct IP
                        if idx < 5:
                            first5.append({'date': date_val, 'score': score_val, 'url': url_val, 'target': target_val})
                        if url_val:
                            entries.append((url_val, ip_val, date_val, score_val, source))
                    if first5:
                        self.logger.debug(f"PhishTank first 5 parsed rows: {first5}")
                except Exception as e:
                    self.logger.error(f"CSV parsing error for {source}: {e}. Raw content head: {content[:300]}")
                    return
            elif source == "SpamhausDROP":
                try:
                    lines = content.splitlines()
                    first5 = []
                    from datetime import datetime
                    now_str = datetime.now().isoformat(sep=' ', timespec='seconds')
                    for idx, line in enumerate(lines):
                        line = line.strip()
                        if not line or line.startswith(';'):
                            continue
                        # Extract the network mask (before the first ';')
                        netmask = line.split(';')[0].strip()
                        if not netmask:
                            continue
                        ip_val = netmask
                        url_val = None
                        date_val = now_str
                        score_val = 8
                        if idx < 5:
                            first5.append({'ip_network': ip_val, 'date': date_val, 'score': score_val})
                        entries.append((url_val, ip_val, date_val, score_val, source))
                    if first5:
                        self.logger.debug(f"SpamhausDROP first 5 parsed rows: {first5}")
                except Exception as e:
                    self.logger.error(f"Parsing error for {source}: {e}. Raw content head: {content[:300]}")
                    return
            elif source == "Dshield":
                try:
                    lines = content.splitlines()
                    from datetime import datetime
                    now_str = datetime.now().isoformat(sep=' ', timespec='seconds')
                    first5 = []
                    for idx, line in enumerate(lines):
                        line = line.strip()
                        # Skip header lines and empty lines
                        if not line or line.startswith('#') or line.startswith('Start') or line.startswith('('):
                            continue
                        
                        # Parse tab-delimited fields
                        fields = line.split('\t')
                        if len(fields) < 3:  # Ensure at least IP range start, end, and subnet
                            continue
                            
                        # Use the start IP of the range
                        ip_val = fields[0].strip()
                        url_val = None
                        date_val = now_str
                        score_val = 8
                        
                        if idx < 5:
                            first5.append({'ip': ip_val, 'date': date_val, 'score': score_val})
                        entries.append((url_val, ip_val, date_val, score_val, source))
                    
                    if first5:
                        self.logger.info(f"Dshield first 5 parsed entries: {first5}")
                except Exception as e:
                    self.logger.error(f"Parsing error for {source}: {e}. Raw content head: {content[:300]}")
                    return
            elif source == "CINSSCORE":
                try:
                    lines = content.splitlines()
                    from datetime import datetime
                    now_str = datetime.now().isoformat(sep=' ', timespec='seconds')
                    first5 = []
                    
                    for idx, line in enumerate(lines):
                        line = line.strip()
                        # Skip empty lines and comments
                        if not line or line.startswith('#'):
                            continue
                            
                        # Each line contains a single IP address
                        ip_val = line
                        url_val = None
                        date_val = now_str
                        score_val = 8
                        
                        if idx < 5:
                            first5.append({'ip': ip_val, 'date': date_val, 'score': score_val})
                        entries.append((url_val, ip_val, date_val, score_val, source))
                    
                    if first5:
                        self.logger.info(f"CINSSCORE first 5 parsed entries: {first5}")
                except Exception as e:
                    self.logger.error(f"Parsing error for {source}: {e}. Raw content head: {content[:300]}")
                    return
            elif source == "EmergingThreats" or source == "FeodoTracker" or source == "BlocklistDE":
                try:
                    lines = content.splitlines()
                    from datetime import datetime
                    now_str = datetime.now().isoformat(sep=' ', timespec='seconds')
                    first5 = []
                    
                    for idx, line in enumerate(lines):
                        line = line.strip()
                        # Skip empty lines and comments
                        if not line or line.startswith('#'):
                            continue
                            
                        # Each line should contain an IP address or domain
                        entry = line
                        
                        # Determine if the entry is an IP address
                        try:
                            from ipaddress import ip_address
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
                        
                        date_val = now_str
                        score_val = 8
                        
                        if idx < 5:
                            first5.append({'ip': ip_val, 'url': url_val, 'date': date_val, 'score': score_val})
                        entries.append((url_val, ip_val, date_val, score_val, source))
                    
                    if first5:
                        self.logger.info(f"{source} first 5 parsed entries: {first5}")
                except Exception as e:
                    self.logger.error(f"Parsing error for {source}: {e}. Raw content head: {content[:300]}")
                    return
            else:
                from datetime import datetime
                from ipaddress import ip_address
                now_str = datetime.now().isoformat(sep=' ', timespec='seconds')
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
            
            # Deduplicate: for IP-based sources use ip_val, otherwise use url_val
            seen = set()
            deduped_entries = []
            for entry in entries:
                url_val, ip_val, date_val, score_val, source = entry
                key = ip_val if ip_val else url_val  # Use IP if available, otherwise URL
                if key and key not in seen:
                    seen.add(key)
                    deduped_entries.append(entry)
            
            if deduped_entries:
                self.logger.info(f"First 5 parsed entries for {source}: {deduped_entries[:5]}")
            else:
                self.logger.warning(f"No valid entries found for {source} during update.")
            
            # Insert entries into database
            url_count = 0
            ip_count = 0
            domain_count = 0
            for entry in deduped_entries:
                url_val, ip_val, date_val, score_val, src = entry
                # Add URL if present and valid
                if url_val and url_val.startswith(('http://', 'https://')):
                    try:
                        from urllib.parse import urlparse
                        parsed_url = urlparse(url_val)
                        domain = parsed_url.netloc
                        if domain:
                            if validate_input(domain):  # Validate domain
                                self.storage.add_domain(domain, date_val, score_val, src)
                                domain_count += 1
                            self.storage.add_url(url_val, date_val, score_val, src)
                            url_count += 1
                    except Exception as e:
                        self.logger.debug(f"URL parsing error: {e} for {url_val}")
                        continue
                
                # Add IP if present and valid
                if ip_val:
                    try:
                        self.storage.add_ip(ip_val, date_val, score_val, src)
                        ip_count += 1
                    except Exception as e:
                        self.logger.debug(f"IP insertion error: {e} for {ip_val}")
                        continue
            
            self.logger.info(f"Updated {source}: {url_count} URLs, {domain_count} domains, {ip_count} IPs.")
        
        except Exception as e:
            self.logger.error(f"Failed to update {source}: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())

    def force_update(self):
        """Force an immediate update of all blacklists."""
        asyncio.run(self.update_all())
