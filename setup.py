from setuptools import setup, find_packages

setup(
    name="sec-mcp",
    version="0.2.4",
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
            "sec-mcp=sec_mcp.interface:cli",
        ],
    },
    python_requires=">=3.11",
    author="Luong NGUYEN",
    description="Model Context Protocol (MCP) Client for checking domains, URLs, and IPs against blacklists",
    package_data={
        "sec_mcp": ["config.json"],
    },
)
