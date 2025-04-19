import React from 'react';

const Hero = () => {
    return (
        <section id="hero" className="bg-gradient-to-b from-slate-800 to-slate-700 text-white py-24">
            <div className="container mx-auto px-4 flex flex-col md:flex-row items-center">
                <div className="md:w-1/2 mb-8 md:mb-0">
                    <h1 className="text-4xl md:text-5xl font-bold mb-4">sec-mcp: Security Checking Toolkit</h1>
                    <p className="text-xl mb-8 text-slate-200">
                        A Python toolkit providing security checks for domains, URLs, IPs, and more.
                        Integrate easily into any Python application, use via terminal CLI, or run as an MCP server
                        to enrich LLM context with real-time threat insights.
                    </p>
                    <div className="flex flex-wrap gap-4">
                        <a href="#installation" className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-3 rounded-lg transition-colors">
                            Get Started
                        </a>
                        <a href="#api" className="border border-white hover:bg-white hover:text-slate-800 text-white font-semibold px-6 py-3 rounded-lg transition-colors">
                            View Documentation
                        </a>
                    </div>
                </div>
                <div className="md:w-1/2 flex justify-center">
                    <div className="bg-slate-900 p-6 rounded-lg shadow-2xl w-full max-w-md">
                        <div className="flex items-center mb-4">
                            <div className="w-3 h-3 rounded-full bg-red-500 mr-2"></div>
                            <div className="w-3 h-3 rounded-full bg-yellow-500 mr-2"></div>
                            <div className="w-3 h-3 rounded-full bg-green-500"></div>
                        </div>
                        <pre className="text-blue-400 overflow-x-auto pb-2">
                            <code>
{`# Install the package
pip install sec-mcp

# Check a URL or IP
sec-mcp check https://example.com

# Run as MCP server for LLMs
sec-mcp-server`}
                            </code>
                        </pre>
                    </div>
                </div>
            </div>
        </section>
    );
};

export default Hero;