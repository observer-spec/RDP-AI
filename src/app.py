"""FastAPI app + routes (extracted from server.py)."""
import json
import os
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import AUTH_TOKEN
from .handlers_browser import handle_browser_interact, handle_browser_open, handle_take_screenshot
from .handlers_files import (
    handle_download_file,
    handle_execute_command,
    handle_http_request,
    handle_python_eval,
    handle_read_file,
    handle_search_files,
    handle_write_file,
)
from .handlers_sys import handle_memory_recall, handle_memory_store, handle_process_manager, handle_system_info, handle_tmux_session
from .tools import TOOLS

app = FastAPI(title="Persistent Linux MCP Cloud Runner with Web Desktop", version="3.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

NOVNC_DIR = "/usr/share/novnc"
if os.path.exists(NOVNC_DIR):
    app.mount("/novnc", StaticFiles(directory=NOVNC_DIR, html=True), name="novnc")


def verify_token(authorization: Optional[str] = Header(None)):
    if AUTH_TOKEN:
        if not authorization or authorization.replace("Bearer ", "").strip() != AUTH_TOKEN:
            raise HTTPException(status_code=401, detail="Unauthorized")
    return True


@app.get("/health")
def health():
    """Unauthenticated liveness probe for workflow health checks."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index_web_gui():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>RDP-AI Cloud Linux Desktop</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0d1117; color: #c9d1d9; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
    header { background: #161b22; border-bottom: 1px solid #30363d; padding: 10px 18px; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
    .title-group { display: flex; align-items: center; gap: 12px; }
    .badge-online { background: #238636; color: #fff; font-size: 11px; padding: 3px 8px; border-radius: 12px; font-weight: bold; }
    .badge-linux { background: #1f6feb; color: #fff; font-size: 11px; padding: 3px 8px; border-radius: 12px; }
    .btn-bar { display: flex; gap: 8px; }
    .btn { background: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 500; text-decoration: none; transition: 0.2s; }
    .btn:hover { background: #30363d; color: #fff; }
    .btn.primary { background: #238636; border-color: #2ea043; color: #fff; }
    .btn.primary:hover { background: #2ea043; }
    iframe { flex: 1; border: none; width: 100%; height: 100%; background: #000; }
  </style>
</head>
<body>
  <header>
    <div class="title-group">
      <h2 style="font-size: 15px; color: #f0f6fc; font-weight: 600;">☁️ RDP-AI Linux Cloud VM</h2>
      <span class="badge-online">ONLINE</span>
      <span class="badge-linux">Ubuntu 24.04 (4-Core AMD / 16GB)</span>
    </div>
    <div class="btn-bar">
      <button class="btn" onclick="toggleFullscreen()">⛶ Fullscreen</button>
      <a class="btn" href="/tools" target="_blank">🛠️ MCP Tools</a>
      <a class="btn primary" href="/mcp" target="_blank">⚡ MCP Endpoint</a>
    </div>
  </header>
  <iframe src="/novnc/vnc.html?autoconnect=true&resize=scale&reconnect=true"></iframe>
  <script>
    function toggleFullscreen() {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
      } else {
        document.exitFullscreen();
      }
    }
  </script>
</body>
</html>"""


HANDLERS = {
    "take_screenshot": handle_take_screenshot,
    "browser_open": handle_browser_open,
    "browser_interact": handle_browser_interact,
    "execute_command": handle_execute_command,
    "python_eval": handle_python_eval,
    "read_file": handle_read_file,
    "write_file": handle_write_file,
    "search_files": handle_search_files,
    "download_file": handle_download_file,
    "http_request": handle_http_request,
    "memory_store": handle_memory_store,
    "memory_recall": handle_memory_recall,
    "process_manager": handle_process_manager,
    "system_info": handle_system_info,
    "tmux_session": handle_tmux_session,
}


class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any] = {}


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Any] = None
    method: str
    params: Optional[Dict[str, Any]] = None


@app.get("/tools", dependencies=[Depends(verify_token)])
def list_tools():
    return {"tools": TOOLS}


@app.post("/call", dependencies=[Depends(verify_token)])
async def call_tool(req: ToolCallRequest):
    handler = HANDLERS.get(req.name)
    if not handler:
        raise HTTPException(status_code=404, detail=f"Tool '{req.name}' not found")
    result = await handler(req.arguments)
    return {"result": result}


@app.post("/mcp", dependencies=[Depends(verify_token)])
async def mcp_rpc(req: JsonRpcRequest):
    if req.method == "tools/list":
        return {"jsonrpc": "2.0", "id": req.id, "result": {"tools": TOOLS}}
    elif req.method == "tools/call":
        params = req.params or {}
        tool_name = params.get("name")
        args = params.get("arguments", {})
        handler = HANDLERS.get(tool_name)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": req.id,
                "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"},
            }
        result = await handler(args)
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]},
        }
    elif req.method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "persistent-super-utility-mcp-runner", "version": "3.2.0"},
            },
        }
    else:
        return {"jsonrpc": "2.0", "id": req.id, "result": {}}
