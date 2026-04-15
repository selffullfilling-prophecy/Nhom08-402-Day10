"""
mcp_server.py - Mock MCP server with optional FastAPI HTTP exposure.

This module keeps:
- tool schemas
- tool registry
- dispatch helpers
- FastAPI endpoints

Tool implementations live in `mcp_tools.py`.
"""

import os
import sys

# Ensure project root is available when uvicorn imports this module.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from mcp_tools import (
    tool_check_access_permission,
    tool_create_ticket,
    tool_get_ticket_info,
    tool_search_kb,
)


TOOL_SCHEMAS = {
    "search_kb": {
        "name": "search_kb",
        "description": "Tim kiem Knowledge Base noi bo bang semantic search.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Cau hoi hoac keyword can tim"},
                "top_k": {"type": "integer", "description": "So chunks can tra ve", "default": 3},
            },
            "required": ["query"],
        },
    },
    "get_ticket_info": {
        "name": "get_ticket_info",
        "description": "Tra cuu thong tin ticket tu he thong Jira noi bo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "ID ticket, vi du IT-1234 hoac P1-LATEST"},
            },
            "required": ["ticket_id"],
        },
    },
    "check_access_permission": {
        "name": "check_access_permission",
        "description": "Kiem tra dieu kien cap quyen truy cap theo Access Control SOP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "access_level": {"type": "integer", "description": "Level can cap, 1/2/3"},
                "requester_role": {"type": "string", "description": "Vai tro cua nguoi yeu cau"},
                "is_emergency": {"type": "boolean", "description": "Co phai tinh huong khan cap khong", "default": False},
            },
            "required": ["access_level", "requester_role"],
        },
    },
    "create_ticket": {
        "name": "create_ticket",
        "description": "Tao ticket moi trong he thong Jira (mock).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "priority": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]},
                "title": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["priority", "title"],
        },
    },
}


TOOL_REGISTRY = {
    "search_kb": tool_search_kb,
    "get_ticket_info": tool_get_ticket_info,
    "check_access_permission": tool_check_access_permission,
    "create_ticket": tool_create_ticket,
}


def list_tools() -> list:
    """Return MCP tool schemas."""
    return list(TOOL_SCHEMAS.values())


def dispatch_tool(tool_name: str, tool_input: dict) -> dict:
    """Dispatch a tool by name and always return a dict."""
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Tool '{tool_name}' khong ton tai."}

    try:
        return TOOL_REGISTRY[tool_name](**tool_input)
    except Exception as exc:
        return {"error": f"Tool '{tool_name}' execution failed: {exc}"}


try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    app = FastAPI(title="MCP HTTP Server", description="REST server exposing MCP-like tools")

    @app.get("/tools")
    def api_list_tools():
        return list_tools()

    @app.post("/tools/{tool_name}")
    async def api_dispatch_tool(tool_name: str, request: Request):
        try:
            tool_input = await request.json()
        except Exception:
            tool_input = {}

        result = dispatch_tool(tool_name, tool_input)
        if isinstance(result, dict) and "error" in result:
            return JSONResponse(status_code=400, content=result)
        return result

except ImportError:
    app = None
    print("Warning: FastAPI chua duoc cai dat. Chay: pip install fastapi uvicorn")


if __name__ == "__main__":
    print("Hay chay server bang lenh: uvicorn mcp_server:app --port 8000 --reload")
