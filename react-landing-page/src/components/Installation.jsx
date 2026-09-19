import React from 'react';
import CodeBlock from './CodeBlock';
import SectionHeading from './SectionHeading';
import Reveal from './Reveal';

const STEPS = [
    {
        title: 'Create a virtual environment',
        note: 'Python 3.11 or newer. The MCP config later needs this path, so keep it somewhere stable.',
        language: 'bash',
        code: `python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate`,
    },
    {
        title: 'Install the package',
        note: null,
        language: 'bash',
        code: `pip install sec-mcp

# Verify installation
sec-mcp --version`,
    },
    {
        title: 'Populate the database',
        note: 'The first download pulls all ten feeds and takes a few minutes. After that a scheduler refreshes them daily at 00:00.',
        language: 'bash',
        code: `# Download and index every configured feed
sec-mcp update

# Entry counts, last update, per-source breakdown
sec-mcp status`,
    },
    {
        title: 'Run a check',
        note: 'Prints "Status: Safe" or "Status: Blacklisted" with an explanation. Add --json for machine-readable output.',
        language: 'bash',
        code: `sec-mcp check example.com
sec-mcp check 8.8.8.8
sec-mcp check https://example.com/path --json`,
    },
];

const Installation = () => (
    <section id="install" className="field relative py-24 md:py-32">
        <div className="mx-auto max-w-[84rem] px-4 sm:px-6 lg:px-10">
            <SectionHeading
                index="05"
                label="Install"
                meta="~5 minutes"
                title="From pip install to a first verdict."
                lede="Four commands to a working install. The only part people trip on is step three — the database is empty until you populate it."
            />

            <div className="grid gap-14 lg:grid-cols-12 lg:gap-16">
                {/* --- CLI timeline ---------------------------------------- */}
                <div className="min-w-0 lg:col-span-7">
                    <ol>
                        {STEPS.map((step, i) => (
                            <Reveal
                                as="li"
                                key={step.title}
                                delay={i * 60}
                                className="relative pb-10 pl-12 last:pb-0 sm:pl-16"
                            >
                                {/* connector: a hairline running through the numbers */}
                                {i < STEPS.length - 1 && (
                                    <span
                                        className="absolute left-[15px] top-9 bottom-0 w-px bg-line sm:left-[19px]"
                                        aria-hidden="true"
                                    />
                                )}
                                <span
                                    className="absolute left-0 top-0 flex h-8 w-8 items-center justify-center border border-line-2 bg-void font-mono text-xs text-signal sm:h-10 sm:w-10 sm:text-sm"
                                    aria-hidden="true"
                                >
                                    {i + 1}
                                </span>

                                <h3 className="font-display text-2xl font-light leading-tight">
                                    {step.title}
                                </h3>
                                {step.note && (
                                    <p className="mt-2 text-sm leading-relaxed text-dim text-pretty">
                                        {step.note}
                                    </p>
                                )}
                                <div className="mt-4">
                                    <CodeBlock language={step.language} label={`step ${i + 1}`}>
                                        {step.code}
                                    </CodeBlock>
                                </div>
                            </Reveal>
                        ))}
                    </ol>
                </div>

                {/* --- Python quickstart ----------------------------------- */}
                <div className="min-w-0 lg:col-span-5">
                    <div className="lg:sticky lg:top-28">
                        <Reveal>
                            <h3 className="font-mono text-xs tracking-[0.18em] uppercase text-dim">
                                Or import it
                            </h3>
                            <p className="mt-4 text-[0.9375rem] leading-relaxed text-dim text-pretty">
                                Constructing{' '}
                                <code className="font-mono text-bright">SecMCP()</code> is what
                                creates the database and starts the scheduler &mdash; importing the
                                package on its own does nothing.
                            </p>
                        </Reveal>

                        <Reveal delay={80} className="mt-6">
                            <CodeBlock language="python" label="python">
{`from sec_mcp import SecMCP

# Default database location
client = SecMCP()

# Or point it at your own file
client = SecMCP(db_path="/srv/sec-mcp/blacklist.db")

result = client.check("https://example.com/login")

if result.blacklisted:
    # e.g. "Blacklisted URL by OpenPhish"
    print(f"Blocked: {result.explanation}")
else:
    print("Clean")`}
                            </CodeBlock>
                        </Reveal>

                        <Reveal delay={130} className="mt-6">
                            <CodeBlock language="python" label="batch">
{`values = [
    "example.com",
    "192.168.1.1",
    "https://example.org/login",
]

# Results come back in input order; CheckResult carries
# the verdict, so zip it against the values you sent.
for value, result in zip(values, client.check_batch(values)):
    verdict = "BLACKLISTED" if result.blacklisted else "clean"
    print(f"{value:<28} {verdict:<12} {result.explanation}")`}
                            </CodeBlock>
                        </Reveal>

                        <Reveal delay={170}>
                            <p className="mt-6 text-sm text-dim">
                                Every method is listed in the{' '}
                                <a
                                    href="#api"
                                    className="text-signal underline decoration-line-signal underline-offset-4 transition-colors hover:decoration-signal"
                                >
                                    API reference
                                </a>
                                .
                            </p>
                        </Reveal>
                    </div>
                </div>
            </div>
        </div>
    </section>
);

export default Installation;
