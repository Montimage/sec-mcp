import React from 'react';
import Logo from './Logo';
import Reveal from './Reveal';
import CodeBlock from './CodeBlock';
import montimageIconSvg from '../assets/montimage-logo.svg';

const SECTION_LINKS = [
    { href: '#features', label: 'Features' },
    { href: '#sources', label: 'Sources' },
    { href: '#mcp', label: 'MCP Server' },
    { href: '#install', label: 'Install' },
    { href: '#api', label: 'API Reference' },
];

const RESOURCE_LINKS = [
    { href: 'https://github.com/montimage/sec-mcp', label: 'GitHub repository' },
    { href: 'https://pypi.org/project/sec-mcp/', label: 'PyPI package' },
    { href: 'https://modelcontextprotocol.io/examples', label: 'MCP documentation' },
    { href: 'https://www.montimage.eu', label: 'Montimage' },
];

const Footer = () => (
    <footer className="field relative border-t border-line">
        {/* --- closing call to action ---------------------------------- */}
        <div className="mx-auto max-w-[84rem] px-4 py-24 sm:px-6 md:py-32 lg:px-10">
            <div className="grid items-center gap-12 lg:grid-cols-12 lg:gap-16">
                <Reveal className="min-w-0 lg:col-span-7">
                    <p className="font-mono text-xs tracking-[0.22em] uppercase text-dim">
                        <span className="text-signal">07</span>
                        <span className="mx-2.5 text-faint" aria-hidden="true">/</span>
                        Get started
                    </p>
                    <h2 className="mt-7 font-display text-title font-light text-balance">
                        One command, and your code stops trusting strangers.
                    </h2>
                    <div className="mt-9 flex flex-wrap items-center gap-3">
                        <a
                            href="#install"
                            className="flex h-12 w-full items-center justify-center bg-bright px-7 font-mono sm:w-auto sm:justify-start text-xs font-medium tracking-[0.16em] uppercase text-void transition-colors hover:bg-dim"
                        >
                            Install guide
                        </a>
                        <a
                            href="https://github.com/montimage/sec-mcp"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="group flex h-12 w-full items-center justify-center gap-2 border border-line-2 px-7 font-mono sm:w-auto sm:justify-start text-xs tracking-[0.16em] uppercase text-bright transition-colors hover:border-signal hover:text-signal"
                        >
                            Star on GitHub
                            <span className="transition-transform group-hover:translate-x-1" aria-hidden="true">
                                &rarr;
                            </span>
                        </a>
                    </div>
                </Reveal>

                <Reveal delay={100} className="min-w-0 lg:col-span-5">
                    <CodeBlock language="bash" label="install">
                        pip install sec-mcp
                    </CodeBlock>
                    <p className="mt-3 font-mono text-xs text-faint">
                        Python 3.11+ &middot; MIT licence &middot; no API key
                    </p>
                </Reveal>
            </div>
        </div>

        {/* --- link columns -------------------------------------------- */}
        <div className="border-t border-line">
            <div className="mx-auto grid max-w-[84rem] gap-12 px-4 py-16 sm:px-6 md:grid-cols-12 lg:px-10">
                <div className="min-w-0 md:col-span-5">
                    <div className="flex items-center gap-2.5 text-bright">
                        <Logo className="h-6 w-6" />
                        <span className="font-mono text-sm font-medium">sec-mcp</span>
                    </div>
                    <p className="mt-5 max-w-sm text-sm leading-relaxed text-dim text-pretty">
                        A Python toolkit that checks domains, URLs and IP addresses against ten
                        public blacklist feeds &mdash; as a library, a CLI, or an MCP server for
                        LLM workflows.
                    </p>
                    <a
                        href="https://pepy.tech/projects/sec-mcp"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-6 inline-block"
                    >
                        <img
                            src="https://static.pepy.tech/badge/sec-mcp"
                            alt="Total sec-mcp downloads on PyPI"
                            width="110"
                            height="20"
                            loading="lazy"
                        />
                    </a>
                </div>

                <nav className="min-w-0 md:col-span-3" aria-label="Sections">
                    <h2 className="font-mono text-xs tracking-[0.18em] uppercase text-faint">
                        On this page
                    </h2>
                    <ul className="mt-5 space-y-3">
                        {SECTION_LINKS.map((link) => (
                            <li key={link.href}>
                                <a
                                    href={link.href}
                                    className="text-sm text-dim transition-colors hover:text-signal"
                                >
                                    {link.label}
                                </a>
                            </li>
                        ))}
                    </ul>
                </nav>

                <nav className="min-w-0 md:col-span-4" aria-label="Resources">
                    <h2 className="font-mono text-xs tracking-[0.18em] uppercase text-faint">
                        Resources
                    </h2>
                    <ul className="mt-5 space-y-3">
                        {RESOURCE_LINKS.map((link) => (
                            <li key={link.href}>
                                <a
                                    href={link.href}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="group inline-flex items-center gap-1.5 text-sm text-dim transition-colors hover:text-signal"
                                >
                                    {link.label}
                                    <span
                                        className="text-faint transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
                                        aria-hidden="true"
                                    >
                                        &#8599;
                                    </span>
                                </a>
                            </li>
                        ))}
                        <li>
                            <a
                                href="mailto:contact@montimage.eu"
                                className="text-sm text-dim transition-colors hover:text-signal"
                            >
                                contact@montimage.eu
                            </a>
                        </li>
                    </ul>
                </nav>
            </div>
        </div>

        {/* --- colophon ------------------------------------------------- */}
        <div className="border-t border-line">
            <div className="mx-auto flex max-w-[84rem] flex-col gap-4 px-4 py-8 text-xs text-dim sm:px-6 md:flex-row md:items-center md:justify-between lg:px-10">
                <p>
                    &copy; {new Date().getFullYear()} Montimage &middot; Released under the MIT
                    licence
                </p>
                <p className="flex flex-wrap items-center gap-2">
                    <span>Built by</span>
                    <a
                        href="https://www.montimage.eu"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 text-bright transition-opacity hover:opacity-70"
                    >
                        <img src={montimageIconSvg} alt="" className="h-5 w-auto" />
                        Montimage
                    </a>
                    <span className="text-faint">&middot; cybersecurity &amp; network monitoring</span>
                </p>
            </div>
        </div>
    </footer>
);

export default Footer;
