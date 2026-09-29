/**
 * Simulation mode — what the playground answers with when no sec-mcp server
 * is connected.
 *
 * The deployed page has no server behind it, so rather than show a dead
 * console it replays a small, fixed demo dataset. Two rules:
 *
 *  1. Never pretend. Every simulated result is labelled as such in the UI,
 *     and a value outside the demo set gets an honest "unknown" instead of a
 *     guessed verdict.
 *  2. Blacklisted samples use reserved names only — `.example`/`.test`
 *     domains (RFC 2606) and documentation IP ranges (RFC 5737) — so the demo
 *     never accuses a real host.
 *
 * Explanation strings match sec_mcp/sec_mcp.py verbatim ("Not blacklisted",
 * "Blacklisted URL by OpenPhish", ...), and TOOLS mirrors the server's
 * tools/list, so switching to a live server changes the data, not the shape.
 */

export const SIMULATED_LATENCY_MS = 180;

// Mirrors `tools/list` from sec_mcp/mcp_server.py (names, titles, schemas).
export const TOOLS = [
    {
        name: 'check_batch',
        title: 'Check Batch',
        description: 'Check multiple domains/URLs/IPs in one call. Returns list of {value, is_safe, verdict, explanation}.',
        inputSchema: {
            type: 'object',
            properties: {
                values: {
                    type: 'array',
                    items: { type: 'string' },
                    description: 'Domains, URLs or IP addresses to check against the blacklists.',
                },
            },
            required: ['values'],
        },
        annotations: { readOnlyHint: true },
    },
    {
        name: 'get_status',
        title: 'Get Status',
        description: 'Get blacklist status including entry counts and sources.',
        inputSchema: { type: 'object', properties: {} },
        annotations: { readOnlyHint: true },
    },
    {
        name: 'update_blacklists',
        title: 'Update Blacklists',
        description: 'Force immediate update of all blacklists. Rate limited.',
        inputSchema: { type: 'object', properties: {} },
        annotations: { readOnlyHint: false, openWorldHint: true },
    },
    {
        name: 'get_diagnostics',
        title: 'Get Diagnostics',
        description: "Get diagnostic information. Mode options: 'summary' (default), 'full', 'health', 'performance', 'sample'.",
        inputSchema: {
            type: 'object',
            properties: {
                mode: { type: 'string', enum: ['summary', 'full', 'health', 'performance', 'sample'], default: 'summary' },
                sample_count: { type: 'integer', minimum: 1, maximum: 100, default: 10 },
            },
        },
        annotations: { readOnlyHint: true },
    },
    {
        name: 'add_entry',
        title: 'Add Entry',
        description: 'Add a manual blacklist entry.',
        inputSchema: {
            type: 'object',
            properties: {
                url: { type: 'string', description: 'URL or domain to blacklist (scheme added if missing).' },
                ip: { type: 'string', description: 'IPv4 or IPv6 address to blacklist.' },
                score: { type: 'number', minimum: 0, maximum: 10, default: 8.0 },
            },
        },
        annotations: { readOnlyHint: false },
    },
    {
        name: 'remove_entry',
        title: 'Remove Entry',
        description: 'Remove a blacklist entry by URL or IP.',
        inputSchema: {
            type: 'object',
            properties: { value: { type: 'string', description: 'Domain, URL or IP address to remove from the blacklist.' } },
            required: ['value'],
        },
        annotations: { readOnlyHint: false, destructiveHint: true },
    },
];

// The demo dataset, keyed by the lower-cased value.
const DEMO_VERDICTS = {
    'example.com': null,
    'github.com': null,
    'pypi.org': null,
    '8.8.8.8': null,
    '1.1.1.1': null,
    'https://example.com/path': null,
    'http://signin-verify.example/account': 'Blacklisted URL by OpenPhish',
    'signin-verify.example': 'Blacklisted domain by OpenPhish',
    'invoice-update.test': 'Blacklisted domain by PhishTank',
    'http://payload-cdn.test/dropper.bin': 'Blacklisted URL by URLhaus',
    '203.0.113.66': 'Blacklisted IP by FeodoTracker',
    '198.51.100.23': 'Blacklisted IP by SpamhausDROP',
    '192.0.2.200': 'Blacklisted IP by CINSSCORE',
};

