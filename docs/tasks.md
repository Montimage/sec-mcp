# Development Tasks: Model Context Protocol (MCP) Client

This document outlines the development tasks required to build the **Model Context Protocol (MCP) Client** as specified in the Project Requirement Document (PRD, dated April 15, 2025). Tasks are organized into agile sprints to deliver a Minimum Viable Product (MVP) within a 1-month timeline, addressing core features, user stories, and non-functional requirements. The MVP focuses on blacklist checking, automated updates, and an always-running MCP server, with subsequent sprints covering enhancements and optimizations.

---

## MVP Definition

The MVP delivers the core value proposition of the MCP Client: a lightweight Python library and CLI for cybersecurity developers to check domains, URLs, or IPs against a blacklist, integrated with an always-running MCP server for AI-driven workflows. Key features include:

- **Blacklist Checking**: Single and batch checks against OpenPhish, PhishStats, and URLhaus feeds, with JSON output (`is_safe`, `explain`).
- **Automated Updates**: Daily blacklist updates from open-source feeds, stored in SQLite.
- **MCP Server**: Always-running `check_blacklist` tool via `FastMCP` with STDIO transport.
- **Modular Architecture**: Independent modules (`core`, `update_blacklist`, `storage`, `interface`, `utility`) for testability.
- **Performance**: Near real-time responses (<5s), thousands of checks per second.
- **Security**: Input validation and logging.

The MVP excludes future considerations (e.g., Google Safe Browsing, PhishTank re-enablement) and non-critical features (e.g., advanced error notifications), which are deferred to later sprints.

---

## Sprint Planning

Tasks are grouped into three sprints, aligning with the 1-month timeline (4 weeks, assuming 1-2 developers). Sprint 1 (2 weeks) delivers the MVP, Sprint 2 (1 week) adds enhancements, and Sprint 3 (1 week) focuses on testing, packaging, and optimization.

### Sprint 1: MVP (Weeks 1-2)
Focus: Core functionality for blacklist checking, automated updates, MCP server, and modular architecture.

#### Task 1: Set Up Project Structure
- **Description**: Initialize the Python package with modular structure and dependencies, per PRD Section 6 (Technical Stack). Create files for `core`, `update_blacklist`, `storage`, `interface`, `utility`, and `config.json`.
- **Acceptance Criteria**:
  - Package structure created: `mcp_client/__init__.py`, `core.py`, `update_blacklist.py`, `storage.py`, `interface.py`, `utility.py`.
  - Dependencies installed: `requests`, `click`, `tqdm`, `idna`, `mcp[cli]`, `httpx`.
  - `config.json` generated with default sources: OpenPhish, PhishStats, URLhaus.
  - Basic `setup.py` for `pip install mcp-client`.
- **Dependencies**: None.

#### Task 2: Implement Utility Module
- **Description**: Develop the `utility` module for validation, logging, and config management, per PRD Section 4 (Blacklist Checking) and Section 5 (Security, Usability).
- **Acceptance Criteria**:
  - `validate_url(value)` validates domains (`idna`), URLs (`urllib.parse`), IPs (`ipaddress`).
  - `setup_logging(log_file)` configures logging to `mcp.log`.
  - `load_config(config_path)` reads/writes `config.json` with default sources.
  - Unit tests pass for all functions (mock file I/O for config).
- **Dependencies**: Task 1.

#### Task 3: Implement Storage Module
- **Description**: Build the `storage` module for SQLite operations, supporting blacklist queries and status reporting, per PRD Section 4 (Blacklist Checking, Status Reporting) and Section 5 (Performance, Scalability).
- **Acceptance Criteria**:
  - `init_db(db_path)` creates `blacklist` and `cache` tables with index on `value`.
  - `insert_blacklist(entries)` inserts deduplicated URLs with source and timestamp.
  - `query_blacklist(value)` returns JSON (`is_safe`, `explain`) using cache and SQLite.
  - `query_batch(values)` processes chunks (1000 inputs) with `IN` clause.
  - `get_status()` returns entry count, last update, and server status.
  - In-memory cache (~10k entries) loaded via `load_cache()`.
  - Unit tests pass (mock SQLite connections).
- **Dependencies**: Task 2.

#### Task 4: Implement Update Blacklist Module
- **Description**: Develop the `update_blacklist` module to download, parse, and store feeds from OpenPhish, PhishStats, and URLhaus, per PRD Section 4 (Automated Updates).
- **Acceptance Criteria**:
  - `check_sources(sources)` validates source URLs.
  - `download_feed(source)` fetches `.txt` (OpenPhish, URLhaus) or CSV (PhishStats) using `requests`.
  - `parse_feed(content, source)` extracts URLs, validates via `utility.validate_url`.
  - `update(sources)` coordinates download, parse, and storage via `storage.insert_blacklist`.
  - Handles ~80k entries with deduplication.
  - Unit tests pass (mock `requests.get`, test `.txt` and CSV parsing).
- **Dependencies**: Task 2, Task 3.

#### Task 5: Implement Core Module
- **Description**: Build the `core` module to orchestrate modules and manage the update scheduler, per PRD Section 4 (Modular Architecture) and Section 6 (Design Principles).
- **Acceptance Criteria**:
  - `MCPClient` initializes `storage`, `update_blacklist`, `interface`, and `utility`.
  - Methods (`check`, `check_batch`, `update`, `status`) delegate to respective modules.
  - Daily update scheduler runs at 00:00 via `schedule` in a background thread.
  - Unit tests pass (mock module interactions).
- **Dependencies**: Task 2, Task 3, Task 4.

