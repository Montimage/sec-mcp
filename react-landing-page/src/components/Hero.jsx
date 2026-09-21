import React, { useCallback, useState } from 'react';
import Playground from './Playground';

/** Load-in cascade: each element rises 90ms after the one above it. */
const step = (i) => ({ animationDelay: `${120 + i * 90}ms` });

const STATS = [
    { value: '10', unit: 'feeds', note: 'Threat sources' },
    { value: '0.006', unit: 'ms', note: 'Domain lookup' },
    { value: '~45', unit: 'MB', note: '450K entries in memory' },
    { value: 'Apache-2.0', unit: '', note: 'Open source' },
];

const SETUP = [
    { label: 'Install and index the feeds', code: 'pip install sec-mcp && sec-mcp update' },
    { label: 'Serve MCP over HTTP', code: 'sec-mcp-server --http' },
];

// Checklist rows are hollow rings, like the console's status marker: green
// border when proven, red when disproven, gray while unknown.
const ringClass = (state) =>
    state === 'ok' ? 'border-signal' : state === 'fail' ? 'border-danger' : state === 'checking' ? 'border-dim animate-pulse' : 'border-mute';

const stateText = (state, ok, fail, idle) =>
    state === 'ok' ? ok : state === 'fail' ? fail : state === 'checking' ? 'checking…' : idle;

