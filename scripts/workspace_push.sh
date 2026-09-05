#!/bin/sh
# Push workspace snapshot to orphan branch `workspace-data`.
set -e
if [ -d workspace ] && [ "$(ls -A workspace 2>/dev/null)" ]; then
  git config user.name "rdp-bot"
  git config user.email "bot@rdp.local"
  git fetch origin workspace-data 2>/dev/null || true
  if git show-ref --verify --quiet refs/remotes/origin/workspace-data; then
    git checkout workspace-data 2>/dev/null || git checkout -b workspace-data origin/workspace-data
  else
    git checkout --orphan workspace-data 2>/dev/null || git checkout -b workspace-data
  fi
  mkdir -p workspace
  git add workspace -f
  git diff --cached --quiet || git commit -m "workspace snapshot $(date -u +%Y-%m-%dT%H:%MZ) run ${GITHUB_RUN_NUMBER:-local}" || true
  git push -f origin workspace-data 2>&1 | tail -n 5
  git checkout main 2>/dev/null || git checkout -
else
  echo "workspace empty, skipping git push"
fi
