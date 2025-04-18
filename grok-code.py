# mcp_client/core.py
import threading
import schedule
import time
from .update_blacklist import UpdateBlacklist
from .storage import Storage
from .interface import Interface
from .utility import load_config, setup_logging

class MCPClient:
    def __init__(self, db_path='mcp.db', config_path='config.json', log_file='mcp.log'):
        self.config = load_config(config_path)
        self.logger = setup_logging(log_file)
        self.storage = Storage(db_path)
        self.updater = UpdateBlacklist(self.storage, self.config['sources'])
        self.interface = Interface(self)
        self.start_scheduler()

    def check(self, value):
        return self.storage.query_blacklist(value)

    def check_batch(self, values):
        return self.storage.query_batch(values)

    def update(self, sources=None):
        self.updater.update(sources or self.config['sources'])

    def status(self):
        return self.storage.get_status()

    def start_scheduler(self):
        schedule.every().day.at("00:00").do(self.update)
        def run():
            while True:
                schedule.run_pending()
                time.sleep(60)
        threading.Thread(target=run, daemon=True).start()

# mcp_client/update_blacklist.py
import requests
import csv
import io
from datetime import datetime
from .utility import validate_url

class UpdateBlacklist:
    def __init__(self, storage, sources):
        self.storage = storage
        self.sources = sources

    def check_sources(self, sources):
        return all(s.startswith('http') for s in sources)

    def download_feed(self, source):
        try:
            response = requests.get(source, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Failed to download {source}: {e}")
            return None

    def parse_feed(self, content, source):
        entries = []
        if not content:
            return entries
        if 'phishstats' in source:
            csv_file = io.StringIO(content)
            reader = csv.DictReader(csv_file)
            for row in reader:
                url = row.get('url', '').strip()
                if url and validate_url(url):
                    entries.append((url, 'PhishStats', datetime.now()))
        else:
            lines = content.strip().split('\n')
            for line in lines:
                url = line.strip()
                if url and validate_url(url):
                    entries.append((url, source.split('/')[-2], datetime.now()))
        return entries

    def update(self, sources):
        if not self.check_sources(sources):
            print("Invalid sources")
            return
        for source in sources:
            content = self.download_feed(source)
            entries = self.parse_feed(content, source)
            self.storage.insert_blacklist(entries)
            print(f"Updated {len(entries)} entries from {source}")

# mcp_client/storage.py
import sqlite3
from .utility import validate_url

class Storage:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.init_db()
        self.cache = self.load_cache()

    def init_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS blacklist (
                value TEXT PRIMARY KEY,
                source TEXT,
                added_at TIMESTAMP
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                value TEXT PRIMARY KEY,
                is_safe BOOLEAN,
                explain TEXT,
                timestamp TIMESTAMP,
                ttl INTEGER
            )
        ''')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_blacklist_value ON blacklist(value)')
        self.conn.commit()

    def load_cache(self):
        self.cursor.execute('SELECT value FROM blacklist LIMIT 10000')
        return {row[0] for row in self.cursor.fetchall()}

    def insert_blacklist(self, entries):
        self.cursor.executemany(
            'INSERT OR IGNORE INTO blacklist (value, source, added_at) VALUES (?, ?, ?)',
            entries
        )
        self.conn.commit()
        self.cache = self.load_cache()

    def query_blacklist(self, value):
        if not validate_url(value):
            return {"is_safe": False, "explain": "Invalid domain, URL, or IP"}
        if value in self.cache:
            return {"is_safe": False, "explain": "Blacklisted from cached source"}
        self.cursor.execute('SELECT source FROM blacklist WHERE value = ?', (value,))
        result = self.cursor.fetchone()
        if result:
            return {"is_safe": False, "explain": f"Blacklisted by {result[0]}"}
        return {"is_safe": True, "explain": "Not blacklisted"}

    def query_batch(self, values):
        results = []
        valid_values = [v for v in values if validate_url(v)]
        invalid_values = [v for v in values if not validate_url(v)]
        for value in invalid_values:
            results.append({"is_safe": False, "explain": "Invalid domain, URL, or IP"})
        cache_hits = {v: {"is_safe": False, "explain": "Blacklisted from cached source"} for v in valid_values if v in self.cache}
        remaining = [v for v in valid_values if v not in self.cache]
        if remaining:
            chunks = [remaining[i:i+1000] for i in range(0, len(remaining), 1000)]
            for chunk in chunks:
                placeholders = ','.join('?' * len(chunk))
                self.cursor.execute(f'SELECT value, source FROM blacklist WHERE value IN ({placeholders})', chunk)
                db_hits = {row[0]: row[1] for row in self.cursor.fetchall()}
                for value in chunk:
                    if value in db_hits:
                        results.append({"is_safe": False, "explain": f"Blacklisted by {db_hits[value]}"})
                    else:
                        results.append({"is_safe": True, "explain": "Not blacklisted"})
        results.extend(cache_hits.values())
        return results

    def get_status(self):
        self.cursor.execute('SELECT COUNT(*) FROM blacklist')
        count = self.cursor.fetchone()[0]
        self.cursor.execute('SELECT MAX(added_at) FROM blacklist')
        last_update = self.cursor.fetchone()[0] or 'Never'
        return {
            'blacklist_entries': count,
            'last_update': last_update,
            'server_status': 'Running (STDIO)'
        }

    def __del__(self):
        self.conn.close()

# mcp_client/interface.py
import click
import json
import threading
from mcp.server.fastmcp import FastMCP
from tqdm import tqdm

class Interface:
    def __init__(self, client):
        self.client = client
        self.start_mcp_server()

    def check(self, value):
        return self.client.check(value)

    def check_batch(self, values):
        return self.client.check_batch(values)

    def update(self, sources=None):
        self.client.update(sources)

    def status(self):
        return self.client.status()

    def start_mcp_server(self):
        def run_server():
            mcp = FastMCP("blacklist_checker")
            @mcp.tool("check_blacklist")
            def check_blacklist(value: str):
                return self.client.check(value)
            mcp.run()
        threading.Thread(target=run_server, daemon=True).start()
        print("MCP server started in background (STDIO)")

@click.group()
def cli():
    pass

@cli.command()
@click.argument('value')
@click.option('--json', is_flag=True, help='Output as JSON')
@click.option('--verbose', is_flag=True, help='Verbose output')
def check(value, json, verbose):
    client = MCPClient()
    result = client.check(value)
    if json:
        print(json.dumps(result))
    elif verbose:
        print(f"{value}: {result['explain']}")
    else:
        print(f"is_safe: {result['is_safe']}")

@cli.command()
@click.argument('file', type=click.File('r'))
@click.option('--json', is_flag=True, help='Output as JSON')
@click.option('--verbose', is_flag=True, help='Verbose output')
def batch(file, json, verbose):
    client = MCPClient()
    values = [line.strip() for line in file if line.strip()]
    results = client.check_batch(values)
    if json:
        print(json.dumps(results))
    elif verbose:
        for value, result in zip(values, results):
            print(f"{value}: {result['explain']}")
    else:
        for result in results:
            print(f"is_safe: {result['is_safe']}")

@cli.command()
@click.option('--source', multiple=True, help='Source URL')
def update(source):
    client = MCPClient()
    client.update(list(source) if source else None)
    print("Blacklist updated")

@cli.command()
@click.option('--json', is_flag=True, help='Output as JSON')
def status(json):
    client = MCPClient()
    status = client.status()
    if json:
        print(json.dumps(status))
    else:
        print(f"Blacklist entries: {status['blacklist_entries']}")
        print(f"Last update: {status['last_update']}")
        print(f"Server: {status['server_status']}")

# mcp_client/utility.py
import logging
import urllib.parse
import ipaddress
import idna
import json

def setup_logging(log_file):
    logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger()

def validate_url(value):
    try:
        idna.encode(value)
        return True
    except idna.IDNAError:
        try:
            parsed = urllib.parse.urlparse(value)
            return bool(parsed.scheme and parsed.netloc)
        except ValueError:
            try:
                ipaddress.ip_address(value)
                return True
            except ValueError:
                return False

def load_config(config_path):
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        default_config = {
            'sources': [
                'https://openphish.com/feed.txt',
                'https://phishstats.info/phish_score.csv',
                'https://urlhaus.abuse.ch/downloads/text/'
            ]
        }
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        return default_config

# mcp_client/__init__.py
from .core import MCPClient