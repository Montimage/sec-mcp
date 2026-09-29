import React from 'react';
import CodeBlock from './CodeBlock';
import SectionHeading from './SectionHeading';
import Reveal from './Reveal';

/* Signatures mirror the public methods on SecMCP in sec_mcp/sec_mcp.py. */
const METHODS = [
    { name: 'check', signature: 'check(value: str) -> CheckResult', description: 'Check a domain, URL or IP. Infers which of the three it is.' },
    { name: 'check_domain', signature: 'check_domain(domain: str) -> CheckResult', description: 'Check a domain and each of its parent domains.' },
    { name: 'check_url', signature: 'check_url(url: str) -> CheckResult', description: 'Check a URL exactly, then fall back to its domain.' },
    { name: 'check_ip', signature: 'check_ip(ip: str) -> CheckResult', description: 'Check an address, including the networks that contain it.' },
    { name: 'check_batch', signature: 'check_batch(values: List[str]) -> List[CheckResult]', description: 'Check many values at once. Results come back in input order.' },
    { name: 'get_status', signature: 'get_status() -> StatusInfo', description: 'Entry count, last update time, active sources and server state.' },
    { name: 'update', signature: 'update() -> dict', description: 'Force a refresh of every feed. Rate limited; returns {"updated": bool}.' },
    { name: 'sample', signature: 'sample(count: int = 10) -> List[str]', description: 'Return a random sample of indexed entries.' },
    { name: 'scheduler_alive', signature: 'scheduler_alive() -> bool', description: 'Report whether the background update thread is still running.' },
];

const TYPES = [
    {
        name: 'CheckResult',
        fields: [
            ['blacklisted', 'bool', 'True when the value matched a feed.'],
            ['explanation', 'str', '"Blacklisted URL by OpenPhish", or "Not blacklisted".'],
        ],
    },
    {
        name: 'StatusInfo',
        fields: [
            ['entry_count', 'int', 'Total indexed entries.'],
            ['last_update', 'datetime', 'When the feeds last refreshed.'],
            ['sources', 'List[str]', 'Active feed names.'],
            ['server_status', 'str', 'Current server state.'],
        ],
    },
];

const APIReference = () => (
    <section id="api" className="field relative py-24 md:py-32">
        <div className="mx-auto max-w-[84rem] px-4 sm:px-6 lg:px-10">
            <SectionHeading
                index="07"
                label="Python API"
                meta="from sec_mcp import SecMCP"
                title="Nine methods and two dataclasses. That is the whole surface."
                lede="Every check returns a CheckResult: a boolean and a sentence explaining it. There is nothing else to learn."
            />

            <div className="grid gap-14 lg:grid-cols-12 lg:gap-16">
                {/* --- methods ------------------------------------------- */}
                <div className="min-w-0 lg:col-span-7">
                    <Reveal>
                        <h3 className="font-mono text-xs tracking-[0.18em] uppercase text-dim">
                            Methods
                            <span className="ml-3 text-faint">({METHODS.length})</span>
                        </h3>
                    </Reveal>

                    {/* A definition list rather than a table: it stacks cleanly on a
                        phone, where a three-column table would need side-scrolling. */}
                    <dl className="mt-6 border-t border-line">
                        {METHODS.map((method, i) => (
                            <Reveal
                                key={method.name}
                                delay={i * 45}
                                className="group border-b border-line py-5 transition-colors hover:bg-raise"
                            >
                                <dt>
                                    <code className="block overflow-x-auto whitespace-pre font-mono text-sm text-bright scroll-thin">
                                        <span className="text-signal">{method.name}</span>
                                        {method.signature.slice(method.name.length)}
                                    </code>
                                </dt>
                                <dd className="mt-2 text-sm leading-relaxed text-dim text-pretty">
                                    {method.description}
                                </dd>
                            </Reveal>
                        ))}
                    </dl>
                </div>

                {/* --- types + example ------------------------------------ */}
                <div className="min-w-0 lg:col-span-5">
                    <Reveal>
                        <h3 className="font-mono text-xs tracking-[0.18em] uppercase text-dim">
                            Return types
                        </h3>
                    </Reveal>

                    <div className="mt-6 space-y-5">
                        {TYPES.map((type, i) => (
                            <Reveal key={type.name} delay={i * 80} className="border border-line bg-raise">
                                <p className="border-b border-line px-5 py-3 font-mono text-sm text-signal">
                                    {type.name}
                                </p>
                                <dl className="divide-y divide-line">
                                    {type.fields.map(([field, type_, note]) => (
                                        <div key={field} className="px-5 py-3">
                                            <dt className="flex flex-wrap items-baseline gap-x-2 font-mono text-xs">
                                                <span className="text-bright">{field}</span>
                                                <span className="text-faint">{type_}</span>
                                            </dt>
                                            <dd className="mt-1 text-sm text-dim">{note}</dd>
                                        </div>
                                    ))}
                                </dl>
                            </Reveal>
                        ))}
                    </div>

                    <Reveal delay={140} className="mt-10">
                        <h3 className="font-mono text-xs tracking-[0.18em] uppercase text-dim">
                            Putting it together
                        </h3>
                        <div className="mt-4">
                            <CodeBlock language="python" label="python">
{`from sec_mcp import SecMCP

client = SecMCP()

status = client.get_status()
print(f"{status.entry_count} entries "
      f"from {len(status.sources)} sources")
print(f"last update: {status.last_update}")

result = client.check_ip("185.0.0.1")
print(result.blacklisted, result.explanation)

# Force a refresh (rate limited)
print(client.update())   # {'updated': True}`}
                            </CodeBlock>
                        </div>
                    </Reveal>
                </div>
            </div>
        </div>
    </section>
);

export default APIReference;
