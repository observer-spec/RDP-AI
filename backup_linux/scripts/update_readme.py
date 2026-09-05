#!/usr/bin/env python3
"""Patch README.md LIVE_URLS block with current Tailscale endpoints (called by workflow)."""
import os
import datetime
import pathlib
import re

desktop = os.environ.get("DESKTOP_URL", "")
mcp = os.environ.get("MCP_URL", "")
if not desktop or not mcp:
    ep = pathlib.Path("tailnet-endpoint.txt")
    if ep.exists():
        lines = ep.read_text().splitlines()
        desktop = desktop or (lines[0] if len(lines) > 0 else "")
        mcp = mcp or (lines[1] if len(lines) > 1 else "")
desktop = desktop or "https://<tailnet-ip>:8443"
mcp = mcp or "http://<tailnet-ip>:8000"
rdp_host = re.search(r"https?://([^/:]+)", desktop)
rdp = f"{rdp_host.group(1)}:3389" if rdp_host else "<tailnet-ip>:3389"

timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
repo = os.environ.get("GITHUB_REPOSITORY", "observer-spec/RDP-AI")
run_id = os.environ.get("GITHUB_RUN_ID", "")
run_number = os.environ.get("GITHUB_RUN_NUMBER", "")
run_url = f"https://github.com/{repo}/actions/runs/{run_id}" if run_id else ""

block = (
    "<!-- LIVE_URLS_START -->\n"
    f"> **Current Run (Tailscale, tailnet only):** [Desktop]({desktop}) `{desktop}` | [MCP]({mcp}) `{mcp}` /mcp\n"
    f"> *Last updated: {timestamp} — [Run #{run_number}]({run_url}) — auto-updated by workflow*\n"
    "> Desktop login: `runner` / `VNC_PASSWORD` (accept self-signed cert) — MCP: `Authorization: Bearer $MCP_TOKEN` at `/mcp`\n"
    f"> RDP (Windows Remote Desktop): `{rdp}` — same login\n"
    "<!-- LIVE_URLS_END -->"
)

readme = pathlib.Path("README.md")
text = readme.read_text()
new_text, n = re.subn(r"<!-- LIVE_URLS_START -->.*?<!-- LIVE_URLS_END -->", block, text, flags=re.DOTALL)
if n == 0:
    print("WARN: no LIVE_URLS markers found")
else:
    readme.write_text(new_text)
    print(f"README updated with {desktop} / {mcp}")
