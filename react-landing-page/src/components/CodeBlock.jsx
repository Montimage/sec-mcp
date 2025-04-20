import React, { useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

// Custom theme based on atomDark with blue accent
const codeTheme = {
    ...atomDark,
    'pre[class*="language-"]': {
        ...atomDark['pre[class*="language-"]'],
        background: '#1e293b', // slate-800
        margin: 0,
        borderRadius: '0.25rem',
        padding: '1rem'
    },
    'code[class*="language-"]': {
        ...atomDark['code[class*="language-"]'],
        background: 'transparent'
    }
};

const CodeBlock = ({ children, language = "bash", label = null }) => {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(children);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error('Failed to copy text: ', err);
        }
    };

    return (
        <div className="relative">
            <button
                onClick={handleCopy}
                className="absolute top-0 right-0 bg-slate-700 hover:bg-slate-600 text-slate-300 hover:text-white px-2 py-1 rounded-bl text-xs font-mono transition-colors"
            >
                {copied ? 'Copied!' : 'Copy'}
            </button>
            <div className="absolute -left-1 top-0 bottom-0 w-1 bg-blue-500 rounded"></div>
            <SyntaxHighlighter
                language={language}
                style={codeTheme}
                customStyle={{marginTop: 0, marginBottom: 0}}
                wrapLines={true}
            >
                {children}
            </SyntaxHighlighter>
        </div>
    );
};

export default CodeBlock;