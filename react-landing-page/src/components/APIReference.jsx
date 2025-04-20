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

const CodeBlock = ({ children, language = "python", label = null }) => {
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

const APIReference = () => {
    const apiFunctions = [
        {
            name: 'check',
            signature: 'check(value: str) -> CheckResult',
            description: 'Check a single domain, URL, or IP against the blacklist.'
        },
        {
            name: 'check_batch',
            signature: 'check_batch(values: List[str]) -> List[CheckResult]',
            description: 'Batch check of multiple values.'
        },
        {
            name: 'check_ip',
            signature: 'check_ip(ip: str) -> CheckResult',
            description: 'Check if an IP (or network) is blacklisted.'
        },
        {
            name: 'check_domain',
            signature: 'check_domain(domain: str) -> CheckResult',
            description: 'Check if a domain (including parent domains) is blacklisted.'
        },
        {
            name: 'check_url',
            signature: 'check_url(url: str) -> CheckResult',
            description: 'Check if a URL is blacklisted.'
        },
        {
            name: 'get_status',
            signature: 'get_status() -> StatusInfo',
            description: 'Get current status of the blacklist service.'
        },
        {
            name: 'update',
            signature: 'update() -> None',
            description: 'Force an immediate update of all blacklists.'
        },
        {
            name: 'sample',
            signature: 'sample(count: int = 10) -> List[str]',
            description: 'Return a random sample of blacklist entries.'
        }
    ];

    return (
        <section id="api" className="py-16 bg-slate-50">
            <div className="container mx-auto px-4">
                <h2 className="text-3xl font-bold text-center mb-4">API Reference</h2>
                <p className="text-gray-600 text-center mb-12 max-w-3xl mx-auto">
                    sec-mcp provides a comprehensive Python API for integrating security checks into your applications.
                </p>

                <div className="max-w-5xl mx-auto">
                    <div className="overflow-x-auto rounded-lg shadow">
                        <table className="min-w-full bg-white">
                            <thead>
                                <tr className="bg-slate-800 text-white">
                                    <th className="py-4 px-6 text-left">Function Name</th>
                                    <th className="py-4 px-6 text-left">Signature</th>
                                    <th className="py-4 px-6 text-left">Description</th>
                                </tr>
                            </thead>
                            <tbody>
                                {apiFunctions.map((func, index) => (
                                    <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                        <td className="py-3 px-6 border-b border-gray-200">
                                            <code className="font-mono bg-slate-100 px-2 py-0.5 rounded text-purple-600">{func.name}</code>
                                        </td>
                                        <td className="py-3 px-6 border-b border-gray-200">
                                            <code className="font-mono text-sm text-gray-600">{func.signature}</code>
                                        </td>
                                        <td className="py-3 px-6 border-b border-gray-200 text-gray-700">
                                            {func.description}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    <div className="mt-12 bg-white p-6 rounded-lg shadow">
                        <h3 className="text-xl font-bold mb-4">Example API Usage</h3>
                        <div className="bg-slate-900 p-4 rounded-lg border border-slate-700">
                            <CodeBlock>
{`from sec_mcp import SecMCP

# Initialize the client
client = SecMCP()

# Check a single URL
result = client.check("https://example.com")
if result.is_blacklisted:
    print(f"Warning: {result.value} is blacklisted in {result.source}")
else:
    print(f"{result.value} is safe")

# Batch check multiple values
urls = [
    "https://example1.com",
    "https://example2.com",
    "192.168.1.1"
]

results = client.check_batch(urls)
for result in results:
    status = "⚠️ UNSAFE" if result.is_blacklisted else "✅ SAFE"
    print(f"{status}: {result.value}")

# Get current blacklist status
status = client.get_status()
print(f"Total entries: {status.total_entries}")
print(f"Last update: {status.last_update}")`}
                            </CodeBlock>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
};

export default APIReference;