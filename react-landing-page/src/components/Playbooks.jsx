import React from 'react';
import SectionHeading from './SectionHeading';
import Reveal from './Reveal';
import { PLAYGROUND_EVENT } from './Playground';

/**
 * Task-shaped entry points into the console. Each card is a real job someone
 * does with sec-mcp, the exact tool call behind it, and the sentence you would
 * say to an assistant that has the MCP server attached.
 *
 * "Run in console" sends the call to the hero's Playground via a window event
 * and scrolls it into view — the console answers live or simulated, whichever
 * it is in. Sample values use reserved names (.example / .test, RFC 5737 IPs).
 */
const PLAYBOOKS = [
    {
        title: 'Triage a phishing email',
        scenario: 'Pull every link out of a suspicious message and check them in one call.',
        prompt: 'Are any of the links in this email on a blacklist?',
        call: { values: ['http://signin-verify.example/account', 'invoice-update.test', 'https://example.com/path'] },
    },
    {
        title: 'Vet outbound connections',
        scenario: 'Screen the destination IPs from a firewall or proxy log before you escalate.',
        prompt: 'Which of these destination IPs are known-bad?',
        call: { values: ['203.0.113.66', '198.51.100.23', '8.8.8.8'] },
    },
    {
        title: 'Guard an agent’s clicks',
        scenario: 'Have an agent verify a URL before it fetches, downloads or recommends it.',
        prompt: 'Before you download that file, check the URL with sec-mcp.',
        call: { values: ['github.com', 'pypi.org', 'http://payload-cdn.test/dropper.bin'] },
    },
    {
        title: 'Check feed freshness',
        scenario: 'Entry counts per source and when the blacklists were last refreshed.',
        prompt: 'How fresh are your blacklists, and how many entries does each feed hold?',
        call: { tool: 'get_status', args: {} },
    },
    {
        title: 'Health-check the server',
        scenario: 'Database reachable, scheduler alive, last update recorded — in one answer.',
        prompt: 'Run a health check on the sec-mcp server.',
        call: { tool: 'get_diagnostics', args: { mode: 'health' } },
    },
    {
        title: 'Sample the blacklist',
        scenario: 'Pull a handful of real entries to see what the feeds actually contain.',
        prompt: 'Show me five random entries from the blacklist.',
        call: { tool: 'get_diagnostics', args: { mode: 'sample', sample_count: 5 } },
    },
];

const callLabel = ({ values, tool, args }) =>
    values
        ? `check_batch(values=[${values.length}])`
        : `${tool}(${Object.entries(args || {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ')})`;

const runInConsole = (call) => {
    window.dispatchEvent(new CustomEvent(PLAYGROUND_EVENT, { detail: call }));
    document.getElementById('playground')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
};

const Playbooks = () => (
    <section id="playbooks" className="field relative py-24 md:py-32">
        <div className="mx-auto max-w-[84rem] px-4 sm:px-6 lg:px-10">
            <SectionHeading
                index="02"
                label="Playbooks"
                meta="one click · live or simulated"
                title="Start from the job, not the API."
                lede="Six things people use sec-mcp for. Run any of them in the console above, or say the prompt to an assistant with the MCP server attached."
            />

            {/* gap-px over the hairline colour draws the grid rules */}
            <ul className="grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
                {PLAYBOOKS.map((p, i) => (
                    <Reveal as="li" key={p.title} delay={(i % 3) * 70} className="flex flex-col bg-void p-6 md:p-7">
                        <p className="font-mono text-xs text-signal">{String(i + 1).padStart(2, '0')}</p>
                        <h3 className="mt-4 font-display text-2xl font-light text-bright">{p.title}</h3>
                        <p className="mt-3 text-sm leading-relaxed text-dim text-pretty">{p.scenario}</p>

                        <blockquote className="mt-5 border-l border-line-signal pl-3 text-sm italic text-bright">
                            &ldquo;{p.prompt}&rdquo;
                        </blockquote>

                        <div className="mt-auto pt-6">
                            <code className="block truncate font-mono text-[0.6875rem] text-faint" title={callLabel(p.call)}>
                                {callLabel(p.call)}
                            </code>
                            <button
                                type="button"
                                onClick={() => runInConsole(p.call)}
                                className="group mt-3 flex h-10 w-full items-center justify-center gap-2 border border-mute font-mono text-xs tracking-[0.14em] uppercase text-bright transition-colors hover:border-signal hover:text-signal"
                            >
                                Run in console
                                <span className="transition-transform group-hover:-translate-y-0.5" aria-hidden="true">
                                    &uarr;
                                </span>
                            </button>
                        </div>
                    </Reveal>
                ))}
            </ul>
        </div>
    </section>
);

export default Playbooks;