export const DEMO_VALUES = Object.keys(DEMO_VERDICTS);

const DOMAIN = /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\.?$/i;
const URL_LIKE = /^https?:\/\/[^\s/?#]+(?:[/?#]\S*)?$/i;

const isIp = (value) => {
    const v4 = value.split('.');
    if (v4.length === 4 && v4.every((p) => /^\d{1,3}$/.test(p) && Number(p) <= 255)) return true;
    return value.includes(':') && /^[0-9a-f:.]+$/i.test(value);
};

/** Close cousin of sec_mcp.utility.validate_input — good enough for a demo. */
export const looksValid = (value) => DOMAIN.test(value) || URL_LIKE.test(value) || isIp(value);

const checkOne = (value) => {
    if (!looksValid(value)) {
        return { value, is_safe: false, verdict: 'invalid', explanation: 'Invalid input format.' };
    }
    const key = value.toLowerCase();
    if (key in DEMO_VERDICTS) {
        const hit = DEMO_VERDICTS[key];
        return hit
            ? { value, is_safe: false, verdict: 'blacklisted', explanation: hit }
            : { value, is_safe: true, verdict: 'safe', explanation: 'Not blacklisted' };
    }
    return {
        value,
        is_safe: null,
        verdict: 'unknown',
        explanation: 'Not in the demo dataset. Connect a server for a real verdict.',
    };
};

const SOURCE_COUNTS = {
    OpenPhish: 312,
    PhishStats: 41250,
    URLhaus: 18904,
    PhishTank: 52713,
    SpamhausDROP: 1417,
    Dshield: 20,
    CINSSCORE: 15000,
    EmergingThreats: 1523,
    FeodoTracker: 408,
    BlocklistDE: 27816,
};

const totalEntries = Object.values(SOURCE_COUNTS).reduce((a, b) => a + b, 0);

const structured = (payload, isError = false) => ({
    content: [{ type: 'text', text: typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2) }],
    ...(isError ? { isError: true } : { structuredContent: Array.isArray(payload) ? { result: payload } : payload }),
});

/** Answer a tools/call the way the server would — shape-for-shape. */
export const simulateTool = async (name, args = {}) => {
    await new Promise((resolve) => setTimeout(resolve, SIMULATED_LATENCY_MS));
    const now = new Date().toISOString().slice(0, 19);

    switch (name) {
        case 'check_batch': {
            const values = Array.isArray(args.values) ? args.values : [];
            return structured(values.map((v) => checkOne(String(v))));
        }
        case 'get_status':
            return structured({
                entry_count: totalEntries,
                last_update: now,
                sources: Object.keys(SOURCE_COUNTS),
                server_status: 'Running (simulation)',
                source_counts: SOURCE_COUNTS,
                scheduler_alive: true,
            });
        case 'get_diagnostics':
            return structured({
                mode: args.mode || 'summary',
                total_entries: totalEntries,
                per_source: SOURCE_COUNTS,
                db_ok: true,
                scheduler_alive: true,
                message: 'Simulated diagnostics — connect a server for live numbers.',
            });
        case 'update_blacklists':
            return structured({ updated: false, reason: 'Simulation mode: there are no feeds to refresh.' });
        case 'add_entry':
        case 'remove_entry':
            return structured('Simulation mode is read-only. Connect your own server to manage entries.', true);
        default:
            throw new Error(`Unknown tool: ${name}`);
    }
};

export const SIMULATED_STATUS = { entryCount: totalEntries, sources: Object.keys(SOURCE_COUNTS).length };
