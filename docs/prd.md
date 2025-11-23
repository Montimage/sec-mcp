# Project Requirement Document: Model Context Protocol (MCP) Client

**Version**: 1.0  
**Date**: April 15, 2025  
**Author**: Luong NGUYEN

---

## 1. Introduction / Overview

The **Model Context Protocol (MCP) Client** is a lightweight Python library and command-line interface (CLI) designed to enable cybersecurity developers to check domains, URLs, or IP addresses against a blacklist for phishing and malware threats. Integrated with an always-running MCP server, the tool exposes a `check_blacklist` function for seamless integration into network security monitoring tools, applications, or AI-driven workflows via the MCP protocol. The initial version focuses on simplicity, leveraging open-source blacklist feeds (OpenPhish, PhishStats, URLhaus) with daily updates, stored in a SQLite database. The project adheres to a low-budget, 1-month timeline, targeting high-throughput checks with future extensibility for third-party services like Google Safe Browsing.

This PRD outlines the goals, features, user requirements, and technical considerations for the MCP Client MVP, consolidating insights from discussions to deliver a focused, developer-friendly security tool.

---

## 2. Goals / Objectives

The MCP Client aims to achieve the following measurable outcomes:

1. **Enable Security Integration**: Provide a Python library and CLI that cybersecurity developers can integrate into network security tools or apps to validate domains, URLs, or IPs against a blacklist.
2. **Ensure Threat Coverage**: Support phishing and malware detection using open-source feeds (OpenPhish, PhishStats, URLhaus), covering ~80k unique URLs after deduplication.
3. **Support MCP Protocol**: Implement an always-running MCP server exposing a `check_blacklist` tool for AI-driven clients (e.g., LLMs), ensuring compatibility with the MCP ecosystem.
4. **Achieve High Throughput**: Deliver near real-time responses (<5s) for thousands of checks per second, suitable for high-volume security monitoring.
5. **Automate Updates**: Automatically update blacklists daily from open-source feeds, minimizing manual maintenance.
6. **Maintain Modularity**: Structure the library into independent modules (`core`, `update_blacklist`, `storage`, `interface`, `utility`) for testability and extensibility.
7. **Meet Constraints**: Deliver the MVP within a 1-month timeline and low-budget constraints, using free feeds and local deployment.

---

## 3. Target Audience

### Primary Users
- **Cybersecurity Developers**:
  - **Characteristics**: Proficient in Python and cybersecurity, building or enhancing network security monitoring tools (e.g., SIEM systems, firewalls) or applications.
  - **Needs**:
    - A lightweight library for programmatic integration.
    - A CLI for quick blacklist checks and management.
    - Machine-readable JSON output (`is_safe`, `explain`) for automation.
    - High-throughput performance for real-time monitoring.
  - **Use Case**: Integrating the MCP Client into a SIEM to flag phishing URLs or into an app to validate user-submitted links.

### Secondary Users
- **MCP Client Developers**:
  - **Characteristics**: Developers using the MCP protocol to build AI-driven workflows, leveraging LLMs for security tasks.
  - **Needs**:
    - An always-running MCP server with a `check_blacklist` tool.
    - Standardized JSON output for LLM processing.
  - **Use Case**: Querying the MCP server from an LLM client to validate URLs in a chatbot or automated threat analysis pipeline.

---

## 4. Functional Requirements / Features

### User Stories
| **User Story** | **Priority** | **Description** |
| --- | --- | --- |
| As a cybersecurity developer, I want to check a single domain, URL, or IP against a blacklist so I can determine if it’s safe. | High | Call `check(value)` or `mcp check <value>` to get JSON: `{"is_safe": true/false, "explain": "Reason"}`. |
| As a cybersecurity developer, I want to check multiple inputs in batch so I can process large datasets efficiently. | High | Call `check_batch(values)` or `mcp batch <file>` for a list of JSON results. |
| As a cybersecurity developer, I want automated daily blacklist updates so I don’t need to manually manage data. | High | Blacklists update daily from OpenPhish, PhishStats, URLhaus, stored in SQLite. |
| As a cybersecurity developer, I want to check specifically a domain, URL, or IP so I can optimize checks and get more precise results. | High | Use `mcp check_domain <domain>`, `mcp check_url <url>`, or `mcp check_ip <ip>` for targeted lookups. |
| As a cybersecurity developer, I want to view blacklist status so I can monitor update frequency and data volume. | Medium | Call `status()` or `mcp status` for stats (entry count, last update, sources). |
| As an MCP client developer, I want to query the MCP server so I can integrate blacklist checks into AI workflows. | High | Query `check_blacklist` tool via MCP server (STDIO or HTTP transport) for JSON output. |

