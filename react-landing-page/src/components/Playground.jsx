import React, { useCallback, useEffect, useId, useRef, useState } from 'react';
import McpHttpClient, { McpError } from '../services/mcpClient';
import { DEMO_VALUES, SIMULATED_STATUS, TOOLS, simulateTool } from '../services/simulation';

/**
 * The page's headline feature: a console that talks to a real sec-mcp server
 * over streamable HTTP — or, until one is connected, answers from a labelled
 * demo dataset.
 *
 * Two tabs, two jobs:
 *  - "Check values" is the 90% case: paste domains/URLs/IPs, get verdicts.
 *    It is just check_batch with a friendlier input.
 *  - "Call any tool" drives every tool the server lists, with JSON arguments
 *    prefilled from the tool's inputSchema.
 *
 * Playbooks elsewhere on the page drive this console through a window event
 * (PLAYGROUND_EVENT) rather than shared React state, so the hero does not have
 * to own the whole page.
 */

export const PLAYGROUND_EVENT = 'secmcp:playground';
export const DEFAULT_ENDPOINT = 'http://127.0.0.1:8000/mcp';

// Origins sec-mcp-server --http allows without configuration (keep in sync
// with the SEC_MCP_CORS_ORIGINS default in sec_mcp/http_transport.py).
const DEFAULT_CORS_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:4173',
    'http://127.0.0.1:4173',
    'https://montimage.github.io',
];

const STORE_KEY = 'sec-mcp:playground';
const SAMPLE_CHIPS = ['example.com', 'signin-verify.example', '203.0.113.66', '8.8.8.8', 'not a domain'];

const readStore = () => {
    try {
        return JSON.parse(window.localStorage.getItem(STORE_KEY) || '{}');
    } catch {
        return {};
    }
};
const writeStore = (patch) => {
    try {
        window.localStorage.setItem(STORE_KEY, JSON.stringify({ ...readStore(), ...patch }));
    } catch {
        // private mode / blocked storage: the console still works, it just forgets
    }
};

const isLoopbackPage = () =>
    typeof window !== 'undefined' && /^(localhost|127\.\d+\.\d+\.\d+|\[::1\])$/.test(window.location.hostname);

/** Split pasted text into values: newlines, commas and spaces all separate. */
export const parseValues = (text) =>
    String(text)
        .split(/[\s,]+/)
        .map((v) => v.trim())
        .filter(Boolean);

/** Seed a JSON argument object from a tool's inputSchema. */
const argsTemplate = (tool) => {
    const props = tool?.inputSchema?.properties || {};
    const out = {};
    for (const [key, schema] of Object.entries(props)) {
        if (key === 'source' || key === 'date') continue; // server-side defaults are the right ones
        if (schema.default !== undefined && schema.default !== null) out[key] = schema.default;
        else if (schema.type === 'array') out[key] = key === 'values' ? ['example.com', '203.0.113.66'] : [];
        else if (tool.inputSchema.required?.includes(key)) out[key] = '';
    }
    return JSON.stringify(out, null, 2);
};

// Optional fields a mode does not fill arrive as null — noise in the
// readable view (the raw JSON-RPC pane still shows them).
const dropNulls = (value) =>
    value && typeof value === 'object' && !Array.isArray(value)
        ? Object.fromEntries(Object.entries(value).filter(([, v]) => v !== null))
        : value;

/** The payload a tool result carries: structured content first, text as a fallback. */
const payloadOf = (result) => {
    if (result?.structuredContent !== undefined) {
        const sc = result.structuredContent;
        return sc && typeof sc === 'object' && 'result' in sc && Object.keys(sc).length === 1 ? sc.result : dropNulls(sc);
    }
    const text = (result?.content || []).filter((c) => c.type === 'text').map((c) => c.text).join('\n');
    try {
        return JSON.parse(text);
    } catch {
        return text;
    }
};

