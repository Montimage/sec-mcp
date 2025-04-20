import React from 'react';
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

const Hero = () => {
    return (
        <section id="hero" className="bg-gradient-to-b from-slate-800 to-slate-700 text-white py-24">
            <div className="container mx-auto px-4 flex flex-col lg:flex-row items-center">
                <div className="lg:w-1/2 mb-8 lg:mb-0">
                    <h1 className="text-4xl lg:text-5xl font-bold mb-4">sec-mcp: Security Checking Toolkit</h1>
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
                <div className="lg:w-1/2 flex justify-center">
                    <div className="bg-slate-900 p-6 rounded-lg shadow-2xl w-full max-w-2xl border border-slate-700">
                        <div className="flex items-center mb-4">
                            <div className="w-3 h-3 rounded-full bg-red-500 mr-2"></div>
                            <div className="w-3 h-3 rounded-full bg-yellow-500 mr-2"></div>
                            <div className="w-3 h-3 rounded-full bg-green-500"></div>
                            <span className="ml-4 text-slate-400 text-sm">code example</span>
                        </div>
                        <div className="relative">
                            <div className="absolute -left-2 -top-2 bottom-0 w-1 bg-blue-500 rounded"></div>
                            <SyntaxHighlighter
                                language="bash"
                                style={codeTheme}
                                customStyle={{marginTop: 0, marginBottom: 0}}
                                wrapLines={true}
                                showLineNumbers={false}
                            >
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
                            </SyntaxHighlighter>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
};

export default Hero;