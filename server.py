"""
Persistent Super-Utility MCP Remote Server v3.0 (Linux Edition with Web GUI Desktop)
Includes:
- Full Web-based Interactive Desktop GUI (noVNC embedded at base URL /)
- WebSocket-to-TCP VNC Proxy on port 8000
- 14+ MCP Tools (Playwright Browser, Shell, Python eval, File/Search, Memory, System)
- Persistent Workspace State & GitHub Cache Sync
"""

import os
import sys
import subprocess
import platform
import asyncio
import json
import time
import base64
import urllib.request
import re
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Header, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", os.path.join(os.getcwd(), "workspace"))
STATE_FILE = os.path.join(WORKSPACE_DIR, "agent_memory.json")
HISTORY_FILE = os.path.join(WORKSPACE_DIR, "command_history.log")

os.makedirs(WORKSPACE_DIR, exist_ok=True)

app = FastAPI(title="Persistent Linux MCP Cloud Runner with Web Desktop", version="3.0.0")

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

# --- Memory & History Helpers ---

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

# --- Playwright Browser State ---

browser_instance = None
browser_page = None
playwright_obj = None

async def get_browser_page():
    global browser_instance, browser_page, playwright_obj
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None, "Playwright is not installed"
    
    if browser_page is None or browser_page.is_closed():
        if playwright_obj is None:
            playwright_obj = await async_playwright().start()
        browser_instance = await playwright_obj.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        context = await browser_instance.new_context(viewport={"width": 1920, "height": 1080})
        browser_page = await context.new_page()
    
    return browser_page, None

# --- Web Desktop WebSocket Proxy (noVNC <-> x11vnc on 5900) ---

@app.websocket("/websockify")
async def websocket_vnc_bridge(websocket: WebSocket):
    await websocket.accept(subprotocols=["binary"])
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", 5900)
    except Exception as e:
        await websocket.close(code=1011, reason=f"VNC server connection failed: {str(e)}")
        return

    async def ws_to_tcp():
        try:
            while True:
                data = await websocket.receive_bytes()
                writer.write(data)
                await writer.drain()
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception:
            pass
        finally:
            writer.close()

    async def tcp_to_ws():
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                await websocket.send_bytes(data)
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception:
            pass
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    try:
        await asyncio.gather(ws_to_tcp(), tcp_to_ws())
    except Exception:
        pass

# --- Base URL Web Dashboard & Embedded noVNC GUI ---

