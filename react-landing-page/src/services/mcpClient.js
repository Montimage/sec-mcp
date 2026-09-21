/**
 * Minimal browser client for MCP over streamable HTTP.
 *
 * The playground only needs four calls — initialize, tools/list, tools/call
 * and the initialized notification — so this speaks the wire format directly
 * with fetch instead of pulling in the MCP SDK: the landing page stays
 * dependency-light and the SSR prerender never touches it.
 *
 * Wire rules it honours (streamable-HTTP transport):
 *  - every message is a POST with `Accept: application/json, text/event-stream`;
 *  - the server may answer with plain JSON or an SSE stream — for SSE we read
 *    events until the response carrying our request id arrives (progress
 *    notifications before it are handed to `onNotification`);
 *  - `Mcp-Session-Id` from the initialize response is echoed on every later
 *    request, together with the negotiated `MCP-Protocol-Version`.
 */

const CLIENT_PROTOCOL_VERSION = '2025-06-18';
const DEFAULT_TIMEOUT_MS = 20000;

export class McpError extends Error {
    constructor(message, { code, kind = 'protocol' } = {}) {
        super(message);
        this.name = 'McpError';
        this.code = code;
        // 'network' — the request never reached a server (CORS, refused,
        // blocked local-network access); 'http' — a non-2xx status;
        // 'protocol' — a JSON-RPC error object.
        this.kind = kind;
    }
}

/** Resolve the endpoint a visitor typed into an absolute URL ending in /mcp. */
export const normalizeEndpoint = (raw) => {
    let value = String(raw ?? '').trim();
    if (!value) throw new McpError('Enter the server address, e.g. http://127.0.0.1:8000/mcp', { kind: 'input' });
    // A bare host[:port] means the local HTTP server — sec-mcp-server --http has no TLS.
    if (!/^https?:\/\//i.test(value)) value = `http://${value}`;
    let url;
    try {
        url = new URL(value);
    } catch {
        throw new McpError(`"${raw}" is not a valid URL.`, { kind: 'input' });
    }
    if (url.pathname === '/' || url.pathname === '') url.pathname = '/mcp';
    return url.href;
};

/** Pull JSON-RPC messages out of an SSE body, one `data:` block per event. */
async function* readSseMessages(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
        let boundary;
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
            const block = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);
            const data = block
                .split('\n')
                .filter((line) => line.startsWith('data:'))
                .map((line) => line.slice(5).replace(/^ /, ''))
                .join('\n');
            if (data) {
                try {
                    yield JSON.parse(data);
                } catch {
                    // keep-alive pings and non-JSON frames are not messages
                }
            }
        }
    }
}

export default class McpHttpClient {
    constructor(endpoint, { token, onNotification } = {}) {
        this.endpoint = normalizeEndpoint(endpoint);
        this.token = token || '';
        this.onNotification = onNotification;
        this.sessionId = null;
        this.protocolVersion = null;
        this.serverInfo = null;
        this.nextId = 1;
    }

    headers() {
        const headers = {
            'Content-Type': 'application/json',
            Accept: 'application/json, text/event-stream',
        };
        if (this.sessionId) headers['Mcp-Session-Id'] = this.sessionId;
        if (this.protocolVersion) headers['MCP-Protocol-Version'] = this.protocolVersion;
        if (this.token) headers.Authorization = `Bearer ${this.token}`;
        return headers;
    }

    async post(message, timeoutMs = DEFAULT_TIMEOUT_MS) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), timeoutMs);
        try {
            let response;
            try {
                response = await fetch(this.endpoint, {
                    method: 'POST',
                    headers: this.headers(),
                    body: JSON.stringify(message),
                    signal: controller.signal,
                    mode: 'cors',
                });
            } catch (err) {
                if (err.name === 'AbortError') {
                    throw new McpError(`No answer from ${this.endpoint} after ${timeoutMs / 1000}s.`, { kind: 'network' });
                }
                // fetch rejects with an opaque TypeError for refused
                // connections, CORS rejections and denied local-network
                // access alike — the UI explains all three.
                throw new McpError(`Could not reach ${this.endpoint}.`, { kind: 'network' });
            }

            const session = response.headers.get('mcp-session-id');
            if (session) this.sessionId = session;

            if (response.status === 202) return null; // notification accepted
            if (response.status === 401) {
                throw new McpError('The server wants a bearer token (SEC_MCP_HTTP_AUTH_TOKEN).', { kind: 'http', code: 401 });
            }
            if (!response.ok) {
                const text = await response.text().catch(() => '');
                let detail = text.slice(0, 200);
                try {
                    detail = JSON.parse(text)?.error?.message || detail;
                } catch {
                    // plain-text error body
                }
                throw new McpError(`HTTP ${response.status}${detail ? ` — ${detail}` : ''}`, { kind: 'http', code: response.status });
            }

            const type = response.headers.get('content-type') || '';
            if (type.includes('text/event-stream')) {
                for await (const msg of readSseMessages(response)) {
                    if (msg.id === message.id && ('result' in msg || 'error' in msg)) return msg;
                    if (msg.method && this.onNotification) this.onNotification(msg);
                }
                throw new McpError('The event stream closed before the server answered.');
            }
            return await response.json();
        } finally {
            clearTimeout(timer);
        }
    }

    async request(method, params, timeoutMs) {
        const id = this.nextId++;
        const reply = await this.post({ jsonrpc: '2.0', id, method, ...(params ? { params } : {}) }, timeoutMs);
        if (!reply) throw new McpError(`Empty reply to ${method}.`);
        if (reply.error) {
            throw new McpError(reply.error.message || `${method} failed`, { code: reply.error.code });
        }
        return reply.result;
    }

    async connect() {
        const result = await this.request('initialize', {
            protocolVersion: CLIENT_PROTOCOL_VERSION,
            capabilities: {},
            clientInfo: { name: 'sec-mcp-landing-playground', version: '1.0.0' },
        });
        this.protocolVersion = result.protocolVersion || CLIENT_PROTOCOL_VERSION;
        this.serverInfo = result.serverInfo || null;
        await this.post({ jsonrpc: '2.0', method: 'notifications/initialized' });
        return result;
    }

    async listTools() {
        const result = await this.request('tools/list', {});
        return result.tools || [];
    }

    /** Call a tool; a progress token lets update_blacklists stream per-feed progress. */
    async callTool(name, args = {}, { timeoutMs } = {}) {
        return this.request(
            'tools/call',
            { name, arguments: args, _meta: { progressToken: `pg-${this.nextId}` } },
            timeoutMs,
        );
    }

    /** Best-effort session teardown — the server also expires idle sessions. */
    async close() {
        if (!this.sessionId) return;
        try {
            await fetch(this.endpoint, { method: 'DELETE', headers: this.headers(), mode: 'cors' });
        } catch {
            // nothing to do: the page is moving on either way
        }
        this.sessionId = null;
    }
}
