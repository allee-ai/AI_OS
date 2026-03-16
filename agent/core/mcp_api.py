"""
MCP (Model Context Protocol) API - Scaffold
============================================
Manages MCP server connections and tool discovery.
Servers are stored as JSON in the MCP_SERVERS env var / .env file.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import os

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


class MCPServer(BaseModel):
    name: str
    command: str  # e.g. "npx", "uvx", "python"
    args: List[str] = []  # e.g. ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    env: Dict[str, str] = {}  # extra env vars for the process
    enabled: bool = True


class MCPServerCreate(BaseModel):
    name: str
    command: str
    args: List[str] = []
    env: Dict[str, str] = {}
    enabled: bool = True


# ── Helpers ──

def _load_servers() -> List[dict]:
    raw = os.environ.get("MCP_SERVERS", "[]")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def _save_servers(servers: List[dict]):
    """Persist server list to env + .env file."""
    val = json.dumps(servers)
    os.environ["MCP_SERVERS"] = val
    # Write to .env via the settings API helper
    from agent.core.settings_api import _write_env
    _write_env({"MCP_SERVERS": val})


# ── Endpoints ──

@router.get("/servers")
async def list_servers():
    """List all configured MCP servers."""
    return {"servers": _load_servers()}


@router.post("/servers")
async def add_server(server: MCPServerCreate):
    """Add a new MCP server configuration."""
    servers = _load_servers()
    if any(s["name"] == server.name for s in servers):
        raise HTTPException(status_code=400, detail=f"Server already exists: {server.name}")
    servers.append(server.model_dump())
    _save_servers(servers)
    return {"status": "added", "name": server.name, "total": len(servers)}


@router.delete("/servers/{name}")
async def remove_server(name: str):
    """Remove an MCP server by name."""
    servers = _load_servers()
    updated = [s for s in servers if s["name"] != name]
    if len(updated) == len(servers):
        raise HTTPException(status_code=404, detail=f"Server not found: {name}")
    _save_servers(updated)
    return {"status": "removed", "name": name, "total": len(updated)}


@router.put("/servers/{name}")
async def update_server(name: str, server: MCPServerCreate):
    """Update an existing MCP server configuration."""
    servers = _load_servers()
    for i, s in enumerate(servers):
        if s["name"] == name:
            servers[i] = server.model_dump()
            _save_servers(servers)
            return {"status": "updated", "name": server.name}
    raise HTTPException(status_code=404, detail=f"Server not found: {name}")


@router.post("/servers/{name}/toggle")
async def toggle_server(name: str):
    """Enable/disable an MCP server."""
    servers = _load_servers()
    for s in servers:
        if s["name"] == name:
            s["enabled"] = not s.get("enabled", True)
            _save_servers(servers)
            return {"status": "toggled", "name": name, "enabled": s["enabled"]}
    raise HTTPException(status_code=404, detail=f"Server not found: {name}")


# ── Popular MCP servers catalog (for quick-add UI) ──

MCP_CATALOG = [
    {
        "name": "filesystem",
        "description": "Read/write files, search directories",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        "category": "files",
    },
    {
        "name": "brave-search",
        "description": "Web search via Brave Search API",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env_required": ["BRAVE_API_KEY"],
        "category": "search",
    },
    {
        "name": "github",
        "description": "GitHub repos, issues, PRs, file content",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env_required": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
        "category": "dev",
    },
    {
        "name": "memory",
        "description": "Persistent memory via knowledge graph",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "category": "memory",
    },
    {
        "name": "puppeteer",
        "description": "Browser automation and web scraping",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
        "category": "browser",
    },
    {
        "name": "sqlite",
        "description": "Query SQLite databases",
        "command": "uvx",
        "args": ["mcp-server-sqlite", "--db-path", "data/db/personal.db"],
        "category": "data",
    },
    {
        "name": "fetch",
        "description": "Fetch web pages and convert to markdown",
        "command": "uvx",
        "args": ["mcp-server-fetch"],
        "category": "search",
    },
]


@router.get("/catalog")
async def get_mcp_catalog():
    """Return catalog of popular MCP servers for quick installation."""
    installed = {s["name"] for s in _load_servers()}
    catalog = []
    for item in MCP_CATALOG:
        catalog.append({**item, "installed": item["name"] in installed})
    return {"servers": catalog}


# ── Connection lifecycle & tool discovery ──

@router.post("/servers/{name}/connect")
async def connect_server(name: str):
    """Spawn an MCP server process, discover tools, register in Form thread."""
    from agent.core.mcp_client import connect, is_connected

    servers = _load_servers()
    server_cfg = next((s for s in servers if s["name"] == name), None)
    if not server_cfg:
        raise HTTPException(status_code=404, detail=f"Server not found: {name}")
    if not server_cfg.get("enabled", True):
        raise HTTPException(status_code=400, detail=f"Server is disabled: {name}")
    if is_connected(name):
        # Already connected — just return current tools
        from agent.core.mcp_client import get_connection
        conn = get_connection(name)
        return {
            "status": "already_connected",
            "name": name,
            "tools": [{"name": t.name, "description": t.description} for t in conn.tools],
        }

    try:
        conn = connect(server_cfg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect: {e}")

    # Register discovered tools in Form thread DB
    registered = _register_mcp_tools(name, conn.tools)

    return {
        "status": "connected",
        "name": name,
        "server_info": conn.server_info,
        "tools_discovered": len(conn.tools),
        "tools_registered": registered,
        "tools": [{"name": t.name, "description": t.description} for t in conn.tools],
    }


@router.post("/servers/{name}/disconnect")
async def disconnect_server(name: str):
    """Shut down an MCP server and remove its tools from Form thread."""
    from agent.core.mcp_client import disconnect as mcp_disconnect

    success = mcp_disconnect(name)
    removed = _unregister_mcp_tools(name)

    return {
        "status": "disconnected" if success else "not_connected",
        "name": name,
        "tools_removed": removed,
    }


@router.get("/servers/{name}/tools")
async def get_server_tools(name: str):
    """List tools discovered from a connected MCP server."""
    from agent.core.mcp_client import get_connection, is_connected

    if not is_connected(name):
        return {"name": name, "connected": False, "tools": []}

    conn = get_connection(name)
    return {
        "name": name,
        "connected": True,
        "tools": [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in conn.tools
        ],
    }


@router.get("/connections")
async def list_connections():
    """List all active MCP connections."""
    from agent.core.mcp_client import list_connections as mcp_list
    return {"connections": mcp_list()}


@router.post("/tools/call")
async def call_mcp_tool(request: dict):
    """Call a tool on a connected MCP server."""
    from agent.core.mcp_client import call_tool

    server = request.get("server")
    tool = request.get("tool")
    arguments = request.get("arguments", {})

    if not server or not tool:
        raise HTTPException(status_code=400, detail="'server' and 'tool' are required")

    result = call_tool(server, tool, arguments)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# ── Form thread registration helpers ──

def _mcp_tool_db_name(server_name: str, tool_name: str) -> str:
    """Generate a unique Form DB name for an MCP tool: mcp_<server>_<tool>."""
    return f"mcp_{server_name}_{tool_name}".replace("-", "_")


def _register_mcp_tools(server_name: str, tools) -> int:
    """Register MCP-discovered tools into the Form thread DB."""
    from agent.threads.form.schema import add_tool, get_tool, update_tool

    count = 0
    for t in tools:
        db_name = _mcp_tool_db_name(server_name, t.name)
        # Build actions from input_schema properties
        props = t.input_schema.get("properties", {})
        actions = list(props.keys())[:10] if props else ["call"]

        existing = get_tool(db_name)
        if existing:
            update_tool(
                name=db_name,
                description=f"[MCP:{server_name}] {t.description}",
                actions=actions,
                enabled=True,
            )
        else:
            add_tool(
                name=db_name,
                description=f"[MCP:{server_name}] {t.description}",
                category="mcp",
                actions=actions,
                run_file=None,
                run_type="mcp",
                weight=0.4,
                enabled=True,
                allowed=True,
            )
        count += 1
    return count


def _unregister_mcp_tools(server_name: str) -> int:
    """Remove MCP tools for a server from the Form thread DB."""
    from agent.threads.form.schema import get_tools, delete_tool

    prefix = f"mcp_{server_name}_".replace("-", "_")
    count = 0
    for tool in get_tools():
        if tool["name"].startswith(prefix):
            delete_tool(tool["name"])
            count += 1
    return count
