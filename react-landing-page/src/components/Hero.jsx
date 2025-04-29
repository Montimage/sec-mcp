import React from 'react';
import CodeBlock from './CodeBlock';
import logoSvg from '../assets/logo.svg';
import montimageIconSvg from '../assets/montimage-logo.svg';

const Hero = () => {
    return (
        <section id="hero" className="bg-gradient-to-b from-slate-800 to-slate-700 text-white py-24">
            <div className="container mx-auto px-4 flex flex-col lg:flex-row items-center">
                <div className="lg:w-1/2 mb-8 lg:mb-0">
                    <div className="flex items-center mb-6">
                        <img src={logoSvg} alt="sec-mcp logo" className="w-16 h-16 mr-4" />
                        <h1 className="text-4xl lg:text-5xl font-bold">sec-mcp: Security Checking Toolkit</h1>
                    </div>
                    <p className="text-xl mb-6 text-slate-200">
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
                <div className="lg:w-1/2 flex justify-center">
                    <div className="bg-slate-900 p-6 rounded-lg shadow-2xl w-full max-w-2xl border border-slate-700">
                        <div className="flex items-center mb-4">
                            <div className="w-3 h-3 rounded-full bg-red-500 mr-2"></div>
                            <div className="w-3 h-3 rounded-full bg-yellow-500 mr-2"></div>
                            <div className="w-3 h-3 rounded-full bg-green-500"></div>
                            <span className="ml-4 text-slate-400 text-sm">code example</span>
                        </div>
                        <CodeBlock>
{`# Step 3: Install the package
pip install sec-mcp

# Step 7: Configure MCP client (Claude, etc.)
{
  "mcpServers": {
    "sec-mcp": {
      "command": "/path/to/.venv/bin/python3",
      "args": ["-m", "sec_mcp.start_server"]
    }
  }
}`}
                        </CodeBlock>
                    </div>
                </div>
            </div>
        </section>
    );
};

export default Hero;