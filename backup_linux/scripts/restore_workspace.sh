#!/bin/sh
# Restore workspace from git branch (survives cache eviction).
set -e
git fetch origin workspace-data:workspace-data 2>/dev/null || echo "no workspace-data branch yet"
if git show-ref --verify --quiet refs/remotes/origin/workspace-data; then
  echo "Restoring workspace from git branch..."
  git checkout workspace-data -- workspace 2>/dev/null || true
  git archive origin/workspace-data workspace 2>/dev/null | tar -x 2>/dev/null || true
  ls -la workspace 2>&1 | head -n 20
fi