const VERDICT_STYLE = {
    safe: 'border-line-signal text-signal',
    blacklisted: 'border-danger/50 text-danger',
    invalid: 'border-warn/50 text-warn',
    unknown: 'border-line-2 text-faint',
};

// ---------------------------------------------------------------------------

const StatusRing = ({ tone }) => (
    // A hollow ring, not a filled dot: the palette never fills with green.
    <span
        aria-hidden="true"
        className={`inline-block h-2 w-2 shrink-0 rounded-full border-2 ${
            tone === 'live' ? 'border-signal' : tone === 'error' ? 'border-danger' : tone === 'busy' ? 'border-dim animate-pulse' : 'border-warn'
        }`}
    />
);

const CheckResults = ({ items }) => {
    const counts = items.reduce((acc, it) => ({ ...acc, [it.verdict]: (acc[it.verdict] || 0) + 1 }), {});
    return (
        <>
            <p className="font-mono text-[0.6875rem] tracking-[0.14em] uppercase text-faint">
                {items.length} checked
                {counts.blacklisted ? <span className="text-danger"> · {counts.blacklisted} blacklisted</span> : null}
                {counts.safe ? <span className="text-signal"> · {counts.safe} safe</span> : null}
                {counts.invalid ? <span className="text-warn"> · {counts.invalid} invalid</span> : null}
                {counts.unknown ? <span> · {counts.unknown} unknown</span> : null}
            </p>
            <ul className="mt-3 divide-y divide-line border-y border-line">
                {items.map((it, i) => (
                    <li key={`${it.value}-${i}`} className="grid grid-cols-[6.75rem_minmax(0,1fr)] items-baseline gap-x-3 py-2.5">
                        <span
                            className={`inline-flex w-fit items-center border px-1.5 py-0.5 font-mono text-[0.625rem] tracking-[0.14em] uppercase ${
                                VERDICT_STYLE[it.verdict] || VERDICT_STYLE.unknown
                            }`}
                        >
                            {it.verdict}
                        </span>
                        <span className="min-w-0">
                            <code className="block break-all font-mono text-[0.8125rem] text-bright">{it.value}</code>
                            <span className="mt-0.5 block text-xs text-dim">{it.explanation}</span>
                        </span>
                    </li>
                ))}
            </ul>
        </>
    );
};