@app.get("/", response_class=HTMLResponse)
def index_web_gui():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>RDP-AI Cloud Linux Runner</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <script src="https://cdn.jsdelivr.net/npm/@novnc/novnc@1.5.0/core/rfb.js" type="module"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; background: #0d1117; color: #c9d1d9; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
    header { background: #161b22; border-bottom: 1px solid #30363d; padding: 10px 18px; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
    .title-group { display: flex; align-items: center; gap: 12px; }
    .badge-online { background: #238636; color: #fff; font-size: 11px; padding: 3px 8px; border-radius: 12px; font-weight: bold; }
    .badge-linux { background: #1f6feb; color: #fff; font-size: 11px; padding: 3px 8px; border-radius: 12px; }
    .btn-bar { display: flex; gap: 8px; }
    .btn { background: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 500; text-decoration: none; transition: 0.2s; }
    .btn:hover { background: #30363d; color: #fff; }
    .btn.primary { background: #238636; border-color: #2ea043; color: #fff; }
    .btn.primary:hover { background: #2ea043; }
    #screen-container { flex: 1; position: relative; background: #000; display: flex; align-items: center; justify-content: center; overflow: hidden; }
    #noVNC_canvas { width: 100%; height: 100%; object-fit: contain; }
    #status-overlay { position: absolute; color: #8b949e; font-size: 14px; pointer-events: none; background: rgba(13,17,23,0.85); padding: 12px 20px; border-radius: 8px; border: 1px solid #30363d; }
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
      <button class="btn" onclick="rfb.sendCtrlAltDel()">Ctrl+Alt+Del</button>
      <button class="btn" onclick="toggleFullscreen()">⛶ Fullscreen</button>
      <a class="btn" href="/tools" target="_blank">🛠️ MCP Tools</a>
      <a class="btn primary" href="/mcp" target="_blank">⚡ MCP Endpoint</a>
    </div>
  </header>

  <div id="screen-container">
    <div id="status-overlay">Connecting to interactive display...</div>
  </div>

  <script type="module">
    import RFB from 'https://cdn.jsdelivr.net/npm/@novnc/novnc@1.5.0/core/rfb.js';

    const wsScheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsScheme}//${window.location.host}/websockify`;
    const container = document.getElementById('screen-container');
    const statusOverlay = document.getElementById('status-overlay');

    window.rfb = new RFB(container, wsUrl, {
      credentials: { password: '' },
      wsProtocols: ['binary']
    });

    rfb.scaleViewport = true;
    rfb.resizeSession = false;

    rfb.addEventListener('connect', () => {
      statusOverlay.style.display = 'none';
      console.log('Connected to VNC Desktop!');
    });

    rfb.addEventListener('disconnect', (e) => {
      statusOverlay.style.display = 'block';
      statusOverlay.innerText = 'Disconnected from display. Reconnecting in 3s...';
      setTimeout(() => location.reload(), 3000);
    });

    window.toggleFullscreen = function() {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
      } else {
        document.exitFullscreen();
      }
    };
  </script>
</body>
</html>"""

# --- Tool Definitions ---

TOOLS = [
    {
        "name": "take_screenshot",
        "description": "Capture a screenshot of either the active browser page or the virtual desktop display (X11). Returns base64 image data.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "enum": ["browser", "desktop"], "default": "desktop", "description": "Whether to capture active web page or X11 desktop display"},
                "full_page": {"type": "boolean", "default": False, "description": "If browser, capture full scrollable page"}
            }
        }
    },
    {
        "name": "browser_open",
        "description": "Navigate real Chromium browser to a URL. Returns page title, text content, and high-res screenshot.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Web URL to open"},
                "wait_until": {"type": "string", "enum": ["load", "domcontentloaded", "networkidle"], "default": "domcontentloaded"},
                "capture_screenshot": {"type": "boolean", "default": True}
            },
            "required": ["url"]
        }
    },
    {
        "name": "browser_interact",
        "description": "Perform actions in the active browser: click, type, evaluate JavaScript, scroll, or extract HTML.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["click", "type", "evaluate_js", "screenshot", "get_html", "scroll"]},
                "selector": {"type": "string", "description": "CSS selector or text for click/type"},
                "text": {"type": "string", "description": "Text to type"},
                "script": {"type": "string", "description": "JavaScript code to evaluate"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "execute_command",
        "description": "Execute any bash or shell command on the runner VM.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 120)", "default": 120},
                "cwd": {"type": "string", "description": "Working directory (defaults to workspace)"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "python_eval",
        "description": "Execute Python code directly inside the server runtime and capture stdout/errors.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python source code to execute"}
            },
            "required": ["code"]
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
        "description": "Write or overwrite content to a file in the workspace.",
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
        "name": "search_files",
        "description": "Search for files by pattern or search text content inside files (grep).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory to search in", "default": "."},
                "pattern": {"type": "string", "description": "Regex pattern or glob to search for"},
                "target": {"type": "string", "enum": ["files", "content"], "default": "content"}
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "download_file",
        "description": "Download any file or dataset from a public URL directly into the workspace, with optional auto-unzip.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "HTTP/HTTPS download URL"},
                "save_as": {"type": "string", "description": "Target filename in workspace (optional)"},
                "extract_archive": {"type": "boolean", "default": False, "description": "Auto extract if zip/tar.gz"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "http_request",
        "description": "Perform HTTP GET, POST, PUT, DELETE requests directly from the cloud VM datacenter IP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"], "default": "GET"},
                "url": {"type": "string", "description": "Target URL"},
                "headers": {"type": "object", "description": "Request headers"},
                "json_body": {"type": "object", "description": "JSON payload (for POST/PUT)"}
            },
            "required": ["url"]
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
        "description": "Recall stored memories and persistent state across runs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Optional key name. Omit to retrieve all memories."}
            }
        }
    },
    {
        "name": "process_manager",
        "description": "List running processes, check CPU/RAM consumption, or terminate a process.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "kill"], "default": "list"},
                "pid": {"type": "integer", "description": "Process PID to kill (if action=kill)"}
            }
        }
    },
    {
        "name": "system_info",
        "description": "Get runner OS, hardware specs (CPU, RAM, Disk), and workspace metrics.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]

# --- Tool Handlers ---

async def handle_take_screenshot(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", "desktop")
    full_page = args.get("full_page", False)
    
    if target == "browser":
        page, err = await get_browser_page()
        if err:
            return {"error": err}
        try:
            screenshot_bytes = await page.screenshot(type="jpeg", quality=80, full_page=full_page)
            b64_img = base64.b64encode(screenshot_bytes).decode("utf-8")
            log_history("TAKE_SCREENSHOT: Browser captured")
            return {
                "success": True,
                "target": "browser",
                "current_url": page.url,
                "image_format": "jpeg",
                "screenshot_base64": b64_img
            }
        except Exception as e:
            return {"error": f"Browser screenshot failed: {str(e)}"}
    else:
        try:
            out_path = os.path.join(WORKSPACE_DIR, "desktop_screenshot.jpg")
            res = subprocess.run(f"DISPLAY=:99 scrot -q 80 {out_path} 2>/dev/null || DISPLAY=:99 import -window root {out_path} 2>/dev/null", shell=True)
            if os.path.exists(out_path):
                with open(out_path, "rb") as f:
                    b64_img = base64.b64encode(f.read()).decode("utf-8")
                return {
                    "success": True,
                    "target": "desktop",
                    "image_format": "jpeg",
                    "screenshot_base64": b64_img
                }
            else:
                return {"error": "No virtual X11 display active or scrot tool missing."}
        except Exception as e:
            return {"error": str(e)}

async def handle_browser_open(args: Dict[str, Any]) -> Dict[str, Any]:
    url = args.get("url", "")
    wait_until = args.get("wait_until", "domcontentloaded")
    capture_screenshot = args.get("capture_screenshot", True)
    
    page, err = await get_browser_page()
    if err:
        return {"error": err}
    
    try:
        await page.goto(url, wait_until=wait_until, timeout=30000)
        title = await page.title()
        text_content = await page.evaluate("() => document.body ? document.body.innerText.slice(0, 5000) : ''")
        
        res = {
            "title": title,
            "url": page.url,
            "text_preview": text_content,
            "status": "loaded"
        }
        
        if capture_screenshot:
            screenshot_bytes = await page.screenshot(type="jpeg", quality=75)
            res["screenshot_base64"] = base64.b64encode(screenshot_bytes).decode("utf-8")
        
        log_history(f"BROWSER_GOTO: {url} (Title: {title[:40]})")
        return res
    except Exception as e:
        return {"error": f"Browser navigation failed: {str(e)}"}

async def handle_browser_interact(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action")
    selector = args.get("selector")
    text = args.get("text", "")
    script = args.get("script", "")
    
    page, err = await get_browser_page()
    if err:
        return {"error": err}
    
    try:
        if action == "click":
            await page.click(selector, timeout=10000)
            return {"success": True, "action": "click", "selector": selector}
        elif action == "type":
            await page.fill(selector, text, timeout=10000)
            return {"success": True, "action": "type", "selector": selector}
        elif action == "evaluate_js":
            result = await page.evaluate(script)
            return {"success": True, "action": "evaluate_js", "result": result}
        elif action == "screenshot":
            screenshot_bytes = await page.screenshot(type="jpeg", quality=75)
            return {
                "success": True,
                "screenshot_base64": base64.b64encode(screenshot_bytes).decode("utf-8")
            }
        elif action == "get_html":
            html = await page.content()
            return {"html_length": len(html), "html_preview": html[:4000]}
        elif action == "scroll":
            await page.evaluate("window.scrollBy(0, 600)")
            return {"success": True, "action": "scroll"}
        else:
            return {"error": f"Unknown browser action: {action}"}
    except Exception as e:
        return {"error": str(e)}

async def handle_execute_command(args: Dict[str, Any]) -> Dict[str, Any]:
    cmd = args.get("command", "")
    timeout = args.get("timeout", 120)
    cwd = args.get("cwd", WORKSPACE_DIR)
    target_cwd = cwd if os.path.isabs(cwd) else os.path.join(WORKSPACE_DIR, cwd)
    
    log_history(f"CMD: {cmd}")
    
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=target_cwd if os.path.exists(target_cwd) else WORKSPACE_DIR
        )
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
            "cwd": os.path.abspath(target_cwd)
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {timeout} seconds"}
    except Exception as e:
        return {"error": str(e)}

async def handle_python_eval(args: Dict[str, Any]) -> Dict[str, Any]:
    code = args.get("code", "")
    log_history(f"PYTHON_EVAL: {code[:60]}...")
    
    import io
    from contextlib import redirect_stdout, redirect_stderr
    
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec_globals = {"WORKSPACE_DIR": WORKSPACE_DIR, "os": os, "sys": sys, "time": time}
            exec(code, exec_globals)
        return {
            "stdout": stdout_buf.getvalue(),
            "stderr": stderr_buf.getvalue(),
            "success": True
        }
    except Exception as e:
        return {
            "stdout": stdout_buf.getvalue(),
            "stderr": stderr_buf.getvalue() + f"\nException: {str(e)}",
            "success": False
        }

async def handle_read_file(args: Dict[str, Any]) -> Dict[str, Any]:
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

async def handle_write_file(args: Dict[str, Any]) -> Dict[str, Any]:
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

async def handle_search_files(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("path", ".")
    pattern = args.get("pattern", "")
    target = args.get("target", "content")
    
    search_dir = path if os.path.isabs(path) else os.path.join(WORKSPACE_DIR, path)
    results = []
    
    try:
        regex = re.compile(pattern, re.IGNORECASE)
        for root, _, files in os.walk(search_dir):
            for file in files:
                rel_file = os.path.relpath(os.path.join(root, file), search_dir)
                if target == "files":
                    if regex.search(rel_file):
                        results.append(rel_file)
                else:
                    full_p = os.path.join(root, file)
                    try:
                        with open(full_p, "r", encoding="utf-8", errors="ignore") as f:
                            for idx, line in enumerate(f, 1):
                                if regex.search(line):
                                    results.append({"file": rel_file, "line": idx, "text": line.strip()[:200]})
                                    if len(results) >= 100:
                                        break
                    except Exception:
                        continue
            if len(results) >= 100:
                break
        return {"matches": results, "total": len(results)}
    except Exception as e:
        return {"error": str(e)}

async def handle_download_file(args: Dict[str, Any]) -> Dict[str, Any]:
    url = args.get("url", "")
    save_as = args.get("save_as") or os.path.basename(url.split("?")[0]) or "downloaded_file"
    extract_archive = args.get("extract_archive", False)
    target_path = os.path.join(WORKSPACE_DIR, save_as)
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=45) as response, open(target_path, "wb") as out_file:
            data = response.read()
            out_file.write(data)
        
        extracted = False
        if extract_archive and (save_as.endswith(".zip") or save_as.endswith(".tar.gz")):
            if save_as.endswith(".zip"):
                import zipfile
                with zipfile.ZipFile(target_path, "r") as z:
                    z.extractall(WORKSPACE_DIR)
                extracted = True
            elif save_as.endswith(".tar.gz") or save_as.endswith(".tgz"):
                import tarfile
                with tarfile.open(target_path, "r:gz") as t:
                    t.extractall(WORKSPACE_DIR)
                extracted = True
        
        log_history(f"DOWNLOAD: {url} -> {save_as} ({len(data)} bytes)")
        return {"success": True, "saved_path": target_path, "size_bytes": len(data), "extracted": extracted}
    except Exception as e:
        return {"error": str(e)}

async def handle_http_request(args: Dict[str, Any]) -> Dict[str, Any]:
    import requests as py_requests
    method = args.get("method", "GET").upper()
    url = args.get("url", "")
    headers = args.get("headers", {})
    json_body = args.get("json_body", None)
    
    try:
        resp = py_requests.request(method=method, url=url, headers=headers, json=json_body, timeout=30)
        return {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "text": resp.text[:4000],
            "is_json": "application/json" in resp.headers.get("Content-Type", "")
        }
    except Exception as e:
        return {"error": str(e)}

async def handle_memory_store(args: Dict[str, Any]) -> Dict[str, Any]:
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

async def handle_memory_recall(args: Dict[str, Any]) -> Dict[str, Any]:
    key = args.get("key", None)
    mem = load_memory()
    if key:
        return {"key": key, "entry": mem.get(key, None)}
    return {"all_memories": mem, "total_keys": len(mem)}

async def handle_process_manager(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "list")
    pid = args.get("pid")
    
    try:
        import psutil
        if action == "kill" and pid:
            p = psutil.Process(pid)
            p.terminate()
            return {"success": True, "killed_pid": pid}
        
        proc_list = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                proc_list.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return {"processes": proc_list[:30], "total_count": len(proc_list)}
    except ImportError:
        res = subprocess.run("ps aux --sort=-%cpu | head -25", shell=True, capture_output=True, text=True)
        return {"stdout": res.stdout}

async def handle_system_info(args: Dict[str, Any]) -> Dict[str, Any]:
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
    "system_info": handle_system_info
}

# --- API Endpoints ---

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
        result = await handler(args)
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
            }
        }
    elif req.method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "persistent-super-utility-mcp-runner", "version": "3.0.0"}
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
