"""
MCP Client Runtime
==================
Spawns MCP server processes (stdio transport), performs JSON-RPC 2.0
handshake, discovers tools, and executes tool calls.

Lifecycle:
    1. connect(server_config)  → spawns process, sends initialize, tools/list
    2. call_tool(name, args)   → sends tools/call, returns result
    3. disconnect()            → sends shutdown, kills process

Tools discovered via tools/list are registered in the Form thread DB
as category="mcp" with source tracking so calls route back through here.
"""

import asyncio
import json
import subprocess
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

# JSON-RPC message ID counter
_next_id = 0


def _make_id() -> int:
    global _next_id
    _next_id += 1
    return _next_id


@dataclass
class MCPTool:
    """A tool discovered from an MCP server."""
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    server_name: str = ""


@dataclass
class MCPConnection:
    """A live connection to an MCP server process."""
    name: str
    process: subprocess.Popen
    tools: List[MCPTool] = field(default_factory=list)
    server_info: Dict[str, Any] = field(default_factory=dict)


# Active connections keyed by server name
_connections: Dict[str, MCPConnection] = {}


def _send_jsonrpc(proc: subprocess.Popen, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """Send a JSON-RPC 2.0 request over stdin and read the response from stdout."""
    msg_id = _make_id()
    request = {
        "jsonrpc": "2.0",
        "id": msg_id,
        "method": method,
    }
    if params is not None:
        request["params"] = params

    payload = json.dumps(request)
    # MCP stdio transport: Content-Length header + \r\n\r\n + body
    header = f"Content-Length: {len(payload)}\r\n\r\n"
    proc.stdin.write(header + payload)
    proc.stdin.flush()

    # Read response — Content-Length header then body
    response_header = ""
    while True:
        ch = proc.stdout.read(1)
        if not ch:
            raise ConnectionError("MCP server closed stdout")
        response_header += ch
        if response_header.endswith("\r\n\r\n"):
            break

    # Parse Content-Length
    content_length = 0
    for line in response_header.strip().split("\r\n"):
        if line.lower().startswith("content-length:"):
            content_length = int(line.split(":", 1)[1].strip())
            break

    if content_length == 0:
        raise ConnectionError("No Content-Length in MCP response header")

    body = proc.stdout.read(content_length)
    return json.loads(body)


def connect(server_config: Dict[str, Any]) -> MCPConnection:
    """
    Spawn an MCP server process and perform handshake.

    server_config = {
        "name": "filesystem",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        "env": {}
    }

    Returns MCPConnection with discovered tools.
    """
    name = server_config["name"]

    # Don't double-connect
    if name in _connections:
        return _connections[name]

    # Build env
    env = {**os.environ, **server_config.get("env", {})}

    command = server_config["command"]
    args = server_config.get("args", [])

    proc = subprocess.Popen(
        [command, *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=str(Path.cwd()),
    )

    conn = MCPConnection(name=name, process=proc)

    try:
        # Step 1: initialize
        init_resp = _send_jsonrpc(proc, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "aios", "version": "1.0.0"},
        })

        conn.server_info = init_resp.get("result", {}).get("serverInfo", {})

        # Step 2: initialized notification (no id)
        notif = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
        header = f"Content-Length: {len(notif)}\r\n\r\n"
        proc.stdin.write(header + notif)
        proc.stdin.flush()

        # Step 3: tools/list
        tools_resp = _send_jsonrpc(proc, "tools/list", {})
        raw_tools = tools_resp.get("result", {}).get("tools", [])

        conn.tools = [
            MCPTool(
                name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
                server_name=name,
            )
            for t in raw_tools
        ]

        _connections[name] = conn
        return conn

    except Exception:
        proc.kill()
        raise


def disconnect(name: str) -> bool:
    """Shut down an MCP server process."""
    conn = _connections.pop(name, None)
    if conn is None:
        return False

    try:
        # Send shutdown
        _send_jsonrpc(conn.process, "shutdown", {})
    except Exception:
        pass

    try:
        conn.process.kill()
        conn.process.wait(timeout=5)
    except Exception:
        pass

    return True


def call_tool(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call a tool on a connected MCP server.

    Returns the raw result dict from the server.
    """
    conn = _connections.get(server_name)
    if conn is None:
        return {"error": f"MCP server '{server_name}' not connected"}

    try:
        resp = _send_jsonrpc(conn.process, "tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })

        if "error" in resp:
            return {"error": resp["error"].get("message", str(resp["error"]))}

        result = resp.get("result", {})
        # MCP tool results have content[] array
        content_parts = result.get("content", [])
        texts = [c.get("text", "") for c in content_parts if c.get("type") == "text"]
        return {
            "output": "\n".join(texts) if texts else str(result),
            "isError": result.get("isError", False),
        }
    except Exception as e:
        return {"error": f"Tool call failed: {e}"}


def list_connections() -> List[Dict[str, Any]]:
    """List all active MCP connections and their tools."""
    result = []
    for name, conn in _connections.items():
        result.append({
            "name": name,
            "server_info": conn.server_info,
            "tools": [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in conn.tools
            ],
            "alive": conn.process.poll() is None,
        })
    return result


def get_connection(name: str) -> Optional[MCPConnection]:
    """Get a specific connection by server name."""
    return _connections.get(name)


def is_connected(name: str) -> bool:
    """Check if a server is connected and alive."""
    conn = _connections.get(name)
    return conn is not None and conn.process.poll() is None
