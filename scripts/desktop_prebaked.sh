#!/bin/sh
# Boot prebaked desktop container (fast path). Exits 1 to trigger live fallback.
set -e
echo "Pulling prebuilt desktop image from ghcr.io..."
docker pull ghcr.io/observer-spec/rdp-ai:latest || {
  echo "::warning::Prebaked image unavailable — falling back to live install"
  exit 1
}

docker run -d --name desktop \
  --shm-size=2g \
  -e VNC_USER="$VNC_USER" \
  -e VNC_PASS="$VNC_PASS" \
  -e DISPLAY=:1 \
  -v "$PWD/workspace:/workspace" \
  --network host \
  ghcr.io/observer-spec/rdp-ai:latest

for i in $(seq 1 30); do
  if curl -sk -o /dev/null http://127.0.0.1:8443; then
    echo "KasmVNC is up."
    break
  fi
  sleep 2
done
curl -sk -o /dev/null http://127.0.0.1:8443 || {
  echo "::error::KasmVNC never came up inside container"; exit 1;
}
echo "DISPLAY=:1" >> "$GITHUB_ENV"
