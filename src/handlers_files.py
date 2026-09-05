"""File / exec / network handlers (extracted from server.py)."""
import os
import re
import subprocess
import sys
import time
import urllib.request
from typing import Any, Dict

from .config import WORKSPACE_DIR, log_history


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
            cwd=target_cwd if os.path.exists(target_cwd) else WORKSPACE_DIR,
        )
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
            "cwd": os.path.abspath(target_cwd),
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {timeout} seconds"}
    except Exception as e:
        return {"error": str(e)}


async def handle_python_eval(args: Dict[str, Any]) -> Dict[str, Any]:
    code = args.get("code", "")
    log_history(f"PYTHON_EVAL: {code[:60]}...")

    import io
    from contextlib import redirect_stderr, redirect_stdout

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec_globals = {"WORKSPACE_DIR": WORKSPACE_DIR, "os": os, "sys": sys, "time": time}
            exec(code, exec_globals)
        return {"stdout": stdout_buf.getvalue(), "stderr": stderr_buf.getvalue(), "success": True}
    except Exception as e:
        return {
            "stdout": stdout_buf.getvalue(),
            "stderr": stderr_buf.getvalue() + f"\nException: {str(e)}",
            "success": False,
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
            "is_json": "application/json" in resp.headers.get("Content-Type", ""),
        }
    except Exception as e:
        return {"error": str(e)}
