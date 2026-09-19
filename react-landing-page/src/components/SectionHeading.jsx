import React from 'react';
import Reveal from './Reveal';

/**
 * Every section opens the same way: a full-bleed hairline, a monospace
 * index/label row, then a display-serif title and a lede. Repeating this
 * exactly gives the page its rhythm and tells a scanner where they are —
 * the numbering is the "you are here" signal.
 */
const SectionHeading = ({ index, label, title, lede, meta }) => (
    <header className="mb-14 md:mb-20">
        <div className="rule-signal mb-5 draw-in" />

        <Reveal className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
            <p className="font-mono text-xs tracking-[0.22em] uppercase text-dim">
                <span className="text-signal">{index}</span>
                <span className="mx-2.5 text-faint" aria-hidden="true">
                    /
                </span>
                {label}
            </p>
            {meta && (
                /* Hidden on phones: the label above already wraps to two lines
                   there, and a third quiet line reads as part of it rather than
                   as metadata. Every meta string is supplementary. */
                <p className="hidden font-mono text-xs tracking-[0.14em] uppercase text-faint sm:block">
                    {meta}
                </p>
            )}
        </Reveal>

        <Reveal delay={80}>
            <h2 className="font-display font-light text-title mt-7 max-w-4xl text-balance">
                {title}
            </h2>
        </Reveal>

        {lede && (
            <Reveal delay={150}>
                <p className="mt-6 max-w-2xl text-lg leading-relaxed text-dim text-pretty">
                    {lede}
                </p>
            </Reveal>
        )}
    </header>
);

export default SectionHeading;
