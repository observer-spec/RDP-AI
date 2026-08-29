# RDP-AI — Cloud Desktop & MCP Runner

Run an ephemeral Linux cloud desktop (XFCE4 + Chrome + KasmVNC at 60FPS) on GitHub Actions, exposed through free Cloudflare tunnels. Includes an MCP server for AI agent control.

## Features
- **Web Desktop:** KasmVNC streaming (WebP/H.264, 60 FPS) in any browser.
- **MCP Server:** Compatible with MCP AI agents (Claude Desktop, Cursor, Hermes, etc.).
- **Cloudflare Tunnels:** Free, zero-config public endpoints via `*.trycloudflare.com`.
- **Prebaked Image:** Desktop stack ships as a container image on ghcr.io — boots in seconds, not minutes.
- **Persistent Workspace:** `workspace/` survives between runs via Actions cache.
- **Single-Instance Guard:** New dispatches automatically cancel zombie runs.

## One-Time Setup (required before first run)

The repo is public, so no credentials live in the code or logs. Add two repository secrets:

1. Go to **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
2. Add:

| Secret | Purpose |
|--------|---------|
| `VNC_PASSWORD` | Desktop login password (user: `runner`) |
| `MCP_TOKEN` | Bearer token protecting the MCP API (`/call`, `/mcp`, `/tools`) |

Without these secrets the workflow refuses to start.

## How to Start the Runner
1. Go to **Actions** → **Cloudflare MCP Runner** → **Run workflow**.
2. Keep `use_prebaked_image` on `true` for a fast boot (falls back to live install automatically if the image is missing).
3. Open the run — the Job Summary shows the live `trycloudflare.com` desktop URL.
4. Log in with user `runner` + your `VNC_PASSWORD` secret value.

## MCP Endpoints
- `/health` — unauthenticated liveness probe.
- `/tools`, `/call`, `/mcp` — require header: `Authorization: Bearer <your MCP_TOKEN>`.

## Maintenance
- **Rebuild the desktop image:** push changes to `Dockerfile`/`entrypoint.sh`, or run **Build Prebaked Desktop Image** manually. The runner pulls `ghcr.io/observer-spec/rdp-ai:latest`.
- **Workspace cache:** rolling window of 5; older caches are pruned automatically after each run.
