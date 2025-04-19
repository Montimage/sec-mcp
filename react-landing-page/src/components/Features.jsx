import React from 'react';

const Features = () => {
    const featuresList = [
        {
            title: 'Comprehensive Security Checks',
            description: 'Security verification for domains, URLs, IPs, and more against multiple blacklist feeds.',
            icon: (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
            )
        },
        {
            title: 'Multiple Integration Options',
            description: 'Use as a Python API, CLI tool, or MCP server for AI/LLM integrations over JSON/STDIO.',
            icon: (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z" />
                </svg>
            )
        },
        {
            title: 'High-Performance Storage',
            description: 'Thread-safe SQLite storage with in-memory caching for ultra-fast lookups and responses.',
            icon: (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
                </svg>
            )
        },
        {
            title: 'MCP Server for LLMs',
            description: 'Enrich AI workflows with real-time security checks using the Model Context Protocol (MCP).',
            icon: (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
            )
        },
        {
            title: 'Automatic Updates',
            description: 'On-demand updates from OpenPhish, PhishStats, URLhaus and custom sources.',
            icon: (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
            )
        },
        {
            title: 'Extensive API',
            description: 'Rich set of functions for checking URLs, domains, IPs with detailed response information.',
            icon: (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
            )
        }
    ];

    return (
        <section id="features" className="py-16 bg-gray-50">
            <div className="container mx-auto px-4">
                <h2 className="text-3xl font-bold text-center mb-4">Key Features</h2>
                <p className="text-gray-600 text-center mb-12 max-w-3xl mx-auto">
                    sec-mcp provides powerful tools for security verification with multiple integration options
                    and high-performance capabilities.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                    {featuresList.map((feature, index) => (
                        <div key={index} className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300 flex flex-col items-center text-center">
                            <div className="mb-4">
                                {feature.icon}
                            </div>
                            <h3 className="text-xl font-semibold mb-3">{feature.title}</h3>
                            <p className="text-gray-600">{feature.description}</p>
                        </div>
                    ))}
                </div>

                <div className="mt-16 bg-blue-50 border border-blue-100 rounded-lg p-6 md:p-8">
                    <h3 className="text-2xl font-bold mb-4 text-center">MCP Server & LLM Support</h3>
                    <p className="text-gray-600 mb-6 text-center">
                        sec-mcp is designed for seamless integration with Model Context Protocol (MCP) compatible clients
                        (e.g., Claude, Windsurf, Cursor) for real-time security checks in LLM workflows.
                    </p>

                    <div className="overflow-x-auto">
                        <table className="min-w-full bg-white border border-gray-200 rounded-lg">
                            <thead className="bg-gray-100">
                                <tr>
                                    <th className="py-3 px-4 text-left text-sm font-semibold text-gray-700 border-b">Tool Name</th>
                                    <th className="py-3 px-4 text-left text-sm font-semibold text-gray-700 border-b">Description</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td className="py-3 px-4 border-b text-sm font-mono text-blue-600">check_blacklist</td>
                                    <td className="py-3 px-4 border-b text-sm">Check a single value (domain, URL, or IP) against the blacklist</td>
                                </tr>
                                <tr>
                                    <td className="py-3 px-4 border-b text-sm font-mono text-blue-600">check_batch</td>
                                    <td className="py-3 px-4 border-b text-sm">Bulk check multiple domains/URLs/IPs in one call</td>
                                </tr>
                                <tr>
                                    <td className="py-3 px-4 border-b text-sm font-mono text-blue-600">get_blacklist_status</td>
                                    <td className="py-3 px-4 border-b text-sm">Get status of the blacklist, including entry counts</td>
                                </tr>
                                <tr>
                                    <td className="py-3 px-4 border-b text-sm font-mono text-blue-600">update_blacklists</td>
                                    <td className="py-3 px-4 border-b text-sm">Force immediate update of all blacklists</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </section>
    );
};

export default Features;