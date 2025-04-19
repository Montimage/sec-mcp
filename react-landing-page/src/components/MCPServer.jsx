import React from 'react';

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

                        <div className="space-y-4">
                            <div>
                                <h4 className="font-semibold mb-2">1. Install sec-mcp</h4>
                                <div className="bg-slate-800 rounded-lg p-3">
                                    <pre className="text-blue-400 text-sm overflow-x-auto">
                                        <code>pip install sec-mcp</code>
                                    </pre>
                                </div>
                            </div>

                            <div>
                                <h4 className="font-semibold mb-2">2. Start the MCP server</h4>
                                <div className="bg-slate-800 rounded-lg p-3">
                                    <pre className="text-blue-400 text-sm overflow-x-auto">
                                        <code>sec-mcp-server</code>
                                    </pre>
                                </div>
                            </div>

                            <div>
                                <h4 className="font-semibold mb-2">3. Configure your MCP client (e.g., Claude)</h4>
                                <div className="bg-slate-800 rounded-lg p-3">
                                    <pre className="text-blue-400 text-sm overflow-x-auto">
                                        <code>{`{
  "mcpServers": {
    "sec-mcp": {
      "command": "/path/to/your/python3",
      "args": ["-m", "sec_mcp.start_server"]
    }
  }
}`}</code>
                                    </pre>
                                </div>
                            </div>
                        </div>

                        <div className="mt-6 p-4 bg-blue-50 border border-blue-100 rounded-md">
                            <h4 className="font-semibold text-blue-700 mb-2">Integration Tips</h4>
                            <ul className="list-disc list-inside text-gray-600 space-y-1">
                                <li>For virtual environments, use the absolute path to the Python executable</li>
                                <li>For system-wide installations, use <code className="bg-gray-100 px-1 rounded">python3</code> or <code className="bg-gray-100 px-1 rounded">python</code></li>
                                <li>Ensure all dependencies are installed in your environment</li>
                                <li>The MCP server will automatically maintain the blacklist database</li>
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
                                                    <code className="font-mono text-blue-600">{tool.name}</code>
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
                            <div className="bg-slate-800 rounded-lg p-3">
                                <pre className="text-green-400 text-sm overflow-x-auto">
                                    <code>{`User: "Is example.com safe to visit?"

AI: Let me check that URL for you.
[Uses sec-mcp.check_blacklist tool]

I've checked example.com against our security database.
The domain is not found in any blacklists and
appears to be safe to visit.`}</code>
                                </pre>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
};

export default MCPServer;