const JsonView = ({ value, tone = 'text-dim' }) => (
    <pre className={`scroll-thin max-h-72 overflow-auto whitespace-pre-wrap break-words font-mono text-xs leading-relaxed ${tone}`}>
        {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
    </pre>
);

// ---------------------------------------------------------------------------

const Playground = ({ onStatusChange }) => {
    const uid = useId();
    const clientRef = useRef(null);
    const textareaRef = useRef(null);

    const [endpoint, setEndpoint] = useState(DEFAULT_ENDPOINT);
    const [token, setToken] = useState('');
    const [showToken, setShowToken] = useState(false);
    // idle → connecting → live | error. Anything but 'live' answers from the simulation.
    const [conn, setConn] = useState({ status: 'idle', error: null, server: null, tools: null });
    const [dataStatus, setDataStatus] = useState(null); // { entryCount, sources } from get_status

    const [tab, setTab] = useState('check');
    const [checkText, setCheckText] = useState('example.com\nsignin-verify.example\n203.0.113.66');
    const [toolName, setToolName] = useState('get_status');
    const [argsText, setArgsText] = useState('{}');
    const [argsError, setArgsError] = useState(null);

    const [running, setRunning] = useState(false);
    const [result, setResult] = useState(null);
    const [progress, setProgress] = useState(null);

    const live = conn.status === 'live';
    const tools = live && conn.tools?.length ? conn.tools : TOOLS;
    const selectedTool = tools.find((t) => t.name === toolName) || tools[0];

    // ---- connection ------------------------------------------------------

    const disconnect = useCallback(() => {
        clientRef.current?.close();
        clientRef.current = null;
        setConn({ status: 'idle', error: null, server: null, tools: null });
        setDataStatus(null);
        writeStore({ connected: false });
    }, []);

    const connect = useCallback(async (target, bearer, { quiet = false } = {}) => {
        let client;
        try {
            client = new McpHttpClient(target, {
                token: bearer,
                onNotification: (msg) => {
                    if (msg.method === 'notifications/progress') setProgress(msg.params);
                },
            });
        } catch (err) {
            setConn({ status: 'error', error: err, server: null, tools: null });
            return;
        }
        setConn((c) => ({ ...c, status: 'connecting', error: null }));
        try {
            const init = await client.connect();
            const listed = await client.listTools();
            clientRef.current = client;
            setConn({
                status: 'live',
                error: null,
                server: { ...init.serverInfo, protocolVersion: client.protocolVersion, endpoint: client.endpoint },
                tools: listed,
            });
            writeStore({ endpoint: client.endpoint, connected: true });
            // Probe the database so the checklist can say whether verdicts mean anything yet.
            try {
                const status = payloadOf(await client.callTool('get_status'));
                setDataStatus({ entryCount: status.entry_count ?? 0, sources: status.sources?.length ?? 0 });
            } catch {
                setDataStatus(null);
            }
        } catch (err) {
            clientRef.current = null;
            setConn({ status: quiet ? 'idle' : 'error', error: quiet ? null : err, server: null, tools: null });
        }
    }, []);

    // Restore the last endpoint. Only auto-connect where it cannot surprise
    // anyone: on a loopback-served page, or when this visitor connected
    // before (a public page probing localhost unprompted would trigger the
    // browser's local-network permission prompt on first visit).
    useEffect(() => {
        const saved = readStore();
        const target = saved.endpoint || DEFAULT_ENDPOINT;
        setEndpoint(target);
        if (isLoopbackPage() || saved.connected) connect(target, '', { quiet: true });
        return () => clientRef.current?.close();
    }, [connect]);

    // Report to the hero's first-run checklist.
    useEffect(() => {
        onStatusChange?.({
            server: conn.status === 'live' ? 'ok' : conn.status === 'error' ? 'fail' : conn.status === 'connecting' ? 'checking' : 'idle',
            data: !live ? 'idle' : dataStatus == null ? 'checking' : dataStatus.entryCount > 0 ? 'ok' : 'fail',
            entryCount: dataStatus?.entryCount ?? null,
        });
    }, [conn.status, live, dataStatus, onStatusChange]);

    // ---- running ---------------------------------------------------------

    const runTool = useCallback(
        async (name, args, view) => {
            const tool = tools.find((t) => t.name === name);
            if (live && tool?.annotations?.destructiveHint && !window.confirm(`${name} changes your local blacklist. Run it?`)) return;

            setRunning(true);
            setProgress(null);
            const started = performance.now();
            const request = { jsonrpc: '2.0', method: 'tools/call', params: { name, arguments: args } };
            try {
                const raw = live
                    ? await clientRef.current.callTool(name, args, { timeoutMs: name === 'update_blacklists' ? 600000 : undefined })
                    : await simulateTool(name, args);
                setResult({ view, name, args, request, raw, payload: payloadOf(raw), isError: !!raw.isError, ms: Math.round(performance.now() - started), live });
            } catch (err) {
                setResult({ view, name, args, request, error: err, ms: Math.round(performance.now() - started), live });
                // A dropped session or a stopped server: fall back so the next run still answers.
                if (live && err instanceof McpError && err.kind !== 'protocol') {
                    setConn((c) => ({ ...c, status: 'error', error: err }));
                    clientRef.current = null;
                }
            } finally {
                setRunning(false);
                setProgress(null);
            }
        },
        [live, tools],
    );

    const runCheck = useCallback(
        (text = checkText) => {
            const values = parseValues(text);
            if (!values.length) {
                setResult({ view: 'check', inputError: 'Enter at least one domain, URL or IP address.' });
                textareaRef.current?.focus();
                return;
            }
            runTool('check_batch', { values }, 'check');
        },
        [checkText, runTool],
    );

    const runSelectedTool = useCallback(
        (text = argsText, name = selectedTool?.name) => {
            let args;
            try {
                args = text.trim() ? JSON.parse(text) : {};
                if (typeof args !== 'object' || Array.isArray(args) || args === null) throw new Error('Arguments must be a JSON object.');
            } catch (err) {
                setArgsError(err.message.replace(/^JSON\.parse: /, ''));
                return;
            }
            setArgsError(null);
            runTool(name, args, 'tool');
        },
        [argsText, selectedTool, runTool],
    );

    const selectTool = (name) => {
        const tool = tools.find((t) => t.name === name);
        setToolName(name);
        setArgsText(argsTemplate(tool));
        setArgsError(null);
    };

    // Playbooks → console.
    useEffect(() => {
        const onRun = (event) => {
            const { values, tool, args } = event.detail || {};
            if (values) {
                const text = values.join('\n');
                setTab('check');
                setCheckText(text);
                runCheck(text);
            } else if (tool) {
                const text = JSON.stringify(args || {}, null, 2);
                setTab('tools');
                setToolName(tool);
                setArgsText(text);
                runSelectedTool(text, tool);
            }
        };
        window.addEventListener(PLAYGROUND_EVENT, onRun);
        return () => window.removeEventListener(PLAYGROUND_EVENT, onRun);
    }, [runCheck, runSelectedTool]);

    const submitOnCmdEnter = (fn) => (event) => {
        if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
            event.preventDefault();
            fn();
        }
    };

    // ---- help for a failed connection ------------------------------------

    const origin = typeof window !== 'undefined' ? window.location.origin : '';
    const originNeedsConfig = origin && !DEFAULT_CORS_ORIGINS.includes(origin);
    const serveCommand = `${originNeedsConfig ? `SEC_MCP_CORS_ORIGINS=${origin} ` : ''}sec-mcp-server --http`;

    const modeLabel = live
        ? `Live · ${conn.server?.name || 'sec-mcp'}${conn.server?.version ? ` ${conn.server.version}` : ''}`
        : conn.status === 'connecting'
          ? 'Connecting…'
          : 'Simulation';

    const tabs = [
        { id: 'check', label: 'Check values' },
        { id: 'tools', label: 'Call any tool' },
    ];

    return (
        <section
            aria-labelledby={`${uid}-title`}
            className="border border-line bg-raise shadow-2xl shadow-black/60"
        >
            {/* --- window chrome ---------------------------------------------- */}
            <header className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line px-4 py-3">
                <h2 id={`${uid}-title`} className="font-mono text-xs tracking-[0.18em] uppercase text-bright">
                    <span className="text-signal">sec-mcp</span>
                    <span className="mx-1.5 text-faint" aria-hidden="true">/</span>
                    playground
                </h2>
                <p
                    className={`ml-auto flex items-center gap-2 font-mono text-[0.6875rem] tracking-[0.14em] uppercase ${
                        live ? 'text-signal' : conn.status === 'connecting' ? 'text-dim' : 'text-warn'
                    }`}
                    role="status"
                >
                    <StatusRing tone={live ? 'live' : conn.status === 'connecting' ? 'busy' : 'sim'} />
                    {modeLabel}
                </p>
            </header>

            {/* --- server strip ------------------------------------------------ */}
            <form
                className="border-b border-line px-4 py-3"
                onSubmit={(e) => {
                    e.preventDefault();
                    if (live) disconnect();
                    else connect(endpoint, token);
                }}
            >
                <label htmlFor={`${uid}-endpoint`} className="font-mono text-[0.6875rem] tracking-[0.16em] uppercase text-faint">
                    MCP server
                </label>
                <div className="mt-1.5 flex gap-2">
                    <input
                        id={`${uid}-endpoint`}
                        type="text"
                        inputMode="url"
                        spellCheck="false"
                        autoComplete="off"
                        value={endpoint}
                        disabled={live || conn.status === 'connecting'}
                        onChange={(e) => setEndpoint(e.target.value)}
                        className="h-10 min-w-0 flex-1 border border-line-2 bg-void px-3 font-mono text-[0.8125rem] text-bright placeholder:text-faint focus:border-signal focus:outline-none disabled:text-dim"
                        placeholder={DEFAULT_ENDPOINT}
                    />
                    <button
                        type="submit"
                        disabled={conn.status === 'connecting'}
                        className={`h-10 shrink-0 px-4 font-mono text-xs font-medium tracking-[0.14em] uppercase transition-colors disabled:cursor-wait ${
                            live
                                ? 'border border-mute text-dim hover:border-bright hover:text-bright'
                                : 'bg-bright text-void hover:bg-dim'
                        }`}
                    >
                        {live ? 'Disconnect' : conn.status === 'connecting' ? 'Connecting' : 'Connect'}
                    </button>
                </div>

                {!live && (
                    <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                        <button
                            type="button"
                            onClick={() => setShowToken((v) => !v)}
                            aria-expanded={showToken}
                            className="font-mono text-[0.6875rem] tracking-[0.12em] uppercase text-faint underline decoration-line-2 underline-offset-4 transition-colors hover:text-bright"
                        >
                            {showToken ? 'Hide token' : 'Server needs a token?'}
                        </button>
                        <span className="text-xs text-faint">
                            Start one with <code className="font-mono text-dim">{serveCommand}</code>
                        </span>
                    </div>
                )}
                {!live && showToken && (
                    <div className="mt-2">
                        <label htmlFor={`${uid}-token`} className="sr-only">Bearer token</label>
                        <input
                            id={`${uid}-token`}
                            type="password"
                            autoComplete="off"
                            value={token}
                            onChange={(e) => setToken(e.target.value)}
                            placeholder="SEC_MCP_HTTP_AUTH_TOKEN (kept in this tab only)"
                            className="h-9 w-full border border-line-2 bg-void px-3 font-mono text-xs text-bright placeholder:text-faint focus:border-signal focus:outline-none"
                        />
                    </div>
                )}

                {conn.status === 'error' && conn.error && (
                    <div className="mt-3 border-l border-danger/60 pl-3 text-xs leading-relaxed text-dim" role="alert">
                        <p className="text-danger">{conn.error.message}</p>
                        {conn.error.kind === 'network' && (
                            <ul className="mt-1.5 list-disc space-y-1 pl-4">
                                <li>
                                    Is the server running? <code className="font-mono text-bright">{serveCommand}</code>
                                </li>
                                <li>If your browser asks to access devices on your local network, allow it.</li>
                                <li>Brave and Safari may block localhost from https pages — run the page locally instead.</li>
                            </ul>
                        )}
                        <p className="mt-1.5 text-faint">Meanwhile the console answers from the demo dataset.</p>
                    </div>
                )}
            </form>

            {/* --- tabs ----------------------------------------------------------- */}
            <div role="tablist" aria-label="Playground mode" className="flex border-b border-line">
                {tabs.map((t) => (
                    <button
                        key={t.id}
                        id={`${uid}-tab-${t.id}`}
                        type="button"
                        role="tab"
                        aria-selected={tab === t.id}
                        aria-controls={`${uid}-panel-${t.id}`}
                        tabIndex={tab === t.id ? 0 : -1}
                        onClick={() => setTab(t.id)}
                        onKeyDown={(e) => {
                            if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                                const next = tab === 'check' ? 'tools' : 'check';
                                setTab(next);
                                document.getElementById(`${uid}-tab-${next}`)?.focus();
                            }
                        }}
                        className={`-mb-px flex-1 border-b px-4 py-3 font-mono text-xs tracking-[0.14em] uppercase transition-colors ${
                            tab === t.id ? 'border-signal text-bright' : 'border-transparent text-faint hover:text-bright'
                        }`}
                    >
                        {t.label}
                    </button>
                ))}
            </div>

            {/* --- input panel ---------------------------------------------------- */}
            <div className="px-4 py-4">
                {tab === 'check' ? (
                    <div id={`${uid}-panel-check`} role="tabpanel" aria-labelledby={`${uid}-tab-check`}>
                        <label htmlFor={`${uid}-values`} className="text-sm text-dim">
                            Domains, URLs or IPs — one per line
                        </label>
                        <textarea
                            ref={textareaRef}
                            id={`${uid}-values`}
                            rows={4}
                            spellCheck="false"
                            value={checkText}
                            onChange={(e) => setCheckText(e.target.value)}
                            onKeyDown={submitOnCmdEnter(() => runCheck())}
                            className="scroll-thin mt-2 block w-full resize-y border border-line-2 bg-void px-3 py-2.5 font-mono text-[0.8125rem] leading-relaxed text-bright focus:border-signal focus:outline-none"
                        />
                        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                            <span className="mr-1 font-mono text-[0.625rem] tracking-[0.14em] uppercase text-faint">Add</span>
                            {SAMPLE_CHIPS.map((chip) => (
                                <button
                                    key={chip}
                                    type="button"
                                    onClick={() => setCheckText((t) => (t.trim() ? `${t.trimEnd()}\n${chip}` : chip))}
                                    className="border border-line-2 px-2 py-1 font-mono text-[0.6875rem] text-dim transition-colors hover:border-signal hover:text-signal"
                                >
                                    + {chip}
                                </button>
                            ))}
                        </div>
                        <RunRow running={running} label="Run check" hint="check_batch" onRun={() => runCheck()} />
                    </div>
                ) : (
                    <div id={`${uid}-panel-tools`} role="tabpanel" aria-labelledby={`${uid}-tab-tools`}>
                        <div className="grid gap-3 sm:grid-cols-[minmax(0,13rem)_minmax(0,1fr)]">
                            <div>
                                <label htmlFor={`${uid}-tool`} className="text-sm text-dim">Tool</label>
                                <select
                                    id={`${uid}-tool`}
                                    value={selectedTool?.name}
                                    onChange={(e) => selectTool(e.target.value)}
                                    className="mt-2 h-10 w-full border border-line-2 bg-void px-2.5 font-mono text-[0.8125rem] text-bright focus:border-signal focus:outline-none"
                                >
                                    {tools.map((t) => (
                                        <option key={t.name} value={t.name}>
                                            {t.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <p className="self-end text-xs leading-relaxed text-dim sm:pb-1">
                                {selectedTool?.description}
                                {selectedTool?.annotations?.destructiveHint && <span className="text-warn"> Destructive.</span>}
                            </p>
                        </div>
                        <label htmlFor={`${uid}-args`} className="mt-3 block text-sm text-dim">
                            Arguments <span className="text-faint">(JSON)</span>
                        </label>
                        <textarea
                            id={`${uid}-args`}
                            rows={4}
                            spellCheck="false"
                            value={argsText}
                            onChange={(e) => setArgsText(e.target.value)}
                            onKeyDown={submitOnCmdEnter(() => runSelectedTool())}
                            aria-invalid={!!argsError}
                            aria-describedby={argsError ? `${uid}-args-error` : undefined}
                            className="scroll-thin mt-2 block w-full resize-y border border-line-2 bg-void px-3 py-2.5 font-mono text-[0.8125rem] leading-relaxed text-bright focus:border-signal focus:outline-none"
                        />
                        {argsError && (
                            <p id={`${uid}-args-error`} className="mt-1.5 text-xs text-danger">
                                Fix the JSON: {argsError}
                            </p>
                        )}
                        <RunRow running={running} label="Run tool" hint={selectedTool?.name} onRun={() => runSelectedTool()} />
                    </div>
                )}
            </div>

            {/* --- output --------------------------------------------------------- */}
            <div className="border-t border-line bg-void/50 px-4 py-4" aria-live="polite" aria-busy={running}>
                <Output result={result} running={running} progress={progress} />
            </div>

            <footer className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line px-4 py-3 text-xs text-dim">
                {live ? (
                    <span>
                        Answers come from <code className="break-all font-mono text-bright">{conn.server?.endpoint}</code>
                        {dataStatus && (
                            <span className="text-faint"> · {dataStatus.entryCount.toLocaleString('en-US')} {dataStatus.entryCount === 1 ? 'entry' : 'entries'} indexed</span>
                        )}
                    </span>
                ) : (
                    <span>
                        <span className="text-warn">Simulated</span> answers from a{' '}
                        {SIMULATED_STATUS.sources}-feed demo dataset ({DEMO_VALUES.length} known values). Connect your own
                        server for real verdicts.
                    </span>
                )}
            </footer>
        </section>
    );
};

const RunRow = ({ running, label, hint, onRun }) => (
    <div className="mt-4 flex items-center gap-3">
        <button
            type="button"
            onClick={onRun}
            disabled={running}
            className="flex h-11 items-center gap-2 bg-bright px-5 font-mono text-xs font-medium tracking-[0.14em] uppercase text-void transition-colors hover:bg-dim disabled:cursor-wait disabled:bg-dim"
        >
            {running ? 'Running…' : label}
            {!running && <span aria-hidden="true">&rarr;</span>}
        </button>
        <span className="min-w-0 truncate font-mono text-[0.6875rem] text-faint">
            {hint}
            <span className="hidden sm:inline"> · Ctrl/⌘ + Enter</span>
        </span>
    </div>
);

const Output = ({ result, running, progress }) => {
    if (running) {
        return (
            <p className="font-mono text-xs text-dim">
                <span className="caret text-signal">▍</span> Waiting for the server
                {progress?.message ? ` — ${progress.message}` : progress?.total ? ` — ${progress.progress}/${progress.total}` : '…'}
            </p>
        );
    }
    if (!result) {
        return (
            <p className="text-sm text-faint">
                Results appear here. Try the sample values above, or pick a playbook below.
            </p>
        );
    }
    if (result.inputError) return <p className="text-sm text-warn">{result.inputError}</p>;

    const meta = (
        <p className="mb-3 flex flex-wrap gap-x-3 font-mono text-[0.6875rem] tracking-[0.12em] uppercase text-faint">
            <span className="text-dim">{result.name}</span>
            <span>{result.ms} ms</span>
            <span className={result.live ? 'text-signal' : 'text-warn'}>{result.live ? 'live' : 'simulated'}</span>
        </p>
    );

    if (result.error) {
        return (
            <div role="alert">
                {meta}
                <p className="text-sm text-danger">{result.error.message}</p>
                <p className="mt-1 text-xs text-dim">
                    {result.error.kind === 'protocol'
                        ? 'The server rejected the call — check the arguments against the tool schema.'
                        : 'The connection dropped. The console is back on the demo dataset; reconnect to retry live.'}
                </p>
            </div>
        );
    }

    const isCheck = result.name === 'check_batch' && Array.isArray(result.payload) && !result.isError;
    return (
        <div>
            {meta}
            {result.isError ? (
                <p className="text-sm text-danger">{typeof result.payload === 'string' ? result.payload : JSON.stringify(result.payload)}</p>
            ) : isCheck ? (
                <CheckResults items={result.payload} />
            ) : (
                <JsonView value={result.payload} tone="text-bright" />
            )}
            <details className="group mt-3">
                <summary className="cursor-pointer select-none font-mono text-[0.6875rem] tracking-[0.12em] uppercase text-faint transition-colors hover:text-bright">
                    Raw JSON-RPC
                </summary>
                <div className="mt-2 space-y-2 border-l border-line-2 pl-3">
                    <p className="font-mono text-[0.625rem] tracking-[0.14em] uppercase text-faint">request</p>
                    <JsonView value={result.request} />
                    <p className="font-mono text-[0.625rem] tracking-[0.14em] uppercase text-faint">result</p>
                    <JsonView value={result.raw} />
                </div>
            </details>
        </div>
    );
};

export default Playground;
