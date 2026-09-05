#!/bin/sh
# Start MCP server on the tailnet. No Cloudflare tunnels.
# Needs: tailscale already up (tailscale/github-action step), WORKSPACE_DIR, GITHUB_ENV, GITHUB_STEP_SUMMARY.
set -e
python server.py &
sleep 2

# --- Health check: desktop (KasmVNC :8443) must answer ---
for i in $(seq 1 15); do
  if curl -sk -o /dev/null https://127.0.0.1:8443; then
    break
  fi
  sleep 2
done
curl -sk -o /dev/null https://127.0.0.1:8443 || { echo "::error::KasmVNC failed on :8443"; exit 1; }

# --- Health check: MCP server must answer ---
MCP_OK=""
for i in $(seq 1 15); do
  HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health || true)
  [ "$HTTP_CODE" = "200" ] && MCP_OK=yes && break
  sleep 2
done
[ -n "$MCP_OK" ] || { echo "::error::MCP server failed /health on :8000"; exit 1; }

# --- Tailnet IP (the only address clients use) ---
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null | head -n 1 || true)
[ -n "$TAILSCALE_IP" ] || { echo "::error::tailscale ip -4 returned nothing (is Tailscale up?)"; exit 1; }

# Allow tailnet traffic to both services (belt and braces, like MobileDevice).
sudo iptables -I INPUT -i tailscale0 -p tcp --dport 8443 -j ACCEPT 2>/dev/null || true
sudo iptables -I INPUT -i tailscale0 -p tcp --dport 8000 -j ACCEPT 2>/dev/null || true

DESKTOP_TAILNET="https://$TAILSCALE_IP:8443"
MCP_TAILNET="http://$TAILSCALE_IP:8000"

{
  echo "TAILSCALE_IP=$TAILSCALE_IP"
  echo "DESKTOP_URL=$DESKTOP_TAILNET"
  echo "MCP_URL=$MCP_TAILNET"
  printf '%s\n' "$DESKTOP_TAILNET" "$MCP_TAILNET" > tailnet-endpoint.txt
} >> "$GITHUB_ENV"

# Private endpoint pointer (tailnet-only address, expires with the run).
cat > CURRENT_TAILSCALE_ENDPOINT.md <<EOF
# Active RDP-AI endpoint (Tailscale)

Private to your tailnet. Expires when the workflow ends.

- **Desktop:** $DESKTOP_TAILNET (login: \`runner\` / \`VNC_PASSWORD\`, accept the self-signed cert)
- **MCP:** $MCP_TAILNET/mcp (\`Authorization: Bearer \$MCP_TOKEN\`)
EOF

# Never print credentials — public repo, public Actions log.
echo "==============================================================="
echo "⚡ WEB DESKTOP ONLINE (Tailscale)"
echo "🔗 Desktop: $DESKTOP_TAILNET"
echo "🛠 MCP: $MCP_TAILNET/mcp"
echo "🔐 Credentials: from repository secrets (never shown here)"
echo "📁 Persistent Workspace: $WORKSPACE_DIR"
echo "==============================================================="

cat >> "$GITHUB_STEP_SUMMARY" << SUMMARY
# ⚡ Live Cloud Desktop & MCP Server (Tailscale)

- **Desktop:** \`$DESKTOP_TAILNET\` (tailnet only, accept self-signed cert)
- **MCP:** \`$MCP_TAILNET\`/mcp (tailnet only)
- **Login:** user + password come from repo secrets (\`VNC_USER\` / \`VNC_PASSWORD\`)
- **Browser:** Google Chrome (shortcut on desktop)
SUMMARY
