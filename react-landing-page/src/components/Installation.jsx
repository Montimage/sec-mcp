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

const Installation = () => {
    return (
        <section id="installation" className="py-16 bg-gray-50">
            <div className="container mx-auto px-4">
                <h2 className="text-3xl font-bold text-center mb-4">Installation Guide</h2>
                <p className="text-gray-600 text-center mb-12 max-w-3xl mx-auto">
                    Follow these simple steps to install and configure sec-mcp for your environment.
                </p>

                <div className="max-w-4xl mx-auto">
                    <div className="bg-white rounded-lg shadow-lg overflow-hidden mb-8">
                        <div className="bg-blue-600 text-white py-3 px-6">
                            <h3 className="text-xl font-semibold">Basic Installation</h3>
                        </div>
                        <div className="p-6">
                            <div className="mb-6">
                                <h4 className="text-lg font-medium mb-2">1. Create a virtual environment (recommended)</h4>
                                <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
                                    <CodeBlock>
{`# Python 3.10+ is required
python3.12 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate`}
                                    </CodeBlock>
                                </div>
                            </div>

                            <div className="mb-6">
                                <h4 className="text-lg font-medium mb-2">2. Install the package</h4>
                                <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
                                    <CodeBlock>
{`pip install sec-mcp

# Verify installation
sec-mcp --version`}
                                    </CodeBlock>
                                </div>
                            </div>

                            <div className="mb-6">
                                <h4 className="text-lg font-medium mb-2">3. Initialize and update the database</h4>
                                <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
                                    <CodeBlock>
{`# This will download and process blacklists
sec-mcp update

# Check status
sec-mcp status`}
                                    </CodeBlock>
                                </div>
                                <p className="text-gray-500 text-sm mt-2">Initial download may take a few minutes. The database will update automatically every 12 hours by default.</p>
                            </div>

                            <div>
                                <h4 className="text-lg font-medium mb-2">4. Test the installation</h4>
                                <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
                                    <CodeBlock>
{`# Check a domain
sec-mcp check example.com

# Check an IP address
sec-mcp check 8.8.8.8`}
                                    </CodeBlock>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="bg-white rounded-lg shadow-lg overflow-hidden">
                        <div className="bg-blue-600 text-white py-3 px-6">
                            <h3 className="text-xl font-semibold">Python API Integration</h3>
                        </div>
                        <div className="p-6">
                            <div className="mb-6">
                                <h4 className="text-lg font-medium mb-2">Import and initialize</h4>
                                <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
                                    <CodeBlock language="python" label="PYTHON">
{`from sec_mcp import SecMCP

# Initialize the client
client = SecMCP()

# Optional: Custom configuration
client = SecMCP(
    db_path="/path/to/custom/database.db",
    update_interval=24,  # hours
    log_level="INFO"
)`}
                                    </CodeBlock>
                                </div>
                            </div>

                            <div>
                                <h4 className="text-lg font-medium mb-2">Basic usage examples</h4>
                                <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
                                    <CodeBlock language="python" label="PYTHON">
{`# Check a URL
result = client.check("https://example.com/path")
print(f"Is blacklisted: {result.is_blacklisted}")
print(f"Match found in: {result.source if result.is_blacklisted else 'None'}")

# Check multiple values
results = client.check_batch([
    "example.com",
    "192.168.1.1",
    "https://suspicious-site.com/path"
])

# Process results
for result in results:
    if result.is_blacklisted:
        print(f"⚠️ {result.value} is blacklisted in {result.source}")
    else:
        print(f"✅ {result.value} is not blacklisted")`}
                                    </CodeBlock>
                                </div>
                                <p className="text-gray-500 text-sm mt-2">See the <a href="#api" className="text-blue-600 hover:underline">API Reference</a> for more advanced usage examples.</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
};

export default Installation;