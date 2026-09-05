#!/usr/bin/env python3
"""Prune workspace caches, keep newest 5. Needs GH_TOKEN + repo slug env."""
import os
import requests

token = os.environ["GH_TOKEN"]
repo = os.environ.get("GITHUB_REPOSITORY", "observer-spec/RDP-AI")
headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
base = f"https://api.github.com/repos/{repo}/actions/caches"
r = requests.get(base, headers=headers, timeout=20)
caches = r.json().get("actions_caches", [])
caches.sort(key=lambda c: c.get("created_at", ""), reverse=True)
for c in caches[5:]:
    cid = c.get("id")
    if cid:
        d = requests.delete(f"{base}?cache_id={cid}", headers=headers, timeout=20)
        print(f"pruned cache {cid}: {d.status_code}")
