"""
FastAPI + MCP Server for Remote GitHub Actions Runner Control.
Exposes Tools via SSE / HTTP endpoint with persistent state syncing.
"""

import os
import subprocess
import sys
import platform
import asyncio
import json
import time
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", os.path.join(os.getcwd(), "workspace"))
STATE_FILE = os.path.join(WORKSPACE_DIR, "agent_memory.json")
HISTORY_FILE = os.path.join(WORKSPACE_DIR, "command_history.log")

os.makedirs(WORKSPACE_DIR, exist_ok=True)

app = FastAPI(title="Persistent Remote Runner MCP Agent", version="1.1.0")

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

# --- Persistent Memory Helpers ---

def load_memory() -> Dict[str, Any]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_memory(data: Dict[str, Any]):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def log_history(entry: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {entry}\n")

# --- Tool Definitions ---

TOOLS = [
    {
        "name": "execute_command",
        "description": "Execute a shell command on the runner. Working directory defaults to workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 120)", "default": 120},
                "cwd": {"type": "string", "description": "Working directory (defaults to persistent workspace)", "default": WORKSPACE_DIR}
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
                "path": {"type": "string", "description": "File path (relative to workspace or absolute)"},
                "max_lines": {"type": "integer", "description": "Limit number of lines (default 1000)", "default": 1000}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write or overwrite content to a file in the persistent workspace.",
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
        "name": "memory_store",
        "description": "Store key-value knowledge or notes that persist across runner restarts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Memory key name"},
                "value": {"type": "string", "description": "Content / memory text to store"}
            },
            "required": ["key", "value"]
        }
    },
    {
        "name": "memory_recall",
        "description": "Recall stored memories and persistent state.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Optional key name. Omit to retrieve all memory entries."}
            }
        }
    },
    {
        "name": "system_info",
        "description": "Get runner OS, memory, disk, and persistent storage stats.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]

# --- Tool Handlers ---

def handle_execute_command(args: Dict[str, Any]) -> Dict[str, Any]:
    cmd = args.get("command", "")
    timeout = args.get("timeout", 120)
    cwd = args.get("cwd", WORKSPACE_DIR)
    
    log_history(f"CMD: {cmd} (cwd: {cwd})")
    
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
            "exit_code": proc.returncode,
            "cwd": os.path.abspath(cwd)
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {timeout} seconds"}
    except Exception as e:
        return {"error": str(e)}

def handle_read_file(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("path", "")
    max_lines = args.get("max_lines", 1000)
    
    target_path = path if os.path.isabs(path) else os.path.join(WORKSPACE_DIR, path)
    
    if not os.path.exists(target_path):
        return {"error": f"File not found: {target_path}"}
    
    try:
        with open(target_path, "r", encoding="utf-8", errors="replace") as f:
            lines = [f.readline() for _ in range(max_lines)]
        return {"content": "".join(lines), "path": os.path.abspath(target_path)}
    except Exception as e:
        return {"error": str(e)}

def handle_write_file(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("path", "")
    content = args.get("content", "")
    
    target_path = path if os.path.isabs(path) else os.path.join(WORKSPACE_DIR, path)
    
    try:
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
        log_history(f"WRITE_FILE: {target_path} ({len(content)} bytes)")
        return {"success": True, "path": os.path.abspath(target_path), "bytes_written": len(content)}
    except Exception as e:
        return {"error": str(e)}

def handle_memory_store(args: Dict[str, Any]) -> Dict[str, Any]:
    key = args.get("key", "").strip()
    value = args.get("value", "")
    
    mem = load_memory()
    mem[key] = {
        "value": value,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    save_memory(mem)
    log_history(f"MEMORY_STORE: key='{key}'")
    return {"success": True, "key": key, "total_keys": len(mem)}

def handle_memory_recall(args: Dict[str, Any]) -> Dict[str, Any]:
    key = args.get("key", None)
    mem = load_memory()
    if key:
        return {"key": key, "entry": mem.get(key, None)}
    return {"all_memories": mem, "total_keys": len(mem)}

def handle_system_info(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "platform": platform.platform(),
        "python_version": sys.version,
        "cpu_count": os.cpu_count(),
        "workspace_dir": WORKSPACE_DIR,
        "workspace_files": os.listdir(WORKSPACE_DIR) if os.path.exists(WORKSPACE_DIR) else [],
        "memories_count": len(load_memory()),
        "user": os.getenv("USER") or os.getenv("USERNAME"),
        "github_workflow": os.getenv("GITHUB_WORKFLOW"),
        "github_runner_os": os.getenv("RUNNER_OS")
    }

HANDLERS = {
    "execute_command": handle_execute_command,
    "read_file": handle_read_file,
    "write_file": handle_write_file,
    "memory_store": handle_memory_store,
    "memory_recall": handle_memory_recall,
    "system_info": handle_system_info
}

# --- Routes ---

class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any] = {}

class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Any] = None
    method: str
    params: Optional[Dict[str, Any]] = None

@app.get("/")
def index():
    return {
        "status": "online",
        "service": "Persistent GitHub Actions MCP Remote Server",
        "tools_count": len(TOOLS),
        "workspace": WORKSPACE_DIR
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
                "serverInfo": {"name": "persistent-github-mcp-runner", "version": "1.1.0"}
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
