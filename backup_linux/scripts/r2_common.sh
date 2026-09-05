#!/bin/sh
# R2 restore/sync helper. Usage: r2_common.sh [restore|sync]
# Needs env: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET (optional)
set -e
MODE="${1:-restore}"
R2_BUCKET="${R2_BUCKET:-rdp-ai-workspace}"

if [ -z "$R2_ACCOUNT_ID" ] || [ -z "$R2_ACCESS_KEY_ID" ] || [ -z "$R2_SECRET_ACCESS_KEY" ]; then
  echo "R2 secrets not set — skipping R2 $MODE (using git branch + cache only)"
  exit 0
fi

command -v rclone >/dev/null 2>&1 || curl -s https://rclone.org/install.sh | sudo bash
mkdir -p ~/.config/rclone
cat > ~/.config/rclone/rclone.conf <<CONF
[r2]
type = s3
provider = Cloudflare
access_key_id = $R2_ACCESS_KEY_ID
secret_access_key = $R2_SECRET_ACCESS_KEY
endpoint = https://$R2_ACCOUNT_ID.r2.cloudflarestorage.com
region = auto
CONF

if [ "$MODE" = "restore" ]; then
  echo "Restoring workspace from R2 s3://$R2_BUCKET/workspace ..."
  rclone copy "r2:$R2_BUCKET/workspace" workspace --transfers 4 --checkers 4 --stats-one-line 2>&1 | tail -n 20 || echo "R2 restore: no existing data or empty bucket"
  ls -lh workspace 2>&1 | head -n 20
  echo "R2 restore done"
else
  rclone sync workspace "r2:$R2_BUCKET/workspace" --transfers 4 --stats-one-line 2>&1 | tail -n 20
  echo "R2 sync done to s3://$R2_BUCKET/workspace"
fi
