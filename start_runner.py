import os
import sys
import time
import requests

GITHUB_TOKEN = os.getenv("OBSERVER_GITHUB_TOKEN", "")
REPO = "observer-spec/RDP-AI"
WORKFLOW_FILE = "mcp-runner.yml"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

def trigger_workflow(runner_os="ubuntu-latest", auth_token="mcp-secret-key-123"):
    if not GITHUB_TOKEN:
        print("[-] Please set OBSERVER_GITHUB_TOKEN environment variable.")
        return
    print(f"[*] Triggering GitHub Actions workflow on {REPO} ({runner_os})...")
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    payload = {
        "ref": "main",
        "inputs": {
            "runner_os": runner_os,
            "auth_token": auth_token
        }
    }
    
    r = requests.post(url, json=payload, headers=headers)
    if r.status_code == 204:
        print("[+] Workflow dispatched successfully!")
    else:
        print(f"[-] Failed to dispatch workflow: {r.status_code} - {r.text}")

if __name__ == "__main__":
    runner_os = sys.argv[1] if len(sys.argv) > 1 else "ubuntu-latest"
    trigger_workflow(runner_os)
