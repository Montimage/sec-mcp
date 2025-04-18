#!/usr/bin/env python3
"""Example MCP client that demonstrates how to interact with the blacklist checking server."""

from mcp.client import Client
import asyncio

async def main():
    # Create an MCP client
    client = Client()
    
    # Connect to our blacklist checking server
    await client.connect_stdio("../start_server.py")
    
    # Example URLs to check
    urls_to_check = [
        "https://example.com",
        "https://known-malicious-site.com",
        "https://phishing-attempt.net"
    ]
    
    # Check each URL using the check_blacklist tool
    for url in urls_to_check:
        print(f"\nChecking URL: {url}")
        try:
            result = await client.invoke_tool(
                "check_blacklist",
                {"value": url}
            )
            print(f"Result: {'Safe' if result['is_safe'] else 'Unsafe'}")
            print(f"Explanation: {result['explain']}")
        except Exception as e:
            print(f"Error checking {url}: {str(e)}")

    # Close the client connection
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