const Hero = () => {
    const [status, setStatus] = useState({ server: 'idle', data: 'idle', entryCount: null });
    // Stable identity: Playground reports from an effect keyed on this callback.
    const onStatusChange = useCallback((next) => setStatus(next), []);

    return (
        <section id="top" className="field relative overflow-hidden pt-28 pb-20 md:pt-36 md:pb-28">
            {/* the signature: one green hairline sweeps the hero, once, on load */}
            <span className="scanline" style={{ '--scan-distance': '100vh' }} aria-hidden="true" />

            <div className="mx-auto max-w-[84rem] px-4 sm:px-6 lg:px-10">
                {/* Three grid children in DOM order intro → console → setup, so on
                    phones the console comes straight after the pitch. On lg the
                    intro and setup stack in column 1 while the console spans both
                    rows of column 2. */}
                <div className="grid items-start gap-12 lg:grid-cols-12 lg:gap-x-12 lg:gap-y-10">
                    {/* --- copy ---------------------------------------------- */}
                    <div className="min-w-0 lg:col-span-6 lg:col-start-1 lg:row-start-1">
                        <p
                            className="enter font-mono text-xs tracking-[0.22em] uppercase text-dim"
                            style={step(0)}
                        >
                            <span className="text-signal">01</span>
                            <span className="mx-2.5 text-faint" aria-hidden="true">/</span>
                            Threat intelligence for Python &amp; MCP
                        </p>

                        <h1
                            className="enter font-display text-display mt-8 font-light text-balance"
                            style={step(1)}
                        >
                            Know what you&rsquo;re{' '}
                            <em className="font-normal italic text-signal">talking to.</em>
                        </h1>

                        <div className="enter rule-signal mt-9 max-w-md" style={step(2)} />

                        <p
                            className="enter mt-8 max-w-xl text-lg leading-relaxed text-dim text-pretty"
                            style={step(3)}
                        >
                            sec-mcp checks domains, URLs and IP addresses against ten live blacklist
                            feeds &mdash; in process, in microseconds, with no API key.{' '}
                            <span className="text-bright">Try the MCP server right here</span>: the
                            console answers from a demo dataset until you connect your own.
                        </p>

                        <div className="enter mt-10 flex flex-wrap items-center gap-3" style={step(4)}>
                            <a
                                href="#playground"
                                className="flex h-12 w-full items-center justify-center bg-bright px-7 font-mono text-xs font-medium tracking-[0.16em] uppercase text-void transition-colors hover:bg-dim sm:w-auto"
                            >
                                Try it live
                            </a>
                            <a
                                href="#install"
                                className="group flex h-12 w-full items-center justify-center gap-2 border border-mute px-7 font-mono text-xs tracking-[0.16em] uppercase text-bright transition-colors hover:border-signal hover:text-signal sm:w-auto"
                            >
                                Install guide
                                <span className="transition-transform group-hover:translate-x-1" aria-hidden="true">
                                    &rarr;
                                </span>
                            </a>
                        </div>

                        <p className="enter mt-8 font-mono text-xs text-faint" style={step(5)}>
                            <span className="text-dim">Python 3.11+</span>
                            <span className="mx-2" aria-hidden="true">&middot;</span>
                            <span className="text-dim">Library, CLI and MCP server</span>
                            <span className="mx-2" aria-hidden="true">&middot;</span>
                            <span className="text-dim">stdio + streamable HTTP</span>
                        </p>
                    </div>

                    {/* --- live console ---------------------------------------- */}
                    {/* Not sticky: with results showing, the console can outgrow
                        the viewport. scroll-mt keeps the #playground anchor
                        clear of the 64px fixed header. */}
                    <div
                        id="playground"
                        className="enter min-w-0 scroll-mt-24 lg:col-span-6 lg:col-start-7 lg:row-span-2 lg:row-start-1"
                        style={step(3)}
                    >
                        <Playground onStatusChange={onStatusChange} />
                    </div>

                    {/* --- connect your own server ----------------------------- */}
                    <div
                        className="enter min-w-0 border border-line bg-raise p-6 sm:p-7 lg:col-span-6 lg:col-start-1 lg:row-start-2"
                        style={step(6)}
                    >
                        <h2 className="font-mono text-xs tracking-[0.18em] uppercase text-dim">
                            Test your own server
                        </h2>
                        <ol className="mt-5 space-y-4">
                            {SETUP.map((s, i) => (
                                <li key={s.code} className="grid grid-cols-[1.5rem_minmax(0,1fr)] gap-x-2">
                                    <span className="font-mono text-xs text-signal">{String(i + 1).padStart(2, '0')}</span>
                                    <div className="min-w-0">
                                        <p className="text-sm text-bright">{s.label}</p>
                                        <code className="scroll-thin mt-1.5 block overflow-x-auto whitespace-nowrap border border-line bg-void px-3 py-2 font-mono text-xs text-dim">
                                            <span className="mr-2 select-none text-signal">$</span>
                                            {s.code}
                                        </code>
                                    </div>
                                </li>
                            ))}
                            <li className="grid grid-cols-[1.5rem_minmax(0,1fr)] gap-x-2">
                                <span className="font-mono text-xs text-signal">03</span>
                                <p className="text-sm text-bright">
                                    Press <span className="font-mono text-xs tracking-[0.12em] uppercase">Connect</span> in
                                    the console.{' '}
                                    <span className="text-dim">
                                        It uses <code className="font-mono text-xs">http://127.0.0.1:8000/mcp</code> by default.
                                    </span>
                                </p>
                            </li>
                        </ol>

                        {/* First-run checklist — mirrors what the console proved. */}
                        <div className="mt-6 border-t border-line pt-5">
                            <h3 className="font-mono text-[0.6875rem] tracking-[0.16em] uppercase text-faint">
                                First-run checklist
                            </h3>
                            <ul className="mt-3 space-y-2 text-sm">
                                <li className="flex items-center gap-2.5" data-status={status.server}>
                                    <span aria-hidden="true" className={`h-2 w-2 shrink-0 rounded-full border-2 ${ringClass(status.server)}`} />
                                    <span className="text-dim">
                                        MCP server reachable{' '}
                                        <span className="text-faint">
                                            — {stateText(status.server, 'connected', 'not reachable', 'not connected yet')}
                                        </span>
                                    </span>
                                </li>
                                <li className="flex items-center gap-2.5" data-status={status.data}>
                                    <span aria-hidden="true" className={`h-2 w-2 shrink-0 rounded-full border-2 ${ringClass(status.data)}`} />
                                    <span className="text-dim">
                                        Blacklists indexed{' '}
                                        <span className="text-faint">
                                            —{' '}
                                            {stateText(
                                                status.data,
                                                `${(status.entryCount ?? 0).toLocaleString('en-US')} ${status.entryCount === 1 ? 'entry' : 'entries'}`,
                                                'empty: run sec-mcp update',
                                                'unknown until connected',
                                            )}
                                        </span>
                                    </span>
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>

                {/* --- stat strip -------------------------------------------- */}
                {/* gap-px over a hairline-coloured backdrop draws the dividers for
                    us — correct at 2 columns and at 4, with no per-cell edge cases. */}
                <dl
                    className="enter mt-20 grid grid-cols-2 gap-px border-y border-line bg-line md:mt-28 md:grid-cols-4"
                    style={step(7)}
                >
                    {STATS.map((stat) => (
                        <div
                            key={stat.note}
                            className="flex flex-col bg-void px-5 py-7 md:px-7 md:py-8"
                        >
                            <dt className="order-2 mt-2 font-mono text-[0.6875rem] tracking-[0.16em] uppercase text-dim">
                                {stat.note}
                            </dt>
                            <dd className="order-1 font-display text-4xl font-light md:text-5xl">
                                {stat.value}
                                {stat.unit && (
                                    <span className="ml-1.5 font-mono text-sm font-normal text-faint">
                                        {stat.unit}
                                    </span>
                                )}
                            </dd>
                        </div>
                    ))}
                </dl>
            </div>
        </section>
    );
};

export default Hero;
