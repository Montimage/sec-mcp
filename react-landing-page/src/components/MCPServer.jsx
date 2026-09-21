import React from 'react';
import CodeBlock from './CodeBlock';
import SectionHeading from './SectionHeading';
import Reveal from './Reveal';

const MCPServer = () => {
    // Keep in sync with the tools registered in sec_mcp/mcp_server.py (tools/list).
    const mcpTools = [
        { name: 'check_batch', signature: 'check_batch(values: List[str])', description: 'Check multiple domains/URLs/IPs in one call. Returns list of {value, is_safe, verdict, explanation}.' },
        { name: 'get_status', signature: 'get_status()', description: 'Get blacklist status including entry counts and sources. Returns {entry_count, last_update, sources, server_status, source_counts}.' },
        { name: 'update_blacklists', signature: 'update_blacklists()', description: 'Force immediate update of all blacklists. Returns {updated: bool}.' },
        { name: 'get_diagnostics', signature: 'get_diagnostics(mode: str = "summary", sample_count: int = 10)', description: "Get diagnostic information. Mode options: 'summary' (default), 'full', 'health', 'performance', 'sample'." },
        { name: 'add_entry', signature: 'add_entry(url, ip, date, score, source)', description: 'Add a manual blacklist entry.' },
        { name: 'remove_entry', signature: 'remove_entry(value: str)', description: 'Remove a blacklist entry by URL or IP.' }
    ];

    return (
        <section id="mcp" className="field relative py-24 md:py-32">
            <div className="mx-auto max-w-[84rem] px-4 sm:px-6 lg:px-10">
                <SectionHeading
                    index="05"
                    label="Model Context Protocol"
                    meta="stdio · streamable HTTP"
                    title="Give your assistant a way to check before it recommends."
                    lede="Run sec-mcp as an MCP server and six tools appear in your client. The model can verify a link mid-conversation instead of guessing at it."
                />

                <div className="grid gap-12 lg:grid-cols-12 lg:gap-14">
                    {/* --- configure --------------------------------------- */}
                    <div className="min-w-0 lg:col-span-5">
                        <Reveal>
                            <h3 className="font-mono text-xs tracking-[0.18em] uppercase text-dim">
                                Client configuration
                            </h3>
                            <p className="mt-4 text-[0.9375rem] leading-relaxed text-dim text-pretty">
                                Point your MCP client at the interpreter inside the virtual
                                environment where sec-mcp is installed.
                            </p>
                        </Reveal>

                        <Reveal delay={90} className="mt-6">
                            <CodeBlock language="json" label="mcp config">
{`{
  "mcpServers": {
    "sec-mcp": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["-m", "sec_mcp.start_server"]
    }
  }
}`}
                            </CodeBlock>
                        </Reveal>

                        <Reveal delay={110} className="mt-6">
                            <p className="text-[0.9375rem] leading-relaxed text-dim text-pretty">
                                Or serve it over streamable HTTP for remote clients and the{' '}
                                <a
                                    href="#playground"
                                    className="text-signal underline decoration-line-signal underline-offset-4 transition-colors hover:decoration-signal"
                                >
                                    playground
                                </a>{' '}
                                above. It binds to 127.0.0.1 unless you pass <code className="font-mono text-bright">--host</code>.
                            </p>
                            <div className="mt-4">
                                <CodeBlock language="bash" label="http transport">
{`sec-mcp-server --http --port 8000
# → http://127.0.0.1:8000/mcp

# optional: allow another web origin, require a token
export SEC_MCP_CORS_ORIGINS=https://your.site
export SEC_MCP_HTTP_AUTH_TOKEN=change-me`}
                                </CodeBlock>
                            </div>
                        </Reveal>

                        {/* The one thing people get wrong — called out, not buried. */}
                        <Reveal delay={140} className="mt-6 border-l border-signal bg-raise p-5">
                            <p className="font-mono text-xs tracking-[0.16em] uppercase text-signal">
                                Before you start
                            </p>
                            <ul className="mt-3 space-y-2 text-sm leading-relaxed text-dim">
                                <li>
                                    Use the <strong className="font-medium text-bright">absolute path</strong>{' '}
                                    to the venv&rsquo;s Python. A bare{' '}
                                    <code className="font-mono text-bright">python</code> will start
                                    the wrong interpreter.
                                </li>
                                <li>
                                    Run <code className="font-mono text-bright">sec-mcp update</code>{' '}
                                    once first, then{' '}
                                    <code className="font-mono text-bright">sec-mcp status</code> to
                                    confirm the database is populated.
                                </li>
                                <li>Over stdio the server starts and stops with your MCP client; over HTTP it runs until you stop it.</li>
                            </ul>
                            <p className="mt-4 text-sm text-dim">
                                Full steps in the{' '}
                                <a
                                    href="#install"
                                    className="text-signal underline decoration-line-signal underline-offset-4 transition-colors hover:decoration-signal"
                                >
                                    install guide
                                </a>
                                .
                            </p>
                        </Reveal>
                    </div>

                    {/* --- tools ------------------------------------------- */}
                    <div className="min-w-0 lg:col-span-7">
                        <Reveal>
                            <h3 className="font-mono text-xs tracking-[0.18em] uppercase text-dim">
                                Exposed tools
                                <span className="ml-3 text-faint">({mcpTools.length})</span>
                            </h3>
                        </Reveal>

                        <dl className="mt-6 border-t border-line">
                            {mcpTools.map((tool, i) => (
                                <Reveal
                                    key={tool.name}
                                    delay={i * 55}
                                    className="group border-b border-line py-5 transition-colors hover:bg-raise"
                                >
                                    <dt className="flex flex-wrap items-baseline gap-x-3">
                                        <code className="font-mono text-[0.9375rem] text-signal">
                                            {tool.name}
                                        </code>
                                        <code className="min-w-0 break-all font-mono text-xs text-faint">
                                            {tool.signature}
                                        </code>
                                    </dt>
                                    <dd className="mt-2 text-sm leading-relaxed text-dim text-pretty">
                                        {tool.description}
                                    </dd>
                                </Reveal>
                            ))}
                        </dl>

                        <Reveal delay={120} className="mt-10">
                            <h3 className="font-mono text-xs tracking-[0.18em] uppercase text-dim">
                                In conversation
                            </h3>
                            <div className="mt-4">
                                <CodeBlock language="markdown" label="transcript">
{`User: "Is example.com safe to visit?"

AI: Let me check that URL for you.
[Uses sec-mcp check_batch tool]

I've checked example.com against our security database.
The domain is not found in any blacklists and
appears to be safe to visit.`}
                                </CodeBlock>
                            </div>
                        </Reveal>
                    </div>
                </div>
            </div>
        </section>
    );
};

export default MCPServer;
