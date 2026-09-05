"""System / memory / tmux handlers (extracted from server.py)."""
import os
import platform
import subprocess
import sys
import time
from typing import Any, Dict

from .config import WORKSPACE_DIR, load_memory, log_history, save_memory


async def handle_memory_store(args: Dict[str, Any]) -> Dict[str, Any]:
    key = args.get("key", "").strip()
    value = args.get("value", "")

    mem = load_memory()
    mem[key] = {"value": value, "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
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
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                proc_list.append(p.info)
            except Exception:
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
        "github_runner_os": os.getenv("RUNNER_OS"),
    }


async def handle_tmux_session(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "list")
    session = args.get("session", "main")
    command = args.get("command", "")
    lines = args.get("lines", 100)
    import shutil

    if not shutil.which("tmux"):
        subprocess.run(
            "sudo apt-get update -qq && sudo apt-get install -y tmux 2>&1 | tail -n 5",
            shell=True,
            timeout=60,
        )

    def run(cmd):
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return r.stdout.strip(), r.stderr.strip(), r.returncode

    if action == "list":
        out, err, code = run("tmux list-sessions -F '#{session_name} #{session_created} #{pane_current_command}' 2>&1 || echo 'no sessions'")
        sessions = [] if "no sessions" in out else out.splitlines()
        return {"sessions": sessions, "raw": out, "stderr": err}
    elif action == "create":
        out, err, code = run(f"tmux has-session -t {session} 2>&1 && echo exists || tmux new-session -d -s {session} 2>&1")
        if command:
            run(f"tmux send-keys -t {session} '{command}' Enter")
        out2, _, _ = run("tmux list-sessions 2>&1 | head")
        return {"action": "create", "session": session, "output": out, "sessions": out2}
    elif action == "send":
        if not command:
            return {"error": "command required for send"}
        out, err, code = run(f"tmux send-keys -t {session} '{command}' Enter; echo ok")
        return {"action": "send", "session": session, "command": command, "result": out, "stderr": err}
    elif action == "capture":
        out, err, code = run(f"tmux capture-pane -p -t {session} -S -{lines} 2>&1 | tail -n {lines}")
        if code != 0:
            return {"error": err or out, "session": session}
        return {"session": session, "output": out, "lines": len(out.splitlines())}
    elif action == "kill":
        out, err, code = run(f"tmux kill-session -t {session} 2>&1; echo killed:{code}")
        return {"action": "kill", "session": session, "result": out}
    else:
        return {"error": f"unknown action {action}"}
