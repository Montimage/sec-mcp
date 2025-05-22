# Sec-MCP Playbook: Top 10 Use Cases

## Table of Contents
1. [Introduction](#introduction)
2. [Top 10 Use Cases](#top-10-use-cases)
   - [1. Check Suspicious URLs](#1-check-suspicious-urls)
   - [2. Block Phishing Domains](#2-block-phishing-domains)
   - [3. Monitor IP Reputation](#3-monitor-ip-reputation)
   - [4. Investigate Security Alerts](#4-investigate-security-alerts)
   - [5. Update Security Feeds](#5-update-security-feeds)
   - [6. Audit Blacklist Entries](#6-audit-blacklist-entries)
   - [7. Handle False Positives](#7-handle-false-positives)
   - [8. Track Threat Intelligence](#8-track-threat-intelligence)
   - [9. Generate Security Reports](#9-generate-security-reports)
   - [10. Automate Security Workflows](#10-automate-security-workflows)
3. [Getting Help](#getting-help)

## Introduction

Welcome to the sec-mcp playbook! This guide highlights the top 10 ways you can leverage sec-mcp to enhance your security operations. Each use case includes practical examples you can use directly in your MCP client.

## Getting Started with Sec-MCP

For detailed instructions on how to install, configure, and enable `sec-mcp` in your MCP client (such as Claude Desktop or other applications), please refer to the main [README.md](../README.md) file of this project.

Once `sec-mcp` is set up, you can use the prompts in this playbook to leverage its security capabilities.

## Top 10 Use Cases

### 1. Check Suspicious URLs
Quickly verify if a URL is known to be malicious.

```
Check if https://suspicious-site.com/login is in the blacklist
```

### 2. Block Phishing Domains
Add newly discovered phishing domains to prevent access.

```
Add phishing-example.com to the blacklist with high severity
```

### 3. Monitor IP Reputation
Check if an IP address is associated with malicious activity.

```
Is 192.168.1.100 in the blacklist?
Show recent activity from 10.0.0.0/24
```

### 4. Investigate Security Alerts
Research potential security incidents.

```
Show me all blacklisted items related to 'creditcard'
What's the reputation of malware-hash:abc123?
```

### 5. Update Security Feeds
Keep your blacklists current with the latest threat intelligence.

```
Update all threat intelligence feeds
When was the last blacklist update?
```

### 6. Audit Blacklist Entries
Review and manage existing blacklist entries.

```
Show me all entries added in the last 7 days
Remove false-positive.example.com from the blacklist
```

### 7. Handle False Positives
Quickly resolve incorrect blacklist entries.

```
Remove safe-site.com from the blacklist
Add safe-site.com to the whitelist
```

### 8. Track Threat Intelligence
Monitor emerging threats and patterns.

```
Show me trending malicious domains this week
What's the most common threat type in the last 30 days?
```

### 9. Generate Security Reports
Create reports for compliance and analysis.

```
Generate a report of all blacklisted items by category
Export all high-severity threats from last month
```

### 10. Automate Security Workflows
Integrate with other security tools.

```
When a new phishing email is detected, add all URLs to blacklist
Alert me when a high-severity threat is detected
```

## Getting Help

For additional assistance, please refer to:
- [Documentation](README.md)
- [API Reference](API.md)
- [Frequently Asked Questions](FAQ.md)

---
*Last updated: 2025-05-22*
