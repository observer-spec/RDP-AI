"""MCP tool schemas (extracted verbatim from server.py v3.2)."""

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
            "required": ["path"]
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
    },
    {
        "name": "tmux_session",
        "description": "Persistent tmux sessions — create, send keys, capture output, list/kill. Survives between calls unlike execute_command.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["create", "list", "send", "capture", "kill"], "description": "create=new session, list=sessions, send=keys to session, capture=pane output, kill=terminate"},
                "session": {"type": "string", "description": "tmux session name (e.g. dev, bot)"},
                "command": {"type": "string", "description": "command/keys to send (for create/send)"},
                "lines": {"type": "integer", "description": "lines to capture (default 100)", "default": 100}
            },
            "required": ["action"]
        }
    }
]
