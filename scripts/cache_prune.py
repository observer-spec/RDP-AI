#!/usr/bin/env python3
"""Prune workspace caches, keep newest 5. Needs GH_TOKEN + repo slug env."""
import json
import os
import urllib.request

token = os.environ.get("GH_TOKEN", "")
if not token:
    print("GH_TOKEN not set — skipping cache pruning")
    raise SystemExit(0)

repo = os.environ.get("GITHUB_REPOSITORY", "observer-spec/RDP-AI")
headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "RDP-AI-Cache-Pruner",
}
base = f"https://api.github.com/repos/{repo}/actions/caches"

try:
    req = urllib.request.Request(base, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode())
    caches = data.get("actions_caches", [])
    caches.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    for c in caches[5:]:
        cid = c.get("id")
        if cid:
            del_req = urllib.request.Request(f"{base}?cache_id={cid}", headers=headers, method="DELETE")
            with urllib.request.urlopen(del_req, timeout=20) as d:
                print(f"pruned cache {cid}: {d.status}")
except Exception as e:
    print(f"cache pruning encountered an error (non-fatal): {e}")
