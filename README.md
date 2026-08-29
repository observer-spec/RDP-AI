# RDP-AI — Cloud Desktop & MCP Runner

Run an ephemeral Linux cloud desktop (XFCE4 + Chrome + KasmVNC at 60FPS) on GitHub Actions, exposed through free Cloudflare tunnels. Includes an MCP server for AI agent control.

## 🔴 Live Status
<!-- LIVE_URLS_START -->
> **Current Run:** [Desktop](https://influences-sticky-nano-symbol.trycloudflare.com) `https://influences-sticky-nano-symbol.trycloudflare.com` | [MCP](https://websites-sitting-traveler-corporate.trycloudflare.com) `https://websites-sitting-traveler-corporate.trycloudflare.com` /mcp
> *Last updated: 2026-08-29 18:13 UTC — [Run #35](https://github.com/observer-spec/RDP-AI/actions/runs/33267582377) — auto-updated by workflow*
> Desktop login: `runner` / `VNC_PASSWORD` — MCP: `Authorization: Bearer $MCP_TOKEN` at `/mcp`
<!-- LIVE_URLS_END -->

## Features
- **Web Desktop:** KasmVNC streaming (WebP/H.264, 60 FPS) in any browser.
- **MCP Server:** Compatible with MCP AI agents (Claude Desktop, Cursor, Hermes, etc.).
- **Cloudflare Tunnels:** Free, zero-config public endpoints via `*.trycloudflare.com`.
- **Prebaked Image:** Desktop stack ships as a container image on ghcr.io — boots in seconds, not minutes.
- **Persistent Workspace:** `workspace/` survives between runs via Actions cache + `workspace-data` branch (infinite).
- **Single-Instance Guard:** New dispatches automatically cancel zombie runs.
- **Infinite Survival:** Auto-heal tunnels + auto-respawn at 4.5h → never dies.

## One-Time Setup (required before first run)

The repo is public, so no credentials live in the code or logs. Add repository secrets:

1. Go to **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
2. Add:

| Secret | Purpose | Required |
|--------|---------|----------|
| `VNC_PASSWORD` | Desktop login password (user: `runner`) | ✅ |
| `MCP_TOKEN` | Bearer token protecting the MCP API (`/call`, `/mcp`, `/tools`) | ✅ |
| `R2_ACCOUNT_ID` | Cloudflare R2 Account ID (for infinite workspace) | ⭕ Optional |
| `R2_ACCESS_KEY_ID` | R2 API Token Access Key | ⭕ Optional |
| `R2_SECRET_ACCESS_KEY` | R2 API Token Secret | ⭕ Optional |
| `R2_BUCKET` | R2 bucket name (default `rdp-ai-workspace`) | ⭕ Optional |

Without these secrets the workflow refuses to start.

## How to Start the Runner
1. Go to **Actions** → **Cloudflare MCP Runner** → **Run workflow**.
2. Keep `use_prebaked_image` on `true` for a fast boot (falls back to live install automatically if the image is missing).
3. Open the run — the Job Summary shows the live `trycloudflare.com` desktop URL.
4. Log in with user `runner` + your `VNC_PASSWORD` secret value.

## MCP Endpoints
- `/health` — unauthenticated liveness probe.
- `/tools`, `/call`, `/mcp` — require header: `Authorization: Bearer <your MCP_TOKEN>`.
- **New:** `tmux_session` — persistent tmux. `{"action":"create","session":"dev","command":"npm run dev"}` → survives between calls. Actions: `create/list/send/capture/kill`.

### MCP Examples
```bash
# persistent bot that survives 5h
curl -H "Authorization: Bearer $MCP_TOKEN" -X POST https://<mcp>/call -d '{"name":"tmux_session","arguments":{"action":"create","session":"bot","command":"python bot.py"}}'
# check output 10min later
curl -H "Authorization: Bearer $MCP_TOKEN" -X POST https://<mcp>/call -d '{"name":"tmux_session","arguments":{"action":"capture","session":"bot","lines":50}}'
```

## Maintenance
- **Rebuild the desktop image:** push changes to `Dockerfile`/`entrypoint.sh`, or run **Build Prebaked Desktop Image** manually. The runner pulls `ghcr.io/observer-spec/rdp-ai:latest`.
- **Workspace cache:** rolling window of 5; older caches pruned automatically.
- **Workspace persistence (3 layers):** `actions/cache` → `workspace-data` git branch → **R2** (if configured, syncs every 30min + on exit, restores on boot). R2 free tier = 10GB forever.
- **R2 setup:** Create R2 bucket in Cloudflare Dashboard → API Token → add 4 secrets above → next run auto-syncs.
