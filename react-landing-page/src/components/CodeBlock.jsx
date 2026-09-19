import React, { useState } from 'react';
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter';
import bash from 'react-syntax-highlighter/dist/esm/languages/prism/bash';
import json from 'react-syntax-highlighter/dist/esm/languages/prism/json';
import markdown from 'react-syntax-highlighter/dist/esm/languages/prism/markdown';
import python from 'react-syntax-highlighter/dist/esm/languages/prism/python';

// PrismLight + explicit registration instead of the full Prism build: the page
// only ever shows these four languages, and the default import pulls in every
// grammar Prism ships.
SyntaxHighlighter.registerLanguage('bash', bash);
SyntaxHighlighter.registerLanguage('json', json);
SyntaxHighlighter.registerLanguage('markdown', markdown);
SyntaxHighlighter.registerLanguage('python', python);

/**
 * A syntax theme written from scratch in the page palette instead of importing
 * a rainbow one. Code reads as part of the design rather than a pasted
 * screenshot: white for structure, gray for punctuation and comments, green
 * for strings, amber for literals. Every colour here clears WCAG AA on the
 * near-black code surface.
 */
const base = {
    color: '#ffffff',
    background: 'none',
    fontFamily: '"IBM Plex Mono", ui-monospace, SFMono-Regular, monospace',
    fontSize: '0.8125rem',
    lineHeight: 1.75,
    direction: 'ltr',
    textAlign: 'left',
    whiteSpace: 'pre',
    wordSpacing: 'normal',
    wordBreak: 'normal',
    tabSize: 4,
    hyphens: 'none',
};

const theme = {
    'code[class*="language-"]': base,
    'pre[class*="language-"]': { ...base, padding: 0, margin: 0, overflow: 'auto' },
    comment: { color: '#9ca3af', fontStyle: 'italic' },
    prolog: { color: '#9ca3af' },
    doctype: { color: '#9ca3af' },
    cdata: { color: '#9ca3af' },
    punctuation: { color: '#9ca3af' },
    operator: { color: '#9ca3af' },
    property: { color: '#ffffff' },
    tag: { color: '#ffffff' },
    boolean: { color: '#f59e0b' },
    number: { color: '#f59e0b' },
    constant: { color: '#f59e0b' },
    symbol: { color: '#f59e0b' },
    deleted: { color: '#ef4444' },
    selector: { color: '#22c55e' },
    'attr-name': { color: '#22c55e' },
    string: { color: '#22c55e' },
    char: { color: '#22c55e' },
    builtin: { color: '#ffffff' },
    inserted: { color: '#22c55e' },
    variable: { color: '#ffffff' },
    atrule: { color: '#ffffff' },
    'attr-value': { color: '#22c55e' },
    keyword: { color: '#ffffff', fontWeight: '600' },
    function: { color: '#ffffff' },
    'class-name': { color: '#ffffff' },
    regex: { color: '#22c55e' },
    important: { color: '#f59e0b', fontWeight: 'bold' },
    bold: { fontWeight: 'bold' },
    italic: { fontStyle: 'italic' },
};

const CodeBlock = ({ children, language = 'bash', label = null }) => {
    const [state, setState] = useState('idle'); // idle | copied | failed

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(children);
            setState('copied');
        } catch {
            setState('failed');
        }
        setTimeout(() => setState('idle'), 2000);
    };

    const caption = label || language;

    return (
        <figure className="code-surface group border border-line bg-raise">
            {/* chrome: language on the left, copy on the right, hairline below */}
            <figcaption className="flex items-center justify-between border-b border-line pl-4 pr-1">
                <span className="font-mono text-[0.6875rem] tracking-[0.18em] uppercase text-faint">
                    {caption}
                </span>
                <button
                    type="button"
                    onClick={handleCopy}
                    aria-label={`Copy ${caption} snippet to clipboard`}
                    className={`min-h-[44px] min-w-[68px] px-3 font-mono text-[0.6875rem] tracking-[0.14em] uppercase transition-colors ${
                        state === 'failed'
                            ? 'text-danger'
                            : state === 'copied'
                              ? 'text-signal'
                              : 'text-dim hover:text-bright'
                    }`}
                >
                    {state === 'failed' ? 'Failed' : state === 'copied' ? 'Copied' : 'Copy'}
                </button>
                {/* announce the result for screen readers without moving focus */}
                <span className="sr-only" role="status" aria-live="polite">
                    {state === 'copied'
                        ? 'Copied to clipboard'
                        : state === 'failed'
                          ? 'Copy failed'
                          : ''}
                </span>
            </figcaption>

            <div className="overflow-x-auto p-4">
                <SyntaxHighlighter language={language} style={theme} PreTag="pre">
                    {children}
                </SyntaxHighlighter>
            </div>
        </figure>
    );
};

export default CodeBlock;
