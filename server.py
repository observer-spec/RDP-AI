"""
FastAPI + MCP Server for Remote GitHub Actions Runner Control.
Exposes Tools via SSE / HTTP endpoint for AI Agents (Claude Desktop, Cursor, Hermes, etc.).
"""

import os
import subprocess
import shlex
import sys
import platform
import asyncio
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")

app = FastAPI(title="Remote Runner MCP Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_token(authorization: Optional[str] = Header(None)):
    if AUTH_TOKEN:
        if not authorization or authorization.replace("Bearer ", "").strip() != AUTH_TOKEN:
            raise HTTPException(status_code=401, detail="Unauthorized")
    return True

# --- Tool Definitions ---

TOOLS = [
    {
        "name": "execute_command",
        "description": "Execute a shell command on the remote GitHub Actions runner VM.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 60)", "default": 60},
                "cwd": {"type": "string", "description": "Working directory (optional)"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "read_file",
        "description": "Read contents of a file on the runner filesystem.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative file path"},
                "max_lines": {"type": "integer", "description": "Limit number of lines (default 1000)", "default": 1000}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write or overwrite content to a file on the runner VM.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Target file path"},
                "content": {"type": "string", "description": "Text content to write"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "system_info",
        "description": "Get system OS, CPU, RAM, Disk, and runner environment details.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]

# --- API Models ---

class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any] = {}

class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Any] = None
    method: str
    params: Optional[Dict[str, Any]] = None

# --- Tool Implementations ---

def handle_execute_command(args: Dict[str, Any]) -> Dict[str, Any]:
    cmd = args.get("command", "")
    timeout = args.get("timeout", 60)
    cwd = args.get("cwd", None)
    
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd
        )
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {timeout} seconds"}
    except Exception as e:
        return {"error": str(e)}

def handle_read_file(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("path", "")
    max_lines = args.get("max_lines", 1000)
    
    if not os.path.exists(path):
        return {"error": f"File not found: {path}"}
    
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = [f.readline() for _ in range(max_lines)]
        return {"content": "".join(lines), "path": os.path.abspath(path)}
    except Exception as e:
        return {"error": str(e)}

def handle_write_file(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("path", "")
    content = args.get("content", "")
    
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "path": os.path.abspath(path), "bytes_written": len(content)}
    except Exception as e:
        return {"error": str(e)}

def handle_system_info(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "platform": platform.platform(),
        "python_version": sys.version,
        "cpu_count": os.cpu_count(),
        "cwd": os.getcwd(),
        "user": os.getenv("USER") or os.getenv("USERNAME"),
        "github_workflow": os.getenv("GITHUB_WORKFLOW"),
        "github_runner_os": os.getenv("RUNNER_OS")
    }

HANDLERS = {
    "execute_command": handle_execute_command,
    "read_file": handle_read_file,
    "write_file": handle_write_file,
    "system_info": handle_system_info
}

# --- Routes ---

@app.get("/")
def index():
    return {
        "status": "online",
        "service": "GitHub Actions MCP Remote Server",
        "tools_count": len(TOOLS)
    }

@app.get("/tools", dependencies=[Depends(verify_token)])
def list_tools():
    return {"tools": TOOLS}

@app.post("/call", dependencies=[Depends(verify_token)])
def call_tool(req: ToolCallRequest):
    handler = HANDLERS.get(req.name)
    if not handler:
        raise HTTPException(status_code=404, detail=f"Tool '{req.name}' not found")
    result = handler(req.arguments)
    return {"result": result}

# MCP JSON-RPC 2.0 endpoint
@app.post("/mcp", dependencies=[Depends(verify_token)])
async def mcp_rpc(req: JsonRpcRequest):
    if req.method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {"tools": TOOLS}
        }
    elif req.method == "tools/call":
        params = req.params or {}
        tool_name = params.get("name")
        args = params.get("arguments", {})
        handler = HANDLERS.get(tool_name)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": req.id,
                "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"}
            }
        result = handler(args)
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {
                "content": [{"type": "text", "text": str(result)}]
            }
        }
    elif req.method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "github-actions-mcp-runner", "version": "1.0.0"}
            }
        }
    else:
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {}
        }

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
