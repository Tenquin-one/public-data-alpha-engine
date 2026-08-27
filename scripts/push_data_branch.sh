#!/usr/bin/env bash
set -euo pipefail

branch="${1:-data}"
max_attempts="${2:-4}"

for ((attempt = 1; attempt <= max_attempts; attempt++)); do
  if git push origin "HEAD:${branch}"; then
    exit 0
  fi

  if ((attempt == max_attempts)); then
    break
  fi

  echo "Data branch advanced; rebasing before push retry ${attempt}/${max_attempts}"
  git fetch --no-tags origin "+refs/heads/${branch}:refs/remotes/origin/${branch}"
  git rebase "origin/${branch}"
done

echo "Unable to push ${branch} after ${max_attempts} attempts" >&2
exit 1
