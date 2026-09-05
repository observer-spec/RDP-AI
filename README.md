# RDP-AI — Cloud Desktop & MCP Runner

Ephemeral Ubuntu desktop (XFCE4 + Chrome + KasmVNC) on GitHub Actions, exposed via Cloudflare tunnels, with an MCP server for agent control.

## 🔴 Live Status
<!-- LIVE_URLS_START -->
> Runner is **offline**. Dispatch **Actions → Cloudflare MCP Runner → Run workflow** to get fresh URLs (README auto-updates on boot).
<!-- LIVE_URLS_END -->

## Layout
- `server.py` — thin entrypoint (`python server.py`)
- `src/` — real code: `app.py` routes, `tools.py` schemas, `handlers_browser.py`, `handlers_files.py`, `handlers_sys.py`, `config.py`, `browser.py`
- `scripts/` — workflow steps: `desktop_prebaked.sh`, `desktop_live.sh`, `start_tunnels.sh`, `keepalive.sh`, `r2_common.sh`, `restore_workspace.sh`, `workspace_push.sh`, `update_readme.py`, `cache_prune.py`
- `Dockerfile` / `entrypoint.sh` — prebaked image (`ghcr.io/observer-spec/rdp-ai:latest`)
- `requirements.txt` — Python deps
- `start_runner.py` — dispatch helper (`--auth-token`, `--ref`, `--no-prebaked`)
- `mcp.json` — client template (replace `<mcp-tunnel>` + `$MCP_TOKEN` after a run)
- `workspace/` — persistent files only (survives via cache → `workspace-data` branch → R2)

## Features
- **Web Desktop:** KasmVNC streaming (WebP/H.264, 60 FPS) in any browser.
- **MCP Server:** 15 tools for agents (browser, files, exec, tmux, memory, system).
- **Cloudflare Tunnels:** free public endpoints via `*.trycloudflare.com`.
- **Prebaked Image:** boots in seconds, live-install fallback.
- **Persistent Workspace:** `actions/cache` → `workspace-data` branch → **R2** (optional).
- **Single-Instance Guard:** new dispatch cancels zombies.
- **Infinite Survival:** auto-heal tunnels + auto-respawn at 4.5h.

## One-Time Setup

Public repo, so no credentials in code or logs. Add repository secrets (**Settings → Secrets and variables → Actions**):

| Secret | Purpose | Required |
|--------|---------|----------|
| `VNC_PASSWORD` | Desktop login password (user: `runner`) | ✅ |
| `MCP_TOKEN` | Bearer token for `/call`, `/mcp`, `/tools` | ✅ |
| `R2_ACCOUNT_ID` | R2 account ID | ⭕ Optional |
| `R2_ACCESS_KEY_ID` | R2 access key | ⭕ Optional |
| `R2_SECRET_ACCESS_KEY` | R2 secret | ⭕ Optional |
| `R2_BUCKET` | Bucket name (default `rdp-ai-workspace`) | ⭕ Optional |

## Start
1. **Actions → Cloudflare MCP Runner → Run workflow** (keep `use_prebaked_image=true`).
2. Open the run — Job Summary shows live desktop + MCP URLs.
3. Log in with `runner` + your `VNC_PASSWORD`.

Or via CLI: `OBSERVER_GITHUB_TOKEN=... python start_runner.py --auth-token ...`

## MCP Endpoints
- `/health` — unauthenticated probe.
- `/tools`, `/call`, `/mcp` — require `Authorization: Bearer <MCP_TOKEN>`.
- `tmux_session` — persistent tmux: `{"action":"create","session":"dev","command":"npm run dev"}`. Actions: `create/list/send/capture/kill`.

```bash
# connect (after a run gives you the tunnel host)
# copy mcp.json and replace <mcp-tunnel> + $MCP_TOKEN

# persistent bot
curl -H "Authorization: Bearer $MCP_TOKEN" -X POST https://<mcp-tunnel>.trycloudflare.com/call \
  -d '{"name":"tmux_session","arguments":{"action":"create","session":"bot","command":"python bot.py"}}'
# check later
curl -H "Authorization: Bearer $MCP_TOKEN" -X POST https://<mcp-tunnel>.trycloudflare.com/call \
  -d '{"name":"tmux_session","arguments":{"action":"capture","session":"bot","lines":50}}'
```

## Maintenance
- **Rebuild image:** push to `Dockerfile`/`entrypoint.sh`, or run **Build Prebaked Desktop Image**.
- **Workspace (3 layers):** cache (rolling 5) → `workspace-data` branch → **R2** (every 30min + on exit, restores on boot).
