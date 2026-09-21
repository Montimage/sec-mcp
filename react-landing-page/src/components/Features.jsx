import React from 'react';
import SectionHeading from './SectionHeading';
import Reveal from './Reveal';

/* Thin line-art icons, stroke 1.25 — drawn to sit at the same optical weight
   as the hairline rules so nothing in the grid shouts. */
const icon = 'h-6 w-6';
const stroke = {
    className: icon,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.25,
    'aria-hidden': true,
};

const FEATURES = [
    {
        title: 'Ten feeds, one index',
        body: 'OpenPhish, PhishTank, PhishStats, URLhaus, Spamhaus DROP, DShield, CINS, Emerging Threats, Feodo Tracker and Blocklist.de — merged into a single lookup.',
        icon: (
            <svg {...stroke}>
                <path d="M3 7h18M3 12h18M3 17h18" strokeLinecap="round" />
                <circle cx="8" cy="7" r="1.6" />
                <circle cx="15" cy="12" r="1.6" />
                <circle cx="6" cy="17" r="1.6" />
            </svg>
        ),
    },
    {
        title: 'Microsecond lookups',
        body: 'One O(1) in-memory index per entry type. A domain resolves in 0.006 ms and a URL in 0.0007 ms once in-memory storage is enabled.',
        icon: (
            <svg {...stroke}>
                <path d="M13 3 4.5 13.5H11L10 21l8.5-10.5H12L13 3Z" strokeLinejoin="round" />
            </svg>
        ),
    },
    {
        title: 'Three ways in',
        body: 'Import it as a Python library, drive it from the terminal, or run it as an MCP server so an assistant can check a link before it recommends one.',
        icon: (
            <svg {...stroke}>
                <path d="M4 5h16v14H4z" />
                <path d="M7.5 9.5 10 12l-2.5 2.5M12.5 14.5H17" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
        ),
    },
    {
        title: 'CIDR-aware IP matching',
        body: 'IPv4 addresses are stored as integers and matched against whole networks, not just literal addresses — so a single range covers what it should.',
        icon: (
            <svg {...stroke}>
                <circle cx="12" cy="12" r="8.5" />
                <path d="M3.5 12h17M12 3.5c4 4.5 4 12.5 0 17M12 3.5c-4 4.5-4 12.5 0 17" />
            </svg>
        ),
    },
    {
        title: 'Refreshed on a schedule',
        body: 'Feeds update daily at 00:00 from a background scheduler, and sec-mcp update forces a refresh whenever you need one.',
        icon: (
            <svg {...stroke}>
                <path d="M20.5 12a8.5 8.5 0 1 1-2.5-6" strokeLinecap="round" />
                <path d="M20.5 3.5V6H18" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
        ),
    },
    {
        title: 'Safe under concurrency',
        body: 'SQLite in WAL mode behind an in-memory cache, so parallel checks from threads or a busy MCP client stay consistent.',
        icon: (
            <svg {...stroke}>
                <rect x="4.5" y="10.5" width="15" height="9.5" rx="1" />
                <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" strokeLinecap="round" />
            </svg>
        ),
    },
];

const Features = () => (
    <section id="features" className="field relative py-24 md:py-32">
        <div className="mx-auto max-w-[84rem] px-4 sm:px-6 lg:px-10">
            <SectionHeading
                index="03"
                label="Capabilities"
                meta="Six things it does well"
                title="A blacklist engine that behaves like a local function call."
                lede="No hosted service sits between you and an answer. The feeds are downloaded, normalised and indexed on your machine, and every check after that is a memory read."
            />

            {/* Exactly six cells: 3 × 2 on desktop, 2 × 3 on tablet, 1 column on
                phones — never ragged, so the shared hairlines always close. */}
            <div className="grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
                {FEATURES.map((feature, i) => (
                    <Reveal
                        key={feature.title}
                        delay={i * 70}
                        className="group relative bg-void p-8 transition-colors duration-300 hover:bg-raise md:p-10"
                    >
                        {/* green rule that draws in on hover — accent as a line, never a fill */}
                        <span className="absolute inset-x-0 top-0 h-px origin-left scale-x-0 bg-signal transition-transform duration-500 group-hover:scale-x-100" aria-hidden="true" />

                        <div className="flex items-start justify-between">
                            <span className="text-faint transition-colors duration-300 group-hover:text-signal">
                                {feature.icon}
                            </span>
                            <span className="font-mono text-[0.6875rem] tracking-[0.16em] text-faint">
                                {String(i + 1).padStart(2, '0')}
                            </span>
                        </div>

                        <h3 className="mt-8 font-display text-2xl font-light">{feature.title}</h3>
                        <p className="mt-3 text-[0.9375rem] leading-relaxed text-dim text-pretty">
                            {feature.body}
                        </p>
                    </Reveal>
                ))}
            </div>
        </div>
    </section>
);

export default Features;
