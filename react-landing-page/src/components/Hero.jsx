import React from 'react';
import Terminal from './Terminal';

/** Load-in cascade: each element rises 90ms after the one above it. */
const step = (i) => ({ animationDelay: `${120 + i * 90}ms` });

const STATS = [
    { value: '10', unit: 'feeds', note: 'Threat sources' },
    { value: '0.006', unit: 'ms', note: 'Domain lookup' },
    { value: '~45', unit: 'MB', note: '450K entries in memory' },
    { value: 'MIT', unit: '', note: 'Open source' },
];

const Hero = () => (
    <section id="top" className="field relative overflow-hidden pt-32 pb-20 md:pt-44 md:pb-28">
        {/* the signature: one green hairline sweeps the hero, once, on load */}
        <span className="scanline" style={{ '--scan-distance': '100vh' }} aria-hidden="true" />

        <div className="mx-auto max-w-[84rem] px-4 sm:px-6 lg:px-10">
            <div className="grid items-start gap-14 lg:grid-cols-12 lg:gap-12">
                {/* --- copy ---------------------------------------------- */}
                <div className="min-w-0 lg:col-span-6">
                    <p
                        className="enter font-mono text-xs tracking-[0.22em] uppercase text-dim"
                        style={step(0)}
                    >
                        <span className="text-signal">01</span>
                        <span className="mx-2.5 text-faint" aria-hidden="true">/</span>
                        Threat intelligence for Python
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
                        feeds &mdash; in process, in microseconds, with no API key and no request
                        leaving your machine.
                    </p>

                    {/* primary CTA is a solid white slab: unmistakably clickable on black.
                        Green stays an accent and is never used as a fill. */}
                    <div className="enter mt-10 flex flex-wrap items-center gap-3" style={step(4)}>
                        <a
                            href="#install"
                            className="flex h-12 w-full items-center justify-center bg-bright px-7 font-mono sm:w-auto sm:justify-start text-xs font-medium tracking-[0.16em] uppercase text-void transition-colors hover:bg-dim"
                        >
                            Get started
                        </a>
                        <a
                            href="#api"
                            className="group flex h-12 w-full items-center justify-center gap-2 border border-line-2 px-7 font-mono sm:w-auto sm:justify-start text-xs tracking-[0.16em] uppercase text-bright transition-colors hover:border-signal hover:text-signal"
                        >
                            Read the API
                            <span className="transition-transform group-hover:translate-x-1" aria-hidden="true">
                                &rarr;
                            </span>
                        </a>
                    </div>

                    <p className="enter mt-8 font-mono text-xs text-faint" style={step(5)}>
                        <span className="text-dim">Python 3.11+</span>
                        <span className="mx-2" aria-hidden="true">&middot;</span>
                        <span className="text-dim">Library, CLI and MCP server</span>
                    </p>
                </div>

                {/* --- terminal ------------------------------------------ */}
                <div className="enter min-w-0 lg:col-span-6" style={step(3)}>
                    <Terminal />
                </div>
            </div>

            {/* --- stat strip -------------------------------------------- */}
            {/* gap-px over a hairline-coloured backdrop draws the dividers for
                us — correct at 2 columns and at 4, with no per-cell edge cases. */}
            <dl
                className="enter mt-20 grid grid-cols-2 gap-px border-y border-line bg-line md:mt-28 md:grid-cols-4"
                style={step(6)}
            >
                {STATS.map((stat) => (
                    <div key={stat.note} className="bg-void px-5 py-7 md:px-7 md:py-8">
                        <dd className="font-display text-4xl font-light md:text-5xl">
                            {stat.value}
                            {stat.unit && (
                                <span className="ml-1.5 font-mono text-sm font-normal text-faint">
                                    {stat.unit}
                                </span>
                            )}
                        </dd>
                        <dt className="mt-2 font-mono text-[0.6875rem] tracking-[0.16em] uppercase text-dim">
                            {stat.note}
                        </dt>
                    </div>
                ))}
            </dl>
        </div>
    </section>
);

export default Hero;
