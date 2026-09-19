import React, { useEffect, useState } from 'react';
import Logo from './Logo';
import montimageIconSvg from '../assets/montimage-logo.svg';

const NAV = [
    { href: '#features', label: 'Features' },
    { href: '#sources', label: 'Sources' },
    { href: '#mcp', label: 'MCP Server' },
    { href: '#install', label: 'Install' },
    { href: '#api', label: 'API' },
];

const GitHubIcon = ({ className = 'h-4 w-4' }) => (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
    </svg>
);

const Header = () => {
    const [scrolled, setScrolled] = useState(false);
    const [open, setOpen] = useState(false);

    // The header is transparent over the hero and only grows its hairline and
    // blur once you leave it — so the hero reads as full-bleed.
    useEffect(() => {
        const onScroll = () => setScrolled(window.scrollY > 24);
        onScroll();
        window.addEventListener('scroll', onScroll, { passive: true });
        return () => window.removeEventListener('scroll', onScroll);
    }, []);

    return (
        <header
            className={`fixed inset-x-0 top-0 z-50 transition-colors duration-300 ${
                scrolled || open
                    ? 'border-b border-line bg-void/85 backdrop-blur-xl'
                    : 'border-b border-transparent'
            }`}
        >
            <div className="mx-auto flex h-16 max-w-[84rem] items-center gap-6 px-4 sm:px-6 lg:px-10">
                {/* identity — upper left, on every viewport */}
                <a
                    href="#top"
                    className="flex shrink-0 items-center gap-2.5 text-bright transition-opacity hover:opacity-70"
                    aria-label="sec-mcp — back to top"
                >
                    <Logo className="h-6 w-6" />
                    <span className="font-mono text-sm font-medium tracking-tight">sec-mcp</span>
                </a>

                <span className="hidden h-4 w-px bg-line-2 lg:block" aria-hidden="true" />

                <a
                    href="https://www.montimage.eu"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hidden items-center gap-2 text-xs text-dim transition-colors hover:text-bright lg:flex"
                >
                    <span className="font-mono tracking-[0.14em] uppercase">by</span>
                    <img src={montimageIconSvg} alt="Montimage" className="h-4 w-auto" />
                    <span>Montimage</span>
                </a>

                {/* desktop nav */}
                <nav className="ml-auto hidden md:block" aria-label="Main">
                    <ul className="flex items-center gap-7">
                        {NAV.map((item) => (
                            <li key={item.href}>
                                <a
                                    href={item.href}
                                    className="font-mono text-xs tracking-[0.14em] uppercase text-dim transition-colors hover:text-bright"
                                >
                                    {item.label}
                                </a>
                            </li>
                        ))}
                    </ul>
                </nav>

                <div className="ml-auto flex items-center gap-2 md:ml-0">
                    <a
                        href="https://github.com/montimage/sec-mcp"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hidden h-9 items-center gap-2 border border-line px-3 font-mono text-xs tracking-[0.14em] uppercase text-dim transition-colors hover:border-line-2 hover:text-bright sm:flex"
                    >
                        <GitHubIcon />
                        GitHub
                    </a>
                    <a
                        href="#install"
                        className="hidden h-9 items-center bg-bright px-4 font-mono text-xs font-medium tracking-[0.14em] uppercase text-void transition-colors hover:bg-dim sm:flex"
                    >
                        Get started
                    </a>

                    {/* mobile menu toggle — hamburger, per convention */}
                    <button
                        type="button"
                        onClick={() => setOpen((v) => !v)}
                        aria-expanded={open}
                        aria-controls="mobile-nav"
                        aria-label={open ? 'Close menu' : 'Open menu'}
                        className="flex h-11 w-11 items-center justify-center text-bright md:hidden"
                    >
                        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                            {open ? (
                                <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
                            ) : (
                                <path d="M3.5 7.5h17M3.5 16.5h17" strokeLinecap="round" />
                            )}
                        </svg>
                    </button>
                </div>
            </div>

            {/* mobile nav */}
            {open && (
                <nav
                    id="mobile-nav"
                    aria-label="Main"
                    className="border-t border-line bg-void/95 backdrop-blur-xl md:hidden"
                >
                    <ul className="mx-auto max-w-[84rem] px-4 py-2 sm:px-6">
                        {NAV.map((item) => (
                            <li key={item.href} className="border-b border-line last:border-0">
                                <a
                                    href={item.href}
                                    onClick={() => setOpen(false)}
                                    className="block py-4 font-mono text-sm tracking-[0.14em] uppercase text-dim transition-colors hover:text-bright"
                                >
                                    {item.label}
                                </a>
                            </li>
                        ))}
                        <li className="flex gap-3 py-4">
                            <a
                                href="#install"
                                onClick={() => setOpen(false)}
                                className="flex h-11 flex-1 items-center justify-center bg-bright font-mono text-xs font-medium tracking-[0.14em] uppercase text-void"
                            >
                                Get started
                            </a>
                            <a
                                href="https://github.com/montimage/sec-mcp"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex h-11 flex-1 items-center justify-center gap-2 border border-line font-mono text-xs tracking-[0.14em] uppercase text-dim"
                            >
                                <GitHubIcon />
                                GitHub
                            </a>
                        </li>
                    </ul>
                </nav>
            )}
        </header>
    );
};

export default Header;
