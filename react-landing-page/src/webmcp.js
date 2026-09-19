// WebMCP (navigator.modelContext) — registers informational tools so
// agentic browsers can query what this page is about. The API is an
// early-stage spec; where it is absent this module is a no-op, and a
// failed registration must never break page boot.
const tools = [
    {
        name: 'sec_mcp_install',
        description:
            'Install and first-run instructions for sec-mcp, the Python blacklist-checking toolkit (library, CLI, MCP server)',
        inputSchema: { type: 'object', properties: {} },
        execute: async () => ({
            content: [
                {
                    type: 'text',
                    text:
                        'pip install sec-mcp (Python 3.11+, MIT) → sec-mcp update (index the feeds) → ' +
                        'sec-mcp check <domain|url|ip>. Package: https://pypi.org/project/sec-mcp/ · ' +
                        'Source: https://github.com/montimage/sec-mcp',
                },
            ],
        }),
    },
    {
        name: 'sec_mcp_api_overview',
        description:
            'The sec-mcp API surface: Python methods, CheckResult/StatusInfo dataclasses, and the six MCP server tools',
        inputSchema: { type: 'object', properties: {} },
        execute: async () => ({
            content: [
                {
                    type: 'text',
                    text:
                        'Python: check/check_domain/check_url/check_ip(value) → CheckResult(is_safe, explanation); ' +
                        'check_batch(values); get_status() → StatusInfo; update(); sample(n); scheduler_alive(). ' +
                        'MCP tools: check_batch, get_status, update_blacklists, get_diagnostics, add_entry, remove_entry. ' +
                        'Ten feeds indexed locally: OpenPhish, PhishStats, URLhaus, PhishTank, Spamhaus DROP, DShield, ' +
                        'CINS Score, Emerging Threats, Feodo Tracker, Blocklist.de.',
                },
            ],
        }),
    },
];

if (typeof navigator !== 'undefined' && navigator.modelContext) {
    try {
        for (const tool of tools) navigator.modelContext.registerTool(tool);
    } catch {
        // spec still in flux — ignore registration failures
    }
}