#### Task 6: Implement Interface Module (CLI and MCP Server)
- **Description**: Develop the `interface` module for CLI commands and an always-running MCP server, per PRD Section 4 (Blacklist Checking, Batch Processing, MCP Server, Status Reporting).
- **Acceptance Criteria**:
  - CLI commands: `mcp check <value>`, `mcp batch <file>`, `mcp update`, `mcp status` using `click`.
  - Options: `--json` for machine-readable output, `--verbose` for human-readable.
  - `tqdm` progress bars for batch checks and updates.
  - API functions: `check(value)`, `check_batch(values)` for library integration.
  - MCP server runs `check_blacklist` tool via `FastMCP` (STDIO) in a background thread, started automatically.
  - Unit tests pass (mock `core` calls, test CLI output, mock MCP server responses).
- **Dependencies**: Task 2, Task 3, Task 4, Task 5.

---

### Sprint 2: Enhancements (Week 3)
Focus: Security, usability, and maintainability improvements.

#### Task 7: Enhance Security Features
- **Description**: Add security measures for input validation, blacklist sanitization, and database protection, per PRD Section 5 (Security).
- **Acceptance Criteria**:
  - `utility.validate_url` rejects private IPs and non-HTTP/HTTPS URLs.
  - `update_blacklist.parse_feed` logs and skips invalid entries.
  - `storage.init_db` sets read-only permissions on `mcp.db` (e.g., `chmod 400`).
  - Comprehensive logging for invalid inputs, update failures, and server errors.
  - Unit tests pass for edge cases (e.g., malformed URLs, private IPs).
- **Dependencies**: Task 2, Task 3, Task 4.

#### Task 8: Improve CLI Usability
- **Description**: Enhance CLI output and error handling for better developer experience, per PRD Section 5 (Usability).
- **Acceptance Criteria**:
  - `mcp check` and `mcp batch` display clear error messages for invalid inputs.
  - `mcp status` includes source list and formatted timestamps.
  - `mcp update` reports number of new entries added.
  - CLI supports `--log <file>` to override default `mcp.log`.
  - Unit tests pass for CLI edge cases (e.g., empty files, missing sources).
- **Dependencies**: Task 6.

#### Task 9: Add Error Handling for Updates
- **Description**: Implement robust error handling for blacklist update failures, per PRD Section 5 (Maintainability).
- **Acceptance Criteria**:
  - `update_blacklist.download_feed` retries failed downloads (3 attempts, 5s timeout).
  - Fallback to last valid blacklist in SQLite on download failure.
  - Log detailed errors (e.g., HTTP status, network issues) to `mcp.log`.
  - `mcp status` flags failed updates with last error message.
  - Unit tests pass (mock failed `requests.get`).
- **Dependencies**: Task 4, Task 6.

---

### Sprint 3: Testing, Packaging, and Optimization (Week 4)
Focus: Comprehensive testing, packaging, and performance tuning.

#### Task 10: Develop Unit Tests
- **Description**: Write unit tests for all modules to ensure independent testability, per PRD Section 6 (Design Principles).
- **Acceptance Criteria**:
  - Tests for `utility`: Validate URLs, config parsing, logging setup.
  - Tests for `storage`: Mock SQLite for table creation, inserts, queries.
  - Tests for `update_blacklist`: Mock `requests.get`, test `.txt`/CSV parsing, deduplication.
  - Tests for `interface`: Mock `core`, test CLI commands, MCP server responses.
  - Tests for `core`: Mock modules, test orchestration and scheduler.
  - Achieve >90% code coverage using `pytest`.
- **Dependencies**: Task 2, Task 3, Task 4, Task 5, Task 6.

#### Task 11: Optimize Performance
- **Description**: Tune SQLite queries and in-memory cache for high throughput, per PRD Section 5 (Performance).
- **Acceptance Criteria**:
  - Single checks return in <100ms for ~80k entries.
  - Batch checks (1000 inputs) return in <1s.
  - Updates process ~80k entries in <10s.
  - Benchmark confirms thousands of checks per second on standard hardware.
  - Unit tests pass for optimized queries (e.g., chunked `IN` clause).
- **Dependencies**: Task 3, Task 4, Task 10.

#### Task 12: Package and Distribute
- **Description**: Package the MCP Client as a Python package for local deployment, per PRD Section 6 (Constraints).
- **Acceptance Criteria**:
  - `setup.py` includes all dependencies and package metadata.
  - `pip install mcp-client` installs library, CLI, and `config.json`.
  - Package includes `mcp.db` (empty) and sample `config.json`.
  - Verify installation on Python 3.11 with all features functional.
  - Basic README with installation and usage instructions (minimal, per user preference).
- **Dependencies**: Task 1, Task 5, Task 6, Task 10.

---

## Ambiguities and Recommendations
- **Ambiguity**: Success metrics for the MVP (e.g., adoption rate, check accuracy) are undefined (PRD Section 8). **Recommendation**: Define post-MVP metrics, e.g., “90% of checks return in <1s” or “100% update success over 30 days.”
- **Ambiguity**: Acceptable blacklist overlap between feeds is unclear (PRD Section 8). **Recommendation**: Post-MVP analysis to measure unique entries and optimize sources.
- **Ambiguity**: Testing strategy (unit vs. integration) is not specified (PRD Section 8). **Recommendation**: Focus on unit tests in Sprint 3, with integration tests post-MVP.

---

## Task Summary
| **Sprint** | **Tasks** | **Focus** | **Duration** |
| --- | --- | --- | --- |
| Sprint 1 | 1-6 | MVP: Project setup, core modules, blacklist checking, updates, MCP server | 2 weeks |
| Sprint 2 | 7-9 | Enhancements: Security, CLI usability, error handling | 1 week |
| Sprint 3 | 10-12 | Testing, optimization, packaging | 1 week |

This plan ensures the MVP is delivered by May 15, 2025, meeting all core requirements within the 1-month timeline and low-budget constraints.
