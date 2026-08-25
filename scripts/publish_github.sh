#!/bin/sh
set -eu

REPOSITORY="taing77/public-data-alpha-engine"
GH_VERSION="2.97.0"
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PUBLISH_TMP=$(mktemp -d)
ARCHIVE="gh_${GH_VERSION}_macOS_amd64.zip"
RELEASE_BASE="https://github.com/cli/cli/releases/download/v${GH_VERSION}"

cleanup() {
  git -C "$PROJECT_DIR" worktree prune >/dev/null 2>&1 || true
}
trap cleanup EXIT

curl -fsSL "$RELEASE_BASE/$ARCHIVE" -o "$PUBLISH_TMP/$ARCHIVE"
curl -fsSL "$RELEASE_BASE/gh_${GH_VERSION}_checksums.txt" -o "$PUBLISH_TMP/checksums.txt"

EXPECTED=$(awk -v name="$ARCHIVE" '$2 == name {print $1}' "$PUBLISH_TMP/checksums.txt")
ACTUAL=$(shasum -a 256 "$PUBLISH_TMP/$ARCHIVE" | awk '{print $1}')
if [ -z "$EXPECTED" ] || [ "$EXPECTED" != "$ACTUAL" ]; then
  echo "GitHub CLI checksum verification failed" >&2
  exit 1
fi

ditto -x -k "$PUBLISH_TMP/$ARCHIVE" "$PUBLISH_TMP/gh"
GH_BIN=$(find "$PUBLISH_TMP/gh" -type f -path '*/bin/gh' -print -quit)
if [ -z "$GH_BIN" ]; then
  echo "GitHub CLI binary not found in verified archive" >&2
  exit 1
fi

if ! "$GH_BIN" auth status --hostname github.com >/dev/null 2>&1; then
  "$GH_BIN" auth login --hostname github.com --git-protocol https --web --skip-ssh-key
fi

LOGIN=$("$GH_BIN" api user --jq .login)
if [ "$LOGIN" != "taing77" ]; then
  echo "Authenticated GitHub account is '$LOGIN', expected 'taing77'. No repository was created." >&2
  exit 1
fi

if "$GH_BIN" repo view "$REPOSITORY" >/dev/null 2>&1; then
  echo "Repository already exists: $REPOSITORY" >&2
  exit 1
fi

cd "$PROJECT_DIR"
"$GH_BIN" repo create "$REPOSITORY" \
  --public \
  --description "Opportunity Foundry Public Data Alpha Engine and Seoul realtime time-axis seed" \
  --source . \
  --remote origin \
  --push

DATA_WORKTREE="$PUBLISH_TMP/data-branch"
git worktree add --detach "$DATA_WORKTREE" main
cd "$DATA_WORKTREE"
git switch --orphan data
cp "$PROJECT_DIR/docs/data_branch_README.md" README.md
git add README.md
git commit -m "Initialize time-axis asset branch"
git push origin data

"$GH_BIN" workflow run collect-seoul.yml --repo "$REPOSITORY" --ref main
echo "Repository created and first sample collection dispatched: https://github.com/$REPOSITORY"

