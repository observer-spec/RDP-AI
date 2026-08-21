"""
Persistent Super-Utility MCP Remote Server for GitHub Actions Runners.
Includes:
- File Management & Fast Content Search (grep)
- Shell & Direct Python Code Execution
- Real Headless Browser Automation (Playwright Chromium)
- Web Fetching & File Downloading
- Process Management
- Persistent Memory & Workspace State Caching
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
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", os.path.join(os.getcwd(), "workspace"))
STATE_FILE = os.path.join(WORKSPACE_DIR, "agent_memory.json")
HISTORY_FILE = os.path.join(WORKSPACE_DIR, "command_history.log")

os.makedirs(WORKSPACE_DIR, exist_ok=True)

app = FastAPI(title="Persistent Super-Utility MCP Remote Server", version="2.0.0")

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

# --- Browser Session State (Playwright) ---

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
        browser_instance = await playwright_obj.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = await browser_instance.new_context(viewport={"width": 1280, "height": 800})
        browser_page = await context.new_page()
    
    return browser_page, None

# --- Tool Definitions ---

TOOLS = [
    {
        "name": "execute_command",
        "description": "Execute any shell command (bash/cmd/PowerShell) on the runner VM.",
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
                "target": {"type": "string", "enum": ["files", "content"], "default": "content", "description": "'files' to find matching filenames, 'content' to grep inside files"}
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "download_file",
        "description": "Download any file or dataset from a public URL directly into the workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "HTTP/HTTPS download URL"},
                "save_as": {"type": "string", "description": "Target filename in workspace (optional)"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "browser_open",
        "description": "Navigate real headless Chromium browser to a URL. Returns page title, text content, and screenshot.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Web URL to open (e.g. https://example.com)"},
                "wait_until": {"type": "string", "enum": ["load", "domcontentloaded", "networkidle"], "default": "domcontentloaded"},
                "capture_screenshot": {"type": "boolean", "default": True, "description": "Whether to return base64 screenshot"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "browser_interact",
        "description": "Perform actions in the active browser: click, type, evaluate JavaScript, or take screenshot.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["click", "type", "evaluate_js", "screenshot", "get_html", "scroll"]},
                "selector": {"type": "string", "description": "CSS or text selector for click/type"},
                "text": {"type": "string", "description": "Text to type"},
                "script": {"type": "string", "description": "JavaScript code to evaluate"}
            },
            "required": ["action"]
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

# --- Tool Implementations ---

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
    target_path = os.path.join(WORKSPACE_DIR, save_as)
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response, open(target_path, "wb") as out_file:
            data = response.read()
            out_file.write(data)
        log_history(f"DOWNLOAD: {url} -> {save_as} ({len(data)} bytes)")
        return {"success": True, "saved_path": target_path, "size_bytes": len(data)}
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
        
        # Extract readable body text
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
        # Fallback to ps aux
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
    "execute_command": handle_execute_command,
    "python_eval": handle_python_eval,
    "read_file": handle_read_file,
    "write_file": handle_write_file,
    "search_files": handle_search_files,
    "download_file": handle_download_file,
    "browser_open": handle_browser_open,
    "browser_interact": handle_browser_interact,
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

@app.get("/")
def index():
    return {
        "status": "online",
        "service": "Persistent Super-Utility MCP Remote Server",
        "version": "2.0.0",
        "tools_count": len(TOOLS),
        "workspace": WORKSPACE_DIR
    }

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
                "serverInfo": {"name": "persistent-super-utility-mcp-runner", "version": "2.0.0"}
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
