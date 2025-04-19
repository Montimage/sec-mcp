import React from 'react';

const Installation = () => {
    return (
        <section id="installation" className="py-16 bg-white">
            <div className="container mx-auto px-4">
                <h2 className="text-3xl font-bold text-center mb-8">Installation & Usage</h2>

                <div className="max-w-4xl mx-auto">
                    {/* Installation Card */}
                    <div className="mb-12 bg-gray-50 rounded-lg p-6 shadow-md">
                        <h3 className="text-2xl font-semibold mb-4">Quick Installation</h3>

                        <div className="bg-slate-800 rounded-lg p-4 mb-4">
                            <pre className="text-green-400 overflow-x-auto">
                                <code>pip install sec-mcp</code>
                            </pre>
                        </div>

                        <p className="text-gray-600 mb-2">
                            This installs the sec-mcp package with all dependencies required for security checks
                            against multiple blacklist feeds.
                        </p>

                        <div className="mt-4">
                            <h4 className="text-lg font-semibold mb-2">Environment Configuration</h4>
                            <p className="text-gray-600 mb-2">
                                By default, sec-mcp stores its SQLite database in a platform-specific location:
                            </p>
                            <ul className="list-disc list-inside text-gray-600 ml-4 space-y-1">
                                <li><span className="font-mono">macOS:</span> ~/Library/Application Support/sec-mcp/mcp.db</li>
                                <li><span className="font-mono">Linux:</span> ~/.local/share/sec-mcp/mcp.db</li>
                                <li><span className="font-mono">Windows:</span> %APPDATA%\sec-mcp\mcp.db</li>
                            </ul>
                            <p className="text-gray-600 mt-2">
                                You can override this location by setting the <span className="font-mono">MCP_DB_PATH</span> environment variable.
                            </p>
                        </div>
                    </div>

                    {/* Usage Cards */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
                        {/* CLI Usage */}
                        <div className="bg-gray-50 rounded-lg p-6 shadow-md">
                            <h3 className="text-xl font-semibold mb-3">CLI Usage</h3>
                            <div className="bg-slate-800 rounded-lg p-3 mb-3">
                                <pre className="text-blue-400 text-sm overflow-x-auto">
                                    <code>{`# Check a single URL/domain/IP
sec-mcp check https://example.com

# Batch check from a file
sec-mcp batch urls.txt

# View blacklist status
sec-mcp status

# Trigger an update
sec-mcp update`}</code>
                                </pre>
                            </div>
                            <p className="text-gray-600 text-sm">
                                The CLI provides quick access to all sec-mcp features from your terminal.
                            </p>
                        </div>

                        {/* Python API Usage */}
                        <div className="bg-gray-50 rounded-lg p-6 shadow-md">
                            <h3 className="text-xl font-semibold mb-3">Python API</h3>
                            <div className="bg-slate-800 rounded-lg p-3 mb-3">
                                <pre className="text-blue-400 text-sm overflow-x-auto">
                                    <code>{`# Import and initialize
from sec_mcp import SecMCP

client = SecMCP()

# Single check
result = client.check("example.com")
print(result.to_json())

# Batch check
urls = ["example1.com", "example2.com"]
results = client.check_batch(urls)`}</code>
                                </pre>
                            </div>
                            <p className="text-gray-600 text-sm">
                                Integrate sec-mcp directly into your Python applications.
                            </p>
                        </div>

                        {/* MCP Server Usage */}
                        <div className="bg-gray-50 rounded-lg p-6 shadow-md">
                            <h3 className="text-xl font-semibold mb-3">MCP Server</h3>
                            <div className="bg-slate-800 rounded-lg p-3 mb-3">
                                <pre className="text-blue-400 text-sm overflow-x-auto">
                                    <code>{`# Start the MCP server
sec-mcp-server

# In your MCP client config (e.g., Claude):
{
  "mcpServers": {
    "sec-mcp": {
      "command": "python3",
      "args": ["-m", "sec_mcp.start_server"]
    }
  }
}`}</code>
                                </pre>
                            </div>
                            <p className="text-gray-600 text-sm">
                                Run as an MCP server for LLM integrations.
                            </p>
                        </div>
                    </div>

                    {/* Development Setup */}
                    <div className="bg-gray-50 rounded-lg p-6 shadow-md">
                        <h3 className="text-xl font-semibold mb-3">Development Setup</h3>
                        <div className="bg-slate-800 rounded-lg p-4 mb-3">
                            <pre className="text-green-400 overflow-x-auto">
                                <code>{`git clone <repository-url>
cd sec-mcp
pip install -e .`}</code>
                            </pre>
                        </div>
                        <p className="text-gray-600">
                            Clone the repository and install in development mode for contributing to sec-mcp.
                        </p>
                    </div>
                </div>
            </div>
        </section>
    );
};

export default Installation;