"""Dispatch the Cloudflare MCP Runner workflow. Fixed arg handling."""
import argparse
import os
import sys

import requests

REPO = os.getenv("RDP_AI_REPO", "observer-spec/RDP-AI")
WORKFLOW_FILE = "mcp-runner.yml"


def trigger_workflow(repo: str, github_token: str, auth_token: str, ref: str = "main", use_prebaked: bool = True):
    print(f"[*] Triggering {WORKFLOW_FILE} on {repo} (ref={ref})...")
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github+json"}
    payload = {
        "ref": ref,
        "inputs": {"auth_token": auth_token, "use_prebaked_image": str(use_prebaked).lower()},
    }
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    if r.status_code == 204:
        print("[+] Workflow dispatched successfully!")
    else:
        print(f"[-] Failed: {r.status_code} - {r.text}")
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(description="Trigger the RDP-AI cloud runner")
    p.add_argument("--auth-token", default="", help="Fallback MCP token (prefer MCP_TOKEN secret)")
    p.add_argument("--ref", default="main", help="Git ref to dispatch")
    p.add_argument("--no-prebaked", action="store_true", help="Force live install instead of prebaked image")
    p.add_argument("--repo", default=REPO, help="owner/repo override")
    args = p.parse_args()

    repo = args.repo
    github_token = os.getenv("OBSERVER_GITHUB_TOKEN", "")
    if not github_token:
        print("[-] Set OBSERVER_GITHUB_TOKEN first.")
        sys.exit(1)
    trigger_workflow(repo, github_token, args.auth_token, ref=args.ref, use_prebaked=not args.no_prebaked)


if __name__ == "__main__":
    main()
