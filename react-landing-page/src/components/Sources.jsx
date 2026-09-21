import React from 'react';
import SectionHeading from './SectionHeading';
import Reveal from './Reveal';

/**
 * The ten feeds in sec_mcp/config.json, in file order. Kinds follow the
 * registered parsers in sec_mcp/feed_parsers.py: PhishStats and PhishTank are
 * URL CSVs, SpamhausDROP is a network list, and Dshield, CINSSCORE,
 * EmergingThreats, FeodoTracker and BlocklistDE are address lists.
 * Keep in sync with sec_mcp/config.json.
 */
const FEEDS = [
    { name: 'OpenPhish', subject: 'Live phishing URLs', kind: 'URL' },
    { name: 'PhishStats', subject: 'Scored phishing URLs', kind: 'URL' },
    { name: 'URLhaus', subject: 'Malware distribution URLs', kind: 'URL' },
    { name: 'PhishTank', subject: 'Community-verified phishing', kind: 'URL' },
    { name: 'Spamhaus DROP', subject: 'Hijacked and rogue netblocks', kind: 'CIDR' },
    { name: 'DShield', subject: 'Most-attacking networks', kind: 'CIDR' },
    { name: 'CINS Score', subject: 'Poorly-reputed addresses', kind: 'IP' },
    { name: 'Emerging Threats', subject: 'Compromised hosts', kind: 'IP' },
    { name: 'Feodo Tracker', subject: 'Botnet command & control', kind: 'IP' },
    { name: 'Blocklist.de', subject: 'Reported attacking hosts', kind: 'IP' },
];

const kindTone = {
    URL: 'text-signal border-line-signal',
    CIDR: 'text-dim border-line-2',
    IP: 'text-dim border-line-2',
};

const Sources = () => (
    <section id="sources" className="field relative py-24 md:py-32">
        <div className="mx-auto max-w-[84rem] px-4 sm:px-6 lg:px-10">
            <SectionHeading
                index="04"
                label="Sources"
                meta="Refreshed daily at 00:00"
                title="Ten public feeds, normalised into one register."
                lede="Each feed has its own format and its own idea of what an entry looks like. sec-mcp parses them per source, normalises URLs, stores IPv4 as integers, and hands you one answer."
            />

            {/* asymmetric: a sticky mono aside against a dense register */}
            <div className="grid gap-12 lg:grid-cols-12 lg:gap-16">
                <aside className="min-w-0 lg:col-span-4">
                    <div className="lg:sticky lg:top-28">
                        <Reveal>
                            <p className="font-display text-7xl font-light leading-none md:text-8xl">
                                10
                            </p>
                            <p className="mt-3 font-mono text-xs tracking-[0.18em] uppercase text-dim">
                                Active feeds
                            </p>
                        </Reveal>

                        <Reveal delay={90} className="mt-10 border-t border-line pt-6">
                            <p className="text-[0.9375rem] leading-relaxed text-dim text-pretty">
                                Feeds arrive on a background scheduler. Nothing is fetched at check
                                time, so a lookup never waits on the network &mdash; and never tells
                                a third party what you looked up.
                            </p>
                            <p className="mt-6 font-mono text-xs leading-relaxed text-faint">
                                <span className="text-signal">$</span>{' '}
                                <span className="text-dim">sec-mcp status</span>
                                <br />
                                <span className="text-faint">
                                    &rarr; per-source counts, split by domains, URLs and IPs
                                </span>
                            </p>
                        </Reveal>
                    </div>
                </aside>

                <div className="min-w-0 lg:col-span-8">
                    <ol className="border-t border-line">
                        {FEEDS.map((feed, i) => (
                            <Reveal
                                as="li"
                                key={feed.name}
                                delay={i * 45}
                                className="group flex items-baseline gap-4 border-b border-line py-5 transition-colors hover:bg-raise sm:gap-6"
                            >
                                <span className="w-6 shrink-0 font-mono text-xs text-faint transition-colors group-hover:text-signal">
                                    {String(i + 1).padStart(2, '0')}
                                </span>

                                <span className="min-w-0 flex-1">
                                    <span className="block font-mono text-[0.9375rem] text-bright">
                                        {feed.name}
                                    </span>
                                    <span className="mt-0.5 block text-sm text-dim">
                                        {feed.subject}
                                    </span>
                                </span>

                                <span
                                    className={`shrink-0 border px-2.5 py-1 font-mono text-[0.625rem] tracking-[0.16em] uppercase ${kindTone[feed.kind]}`}
                                >
                                    {feed.kind}
                                </span>
                            </Reveal>
                        ))}
                    </ol>

                    <Reveal delay={120}>
                        <p className="mt-6 text-sm text-dim">
                            Need a source of your own? Add entries directly with{' '}
                            <code className="font-mono text-signal">add_entry</code> or point the
                            config at another feed.
                        </p>
                    </Reveal>
                </div>
            </div>
        </div>
    </section>
);

export default Sources;
