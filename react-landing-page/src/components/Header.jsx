import React from 'react';
import montimageIconSvg from '../assets/montimage-logo.svg';

const Header = () => {
    return (
        <header className="bg-slate-800 text-white p-4 shadow-md">
            <div className="container mx-auto flex flex-col md:flex-row md:justify-between items-center">
                <div className="flex items-center mb-6 md:mb-0">
                    <h1 className="text-2xl font-bold flex items-center">
                        <svg className="w-8 h-8 mr-2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                            {/* Security shield with network/check elements */}
                            <defs>
                                <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                                    <stop offset="0%" stopColor="#3B82F6" />
                                    <stop offset="100%" stopColor="#2563EB" />
                                </linearGradient>
                            </defs>
                            {/* Shield background */}
                            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" fill="url(#gradient)" stroke="#1E40AF" strokeWidth="1" />
                            
                            {/* Network/globe grid lines representing security scanning */}
                            <path d="M12 4 L12 18" stroke="white" strokeWidth="0.5" opacity="0.7" />
                            <path d="M6 8 L18 8" stroke="white" strokeWidth="0.5" opacity="0.7" />
                            <path d="M6 12 L18 12" stroke="white" strokeWidth="0.5" opacity="0.7" />
                            <path d="M6 16 L18 16" stroke="white" strokeWidth="0.5" opacity="0.7" />
                            
                            {/* Checkmark for security verification */}
                            <path d="M8 12L11 15L16 9" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        sec-mcp
                    </h1>
                    <div className="flex items-center ml-4 pl-4 border-l border-gray-600">
                        <span className="text-sm text-gray-400 mr-2">by</span>
                        <a href="https://www.montimage.eu" target="_blank" rel="noopener noreferrer" className="transition-opacity hover:opacity-80">
                            <img src={montimageIconSvg} alt="Montimage" className="h-6" />
                        </a> <span className="text-md text-gray-200 ml-2">Montimage</span>
                    </div>
                </div>
                <nav className="w-full md:w-auto">
                    <ul className="flex flex-wrap justify-center md:justify-start gap-4 md:gap-6">
                        <li><a href="#features" className="hover:text-blue-400 transition-colors">Features</a></li>
                        <li><a href="#api" className="hover:text-blue-400 transition-colors">API</a></li>
                        <li><a href="#installation" className="hover:text-blue-400 transition-colors">Installation</a></li>
                        <li><a href="#mcp" className="hover:text-blue-400 transition-colors">MCP Server</a></li>
                        <li>
                            <a href="mailto:contact@montimage.eu" className="flex items-center hover:text-blue-400 transition-colors">
                                <svg className="w-5 h-5 mr-1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="0.5">
                                    <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" />
                                </svg>
                                Contact
                            </a>
                        </li>
                        <li>
                            <a href="https://github.com/montimage/sec-mcp" className="flex items-center hover:text-blue-400 transition-colors" target="_blank" rel="noopener noreferrer">
                                <svg className="w-5 h-5 mr-1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                                </svg>
                                GitHub
                            </a>
                        </li>
                        <li>
                            <a href="https://pepy.tech/projects/sec-mcp"><img src="https://static.pepy.tech/badge/sec-mcp" alt="PyPI Downloads" /></a>
                        </li>
                    </ul>
                </nav>
            </div>
        </header>
    );
};

export default Header;