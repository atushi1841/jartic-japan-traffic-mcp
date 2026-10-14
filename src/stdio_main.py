"""stdio entry point for JARTIC MCP server."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from server import mcp

if __name__ == "__main__":
    mcp.run()
