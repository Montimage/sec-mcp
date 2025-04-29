import React from 'react';

const Footer = () => {
    return (
        <footer className="bg-slate-800 text-white py-10">
            <div className="container mx-auto px-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                    {/* Logo & Description */}
                    <div>
                        <div className="flex items-center mb-4">
                            <svg className="w-6 h-6 mr-2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                                <defs>
                                    <linearGradient id="footerGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                                        <stop offset="0%" stopColor="#3B82F6" />
                                        <stop offset="100%" stopColor="#2563EB" />
                                    </linearGradient>
                                </defs>
                                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" fill="url(#footerGradient)" stroke="#1E40AF" strokeWidth="1" />
                                <path d="M12 4 L12 18" stroke="white" strokeWidth="0.5" opacity="0.7" />
                                <path d="M6 8 L18 8" stroke="white" strokeWidth="0.5" opacity="0.7" />
                                <path d="M12 12 L18 12" stroke="white" strokeWidth="0.5" opacity="0.7" />
                                <path d="M6 16 L18 16" stroke="white" strokeWidth="0.5" opacity="0.7" />
                                <path d="M8 12L11 15L16 9" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                            <h2 className="text-xl font-bold">sec-mcp</h2>
                        </div>
                        <p className="text-slate-300 mb-4">
                            A Python security toolkit for checking domains, URLs, and IPs against multiple blacklist feeds,
                            with support for CLI, Python API, and MCP server for LLMs.
                        </p>
                        <p className="text-sm text-slate-400">
                            &copy; {new Date().getFullYear()} sec-mcp. Released under MIT License.
                        </p>
                    </div>

                    {/* Quick Links */}
                    <div>
                        <h3 className="text-lg font-semibold mb-4">Quick Links</h3>
                        <ul className="space-y-2">
                            <li><a href="#features" className="text-slate-300 hover:text-blue-400 transition-colors">Features</a></li>
                            <li><a href="#installation" className="text-slate-300 hover:text-blue-400 transition-colors">Installation</a></li>
                            <li><a href="#api" className="text-slate-300 hover:text-blue-400 transition-colors">API Reference</a></li>
                            <li><a href="#mcp" className="text-slate-300 hover:text-blue-400 transition-colors">MCP Server</a></li>
                        </ul>
                    </div>

                    {/* Resources */}
                    <div>
                        <h3 className="text-lg font-semibold mb-4">Resources</h3>
                        <ul className="space-y-2">
                            <li>
                                <a
                                    href="https://github.com/montimage/sec-mcp"
                                    className="text-slate-300 hover:text-blue-400 transition-colors flex items-center"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                >
                                    <svg className="w-4 h-4 mr-2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
                                        <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                                    </svg>
                                    GitHub Repository
                                </a>
                            </li>
                            <li>
                                <a
                                    href="https://pypi.org/project/sec-mcp/"
                                    className="text-slate-300 hover:text-blue-400 transition-colors flex items-center"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                >
                                    <svg className="w-4 h-4 mr-2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M8 3H5a2 2 0 0 0-2 2v14c0 1.1.9 2 2 2h14a2 2 0 0 0 2-2v-3"></path>
                                        <path d="M18 3h-4a2 2 0 0 0-2 2v14c0 1.1.9 2 2 2h4"></path>
                                        <path d="M8 13h14"></path>
                                    </svg>
                                    PyPI Package
                                </a>
                            </li>
                            <li>
                                <a
                                    href="https://modelcontextprotocol.io/examples"
                                    className="text-slate-300 hover:text-blue-400 transition-colors flex items-center"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                >
                                    <svg className="w-4 h-4 mr-2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
                                        <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path>
                                    </svg>
                                    MCP Documentation
                                </a>
                            </li>
                            <li>
                                <a
                                    href="mailto:contact@example.com"
                                    className="text-slate-300 hover:text-blue-400 transition-colors flex items-center"
                                >
                                    <svg className="w-4 h-4 mr-2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
                                        <polyline points="22,6 12,13 2,6"></polyline>
                                    </svg>
                                    Contact Support
                                </a>
                            </li>
                        </ul>
                    </div>
                </div>

                <div className="border-t border-gray-700 mt-8 pt-8 text-sm text-center text-slate-400">
                    <p>
                        Powered by React, Vite, and TailwindCSS. Built on {new Date().toLocaleDateString()}
                    </p>
                    <p className="mt-2">
                        sec-mcp uses blacklist data from multiple sources including OpenPhish, PhishStats, and URLhaus.
                    </p>
                </div>
            </div>
        </footer>
    );
};

export default Footer;