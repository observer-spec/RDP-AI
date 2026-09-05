"""Shared config + state helpers. No behavior change from server.py v3.2."""
import json
import os
import time

AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", os.path.join(os.getcwd(), "workspace"))
STATE_FILE = os.path.join(WORKSPACE_DIR, "agent_memory.json")
HISTORY_FILE = os.path.join(WORKSPACE_DIR, "command_history.log")

os.makedirs(WORKSPACE_DIR, exist_ok=True)


def load_memory():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_memory(data):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def log_history(entry: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {entry}\n")
