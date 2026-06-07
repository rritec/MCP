from mcp.server.fastmcp import FastMCP

mcp = FastMCP("my-first-server")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Adds two numbers and returns the result."""
    return a + b

@mcp.tool()
def greet(name: str) -> str:
    """Returns a greeting message for the given name."""
    return f"Hello, {name}! Welcome to MCP."

if __name__ == "__main__":
    mcp.run(transport="stdio")