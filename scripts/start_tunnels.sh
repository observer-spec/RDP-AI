#!/bin/sh
# Start MCP server + both Cloudflare tunnels, health-check, export URLs.
set -e
python server.py &
sleep 2

cloudflared tunnel --url http://127.0.0.1:8443 2>&1 | tee tunnel.log &
cloudflared tunnel --url http://127.0.0.1:8000 2>&1 | tee tunnel-mcp.log &

TUNNEL_URL=""
for i in $(seq 1 45); do
  TUNNEL_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' tunnel.log | head -n 1 || true)
  [ -n "$TUNNEL_URL" ] && break
  sleep 2
done
[ -n "$TUNNEL_URL" ] || { echo "::error::Desktop tunnel never got a URL"; exit 1; }

MCP_TUNNEL_URL=""
for i in $(seq 1 45); do
  MCP_TUNNEL_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' tunnel-mcp.log | head -n 1 || true)
  [ -n "$MCP_TUNNEL_URL" ] && break
  sleep 2
done
[ -n "$MCP_TUNNEL_URL" ] || { echo "::error::MCP tunnel never got a URL"; exit 1; }

MCP_OK=""
for i in $(seq 1 15); do
  HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health || true)
  [ "$HTTP_CODE" = "200" ] && MCP_OK=yes && break
  sleep 2
done
[ -n "$MCP_OK" ] || { echo "::error::MCP server failed /health on :8000"; exit 1; }

{
  echo "DESKTOP_URL=$TUNNEL_URL"
  echo "MCP_URL=$MCP_TUNNEL_URL"
  printf '%s\n' "$TUNNEL_URL" "$MCP_TUNNEL_URL" > tunnel-urls.txt
} >> "$GITHUB_ENV"

echo "==============================================================="
echo "⚡ WEB DESKTOP ONLINE"
echo "🔗 Desktop URL: $TUNNEL_URL"
echo "🛠 MCP URL: $MCP_TUNNEL_URL/mcp"
echo "🔐 Credentials: from repository secrets (never shown here)"
echo "📁 Persistent Workspace: $WORKSPACE_DIR"
echo "==============================================================="

cat >> "$GITHUB_STEP_SUMMARY" << SUMMARY
# ⚡ Live Cloud Desktop & MCP Server

- **Web Desktop URL:** [$TUNNEL_URL]($TUNNEL_URL)
- **MCP URL:** [$MCP_TUNNEL_URL]($MCP_TUNNEL_URL)/mcp
- **Login:** user + password come from repo secrets (\`VNC_USER\` / \`VNC_PASSWORD\`)
- **Browser:** Google Chrome (shortcut on desktop)
SUMMARY