### Features
1. **Blacklist Checking**:
   - Input: Domain, URL, or IP address.
   - Output: JSON with `is_safe` (boolean) and `explain` (string, e.g., “Blacklisted by OpenPhish” or “Not blacklisted”).
   - Sources: OpenPhish (`.txt`, phishing URLs), PhishStats (CSV, phishing URLs), URLhaus (`.txt`, malware/phishing URLs).
   - Validation: Ensure inputs are valid domains (IDNA), URLs (HTTP/HTTPS), or IPs (IPv4/IPv6).

2. **Batch Processing**:
   - Process multiple inputs via `check_batch` or `mcp batch <file>`.
   - Optimize with SQLite `IN` clause and chunking (1000 inputs per query).
   - Progress bar via `tqdm` for CLI usability.

3. **Automated Updates**:
   - Download and parse blacklists daily at 00:00 using `schedule`.
   - Sources: `https://openphish.com/feed.txt`, `https://phishstats.info/phish_score.csv`, `https://urlhaus.abuse.ch/downloads/text/`.
   - Deduplicate entries in SQLite (`INSERT OR IGNORE`).
   - Fallback to last valid blacklist on download failure.

4. **MCP Server**:
   - Always-running `FastMCP` server with configurable transport (STDIO or HTTP).
   - STDIO transport (default): Best for local desktop applications and CLI tools.
   - HTTP transport: Best for web applications and remote access via Server-Sent Events (SSE).
   - Exposes `check_blacklist` tool with input schema (`value: str`) and JSON output.
   - Reuses `storage.query_blacklist` for consistency.
   - Configurable via CLI arguments (`--transport`, `--host`, `--port`) or environment variables.

5. **Status Reporting**:
   - `mcp status` or `status()` returns:
     - Blacklist entry count.
     - Last update timestamp.
     - Active sources.
     - Server status ("Running (STDIO)" or "Running (HTTP on host:port)").

6. **Modular Architecture**:
   - Modules: `core` (orchestration), `update_blacklist` (feed management), `storage` (SQLite), `interface` (CLI/MCP server), `utility` (validation/logging).
   - Independent testing via dependency injection (e.g., mock `storage` in `update_blacklist`).

---

## 5. Architecture / Technical Design

### Blacklist Storage Schema (v2)

- The blacklist is now split into three separate tables for improved performance and clarity:
  - `blacklist_domain(domain TEXT PRIMARY KEY, date TEXT, score REAL, source TEXT)`
  - `blacklist_url(url TEXT PRIMARY KEY, date TEXT, score REAL, source TEXT)`
  - `blacklist_ip(ip TEXT PRIMARY KEY, date TEXT, score REAL, source TEXT)`
- This allows fast, type-specific lookups and avoids unnecessary full-table scans.
- All add/check/remove logic is routed to the appropriate table based on input type.

### Input Handling & CLI/API

- The core logic auto-detects input type (domain, URL, IP) and applies blacklist logic accordingly:
  - **Domain:** Checks domain and all parent domains in `blacklist_domain`.
  - **URL:** Checks for an exact match in `blacklist_url`, then extracts the domain and checks `blacklist_domain`.
  - **IP:** Checks for an exact match in `blacklist_ip`.
- New CLI commands:
  - `mcp check_domain <domain>`: Checks a domain and its parent domains.
  - `mcp check_url <url>`: Checks a URL and its domain.
  - `mcp check_ip <ip>`: Checks an IP address.
- The generic `mcp check <value>` command auto-detects type and uses the correct logic.
- Batch and status commands remain available.

---

## 6. Design & Technical Considerations

