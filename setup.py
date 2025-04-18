from setuptools import setup, find_packages

setup(
    name="mcp-client",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests",
        "click",
        "tqdm",
        "idna",
        "mcp[cli]",
        "httpx",
        "schedule",
    ],
    entry_points={
        "console_scripts": [
            "mcp=mcp_client.interface:cli",
        ],
    },
    python_requires=">=3.11",
    author="Luong NGUYEN",
    description="Model Context Protocol (MCP) Client for checking domains, URLs, and IPs against blacklists",
    package_data={
        "mcp_client": ["config.json"],
    },
)
