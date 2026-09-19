import React, { useEffect, useRef, useState } from 'react';

/**
 * The hero's signature element: a replayed CLI session that types itself once
 * when scrolled into view.
 *
 * Every string below is the real output of `sec_mcp/cli.py` — "Status: Safe",
 * "Explanation: Not blacklisted", "Blacklist update triggered." — so the demo
 * is a recording, not a mock-up. Nothing here performs a live check, and the
 * caption says so.
 */
const SCRIPT = [
    { kind: 'cmd', text: 'pip install sec-mcp' },
    { kind: 'cmd', text: 'sec-mcp update' },
    { kind: 'out', text: 'Blacklist update triggered.', tone: 'dim' },
    { kind: 'cmd', text: 'sec-mcp check example.com' },
    { kind: 'out', text: 'Status: Safe', tone: 'safe' },
    { kind: 'out', text: 'Explanation: Not blacklisted', tone: 'dim' },
    { kind: 'cmd', text: 'sec-mcp check http://signin-verify.example/account' },
    { kind: 'out', text: 'Status: Blacklisted', tone: 'bad' },
    { kind: 'out', text: 'Explanation: Blacklisted URL by OpenPhish', tone: 'dim' },
];

const TYPE_MS = 26;      // per character of a typed command
const OUTPUT_MS = 240;   // pause before a result line appears
const PROMPT_MS = 420;   // pause before the next command starts

const toneClass = {
    safe: 'text-signal',
    bad: 'text-danger',
    dim: 'text-dim',
};

const Terminal = () => {
    // How many script lines are done, and how far into the current one we are.
    const [line, setLine] = useState(0);
    const [chars, setChars] = useState(0);
    const [done, setDone] = useState(false);
    const [started, setStarted] = useState(false);
    const hostRef = useRef(null);

    // Start only once the terminal is actually on screen; skip the whole
    // performance for reduced-motion visitors and render the finished session.
    useEffect(() => {
        const node = hostRef.current;
        const reduced =
            typeof window !== 'undefined' &&
            window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        if (!node || reduced || typeof IntersectionObserver === 'undefined') {
            setLine(SCRIPT.length);
            setDone(true);
            return;
        }

        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting) {
                    setStarted(true);
                    observer.unobserve(entry.target);
                }
            },
            { threshold: 0.25 }
        );
        observer.observe(node);
        return () => observer.disconnect();
    }, []);

    useEffect(() => {
        if (!started || done) return;

        if (line >= SCRIPT.length) {
            setDone(true);
            return;
        }

        const step = SCRIPT[line];
        let timer;

        if (step.kind === 'out') {
            timer = setTimeout(() => {
                setLine((n) => n + 1);
                setChars(0);
            }, OUTPUT_MS);
        } else if (chars < step.text.length) {
            timer = setTimeout(() => setChars((c) => c + 1), TYPE_MS);
        } else {
            timer = setTimeout(() => {
                setLine((n) => n + 1);
                setChars(0);
            }, PROMPT_MS);
        }

        return () => clearTimeout(timer);
    }, [started, done, line, chars]);

    const rendered = SCRIPT.slice(0, line);
    const current = line < SCRIPT.length ? SCRIPT[line] : null;

    return (
        <figure ref={hostRef} className="border border-line bg-raise shadow-2xl shadow-black/60">
            {/* window chrome */}
            <div className="flex items-center gap-3 border-b border-line px-4 py-3">
                <span className="flex gap-1.5" aria-hidden="true">
                    <span className="h-2 w-2 rounded-full border border-mute" />
                    <span className="h-2 w-2 rounded-full border border-mute" />
                    <span className="h-2 w-2 rounded-full border border-mute" />
                </span>
                <span className="ml-auto font-mono text-[0.6875rem] tracking-[0.18em] uppercase text-faint">
                    zsh — sample session
                </span>
            </div>

            <div className="min-h-[19rem] overflow-x-auto p-5 font-mono text-[0.8125rem] leading-[1.85] sm:min-h-[17.5rem]">
                {rendered.map((step, i) =>
                    step.kind === 'cmd' ? (
                        <p key={i} className="whitespace-pre text-bright">
                            <span className="mr-2 select-none text-signal">$</span>
                            {step.text}
                        </p>
                    ) : (
                        <p key={i} className={`whitespace-pre ${toneClass[step.tone]}`}>
                            {step.text}
                        </p>
                    )
                )}

                {current && current.kind === 'cmd' && (
                    <p className="whitespace-pre text-bright">
                        <span className="mr-2 select-none text-signal">$</span>
                        {current.text.slice(0, chars)}
                        <span className="caret text-signal">▍</span>
                    </p>
                )}

                {done && (
                    <p className="whitespace-pre text-bright">
                        <span className="mr-2 select-none text-signal">$</span>
                        <span className="caret text-signal">▍</span>
                    </p>
                )}
            </div>

            <figcaption className="border-t border-line px-4 py-3 text-xs text-dim">
                A recorded terminal session. Output is verbatim from the sec-mcp CLI.
            </figcaption>
        </figure>
    );
};

export default Terminal;