### Technical Stack
| **Component** | **Technology** | **Rationale** |
| --- | --- | --- |
| Library | Python 3.11 | Portable, widely used in cybersecurity, supports rapid development. |
| CLI | `click` | Simple, powerful CLI framework for developer-friendly commands. |
| MCP Server | `mcp[cli]` (`FastMCP`, STDIO) | Lightweight, aligns with MCP protocol for AI client integration. |
| Storage | SQLite | Lightweight, serverless database with indexing for high-throughput queries. |
| Blacklist Updates | `requests`, `schedule` | Reliable HTTP downloads and daily scheduling for automation. |
| Validation | `idna`, `urllib.parse`, `ipaddress` | Standard libraries for robust domain/URL/IP validation. |
| Progress | `tqdm` | Enhances CLI usability for batch operations. |
| Future Async | `httpx` | Prepares for async third-party API calls (e.g., Google Safe Browsing). |

### Package Structure
```
mcp_client/
├── __init__.py
├── core.py          # Orchestrates modules
├── update_blacklist.py  # Downloads, parses, validates feeds
├── storage.py       # SQLite operations
├── interface.py     # CLI, API, MCP server
├── utility.py       # Validation, logging, config
└── config.json      # Blacklist sources
```

### Design Principles
- **Modularity**: Each module is independent, with clear interfaces for testing (e.g., mock `storage` in `update_blacklist`).
- **Performance**: In-memory cache (~10k entries) and SQLite indexing ensure high throughput.
- **Extensibility**: `update_blacklist` supports new feed formats (e.g., JSON) via parser plugins.
- **Security**: Input validation and logging prevent errors and track issues.
- **Always-Running Server**: MCP server runs in a background thread, started automatically.

### Constraints
- **Budget**: Low-budget, using free feeds (OpenPhish, PhishStats, URLhaus) and local deployment.
- **Timeline**: 1-month MVP, achievable with 1-2 developers skilled in Python and cybersecurity.
- **Team Expertise**: Strong in Python and security, no major gaps.
- **Deployment**: Local Python package (`pip install mcp-client`), no cloud hosting.

---

## 7. Assumptions & Constraints

### Assumptions
- OpenPhish, PhishStats, and URLhaus will remain accessible and maintain their current formats/URLs during the MVP phase.
- SQLite can handle ~80k entries with sub-millisecond queries on standard developer hardware.
- Cybersecurity developers are familiar with Python and CLI tools, requiring minimal onboarding.
- MCP clients use STDIO transport for local server communication, per the MCP quickstart guide.
- Daily updates at 00:00 are sufficient; more frequent updates are not required for the MVP.

### Constraints
- **Budget**: No funding for cloud hosting, paid APIs, or premium feeds (e.g., OpenPhish premium).
- **Timeline**: 1-month deadline (by May 15, 2025) limits scope to core features and OpenPhish/PhishStats/URLhaus.
- **Blacklist Scope**: Limited to phishing/malware URLs due to feed constraints; IPs and domains are secondary.
- **PhishTank Unavailability**: Disabled due to registration restrictions, requiring alternative feeds.
- **MCP Server Scope**: Limited to `check_blacklist` tool, no additional tools or resources for MVP.

---

## 8. Open Questions / Future Considerations

### Open Questions
- **Success Metrics**: How will success be measured (e.g., number of integrations, check accuracy, update reliability)? **Recommendation**: Define metrics like “90% of checks return in <1s” or “100% update success rate over 30 days.”
- **Blacklist Overlap**: What is the acceptable overlap between feeds (e.g., OpenPhish vs. PhishStats)? **Recommendation**: Analyze deduplicated entry count post-MVP to optimize sources.
- **Error Notification**: Should update failures trigger developer alerts (e.g., email, CLI popup)? **Recommendation**: Add a CLI flag (e.g., `--notify`) for critical errors.
- **Testing Strategy**: How will modules be tested (e.g., unit tests, integration tests)? **Recommendation**: Develop unit tests for each module, mocking dependencies.

### Future Considerations
- **PhishTank Re-enablement**: Monitor PhishTank registration status or explore community mirrors for CSV feeds.
- **Additional Feeds**: Integrate feeds like AlienVault OTX or Spamhaus for broader threat coverage (e.g., IPs, domains).
- **Google Safe Browsing**: Add async `httpx` integration with caching in SQLite’s `cache` table.
- **MCP Enhancements**: Add tools (e.g., `update_blacklist`, `get_status`) or resources (e.g., blacklist metadata) for richer LLM workflows.
- **Performance Optimization**: Explore async downloads (`aiohttp`) or cloud storage for >1M entries.
- **Documentation**: Create a README and API reference for production use.

---
