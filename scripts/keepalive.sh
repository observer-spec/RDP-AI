#!/bin/sh
# Keep-alive loop (~5h40m): heal tunnels, R2 sync every 30min, MCP health, auto-respawn at 4.5h.
# Needs: GH_TOKEN, GITHUB_REPOSITORY, optional R2_* env.
set -e
heal_tunnel() {
  url_port=$1
  log_file=$2
  if ! pgrep -f "cloudflared tunnel.*$url_port" > /dev/null 2>&1; then
    echo "⚠️ Tunnel :$url_port died, healing..."
    pkill -f "cloudflared tunnel.*$url_port" 2>/dev/null || true
    cloudflared tunnel --url http://127.0.0.1:$url_port 2>&1 | tee -a "$log_file" &
    sleep 5
    NEW_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$log_file" | tail -n 1 || true)
    [ -n "$NEW_URL" ] && echo "✓ Healed :$url_port → $NEW_URL"
  fi
}
for tick in $(seq 1 68); do
  echo "Runner tick $tick/68: $(date) — uptime $((tick*5))min"
  heal_tunnel 8443 tunnel.log
  heal_tunnel 8000 tunnel-mcp.log
  if [ $((tick % 6)) -eq 0 ] && [ -n "$R2_ACCOUNT_ID" ]; then
    echo "📦 R2 sync tick $tick..."
    sh scripts/r2_common.sh sync || true
  fi
  if ! curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo "⚠️ MCP /health failed, restarting server..."
    pkill -f "server.py" 2>/dev/null || true
    WORKSPACE_DIR="$PWD/workspace" python server.py &
    sleep 3
  fi
  if [ "$tick" -eq 54 ]; then
    echo "🔄 Chaining next runner for infinite uptime..."
    gh workflow run mcp-runner.yml --ref main -f use_prebaked_image=true 2>&1 || \
    curl -s -X POST -H "Authorization: token $GH_TOKEN" -H "Accept: application/vnd.github+json" \
      "https://api.github.com/repos/${GITHUB_REPOSITORY}/actions/workflows/mcp-runner.yml/dispatches" \
      -d '{"ref":"main","inputs":{"use_prebaked_image":"true"}}' 2>&1 | head
    echo "✓ Next runner dispatched, this one will finish gracefully in ~50min"
  fi
  sleep 300
done
