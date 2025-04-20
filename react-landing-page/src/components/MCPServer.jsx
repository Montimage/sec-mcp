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

const CodeBlock = ({ children, language = "bash", label = null }) => {
    return (
        <div className="relative">
            <div className="absolute top-0 right-0 bg-slate-700 text-xs px-2 py-1 rounded-bl text-slate-300 font-mono">
                {label || language.toUpperCase()}
            </div>
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

const MCPServer = () => {
    const mcpTools = [
        { name: 'check_blacklist', signature: 'check_blacklist(value: str)', description: 'Check a single value (domain, URL, or IP) against the blacklist.' },
        { name: 'check_batch', signature: 'check_batch(values: List[str])', description: 'Bulk check multiple domains/URLs/IPs in one call.' },
        { name: 'get_blacklist_status', signature: 'get_blacklist_status()', description: 'Get status of the blacklist, including entry counts and per-source breakdown.' },
        { name: 'sample_blacklist', signature: 'sample_blacklist(count: int)', description: 'Return a random sample of blacklist entries.' },
        { name: 'get_source_stats', signature: 'get_source_stats()', description: 'Retrieve detailed stats: total entries, per-source counts, last update timestamps.' },
        { name: 'get_update_history', signature: 'get_update_history(...)', description: 'Fetch update history records, optionally filtered by source and time range.' },
        { name: 'flush_cache', signature: 'flush_cache()', description: 'Clear the in-memory URL/IP cache.' },
        { name: 'add_entry', signature: 'add_entry(url, ip, ...)', description: 'Manually add a blacklist entry.' },
        { name: 'remove_entry', signature: 'remove_entry(value: str)', description: 'Remove a blacklist entry by URL or IP address.' },
        { name: 'update_blacklists', signature: 'update_blacklists()', description: 'Force immediate update of all blacklists.' },
        { name: 'health_check', signature: 'health_check()', description: 'Perform a health check of the database and scheduler.' }
    ];

    return (
        <section id="mcp" className="py-16 bg-white">
            <div className="container mx-auto px-4">
                <h2 className="text-3xl font-bold text-center mb-4">MCP Server for LLMs</h2>
                <p className="text-gray-600 text-center mb-12 max-w-3xl mx-auto">
                    Use sec-mcp as a Model Context Protocol (MCP) server to provide real-time security checks in LLM workflows.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-6xl mx-auto">
                    <div className="bg-slate-50 p-6 rounded-lg shadow-md">
                        <h3 className="text-xl font-semibold mb-4">MCP Server Setup</h3>

                        <div className="space-y-6">
                            {/* Step summary card */}
                            <div className="bg-blue-50 p-4 rounded-md border border-blue-200">
                                <h4 className="font-semibold text-blue-700 mb-2">Complete Setup Process</h4>
                                <ol className="list-decimal list-inside space-y-1 text-gray-700">
                                    <li>Create a virtual environment: <code className="bg-slate-900 text-yellow-400 px-2 py-0.5 rounded">python3.12 -m venv .venv</code></li>
                                    <li>Activate the environment: <code className="bg-slate-900 text-yellow-400 px-2 py-0.5 rounded">source .venv/bin/activate</code></li>
                                    <li>Install sec-mcp: <code className="bg-slate-900 text-yellow-400 px-2 py-0.5 rounded">pip install sec-mcp</code></li>
                                    <li>Verify status: <code className="bg-slate-900 text-yellow-400 px-2 py-0.5 rounded">sec-mcp status</code></li>
                                    <li>Update database: <code className="bg-slate-900 text-yellow-400 px-2 py-0.5 rounded">sec-mcp update</code></li>
                                    <li>Verify database: <code className="bg-slate-900 text-yellow-400 px-2 py-0.5 rounded">sec-mcp status</code></li>
                                    <li>Configure MCP client with command and args</li>
                                    <li>Use sec-mcp tools in your MCP client</li>
                                </ol>
                                <p className="mt-3 text-sm text-blue-800">
                                    For detailed instructions, see the <a href="#installation" className="underline hover:text-blue-600">Installation Guide</a>.
                                </p>
                            </div>

                            {/* MCP Client Config */}
                            <div>
                                <h4 className="font-semibold mb-2">MCP Client Configuration</h4>
                                <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
                                    <CodeBlock language="json" label="JSON">
{`{
  "mcpServers": {
    "sec-mcp": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["-m", "sec_mcp.start_server"]
    }
  }
}`}
                                    </CodeBlock>
                                </div>
                                <div className="mt-2 text-gray-600 text-sm">
                                    <p><strong>Important:</strong> Use the absolute path to the Python executable in your virtual environment.</p>
                                </div>
                            </div>
                        </div>

                        <div className="mt-6 p-4 bg-amber-50 border border-amber-100 rounded-md">
                            <h4 className="font-semibold text-amber-700 mb-2">Integration Tips</h4>
                            <ul className="list-disc list-inside text-gray-600 space-y-1">
                                <li>For virtual environments, always use the <strong>absolute path</strong> to the Python executable</li>
                                <li>Check that the database is populated before using the MCP client</li>
                                <li>If the database update fails, check your internet connection</li>
                                <li>The MCP server will automatically start when your MCP client runs</li>
                            </ul>
                        </div>
                    </div>

                    <div>
                        <h3 className="text-xl font-semibold mb-4">Available MCP Tools</h3>
                        <div className="bg-white rounded-lg shadow overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="min-w-full">
                                    <thead>
                                        <tr className="bg-slate-700 text-white">
                                            <th className="py-3 px-4 text-left">Tool Name</th>
                                            <th className="py-3 px-4 text-left">Description</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {mcpTools.map((tool, index) => (
                                            <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                                <td className="py-2 px-4 border-b">
                                                    <code className="font-mono bg-slate-100 px-2 py-0.5 rounded text-purple-600">{tool.name}</code>
                                                </td>
                                                <td className="py-2 px-4 border-b text-sm text-gray-700">
                                                    {tool.description}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <div className="mt-6">
                            <h4 className="font-semibold mb-3">Example LLM Integration</h4>
                            <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
                                <CodeBlock language="markdown" label="Chat">
{`User: "Is example.com safe to visit?"

AI: Let me check that URL for you.
[Uses sec-mcp.check_blacklist tool]

I've checked example.com against our security database.
The domain is not found in any blacklists and
appears to be safe to visit.`}
                                </CodeBlock>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
};

export default MCPServer;