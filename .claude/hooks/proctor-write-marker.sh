#!/bin/bash
#
# Write a proctor quiz-pass marker.
#
# Usage: proctor-write-marker.sh <marker-name> [repo-path]
# Example: proctor-write-marker.sh push-main
#          proctor-write-marker.sh push-main /Users/me/source/my-project
#
# When repo-path is given, git commands run against that directory.
# When omitted, the current working directory is used.
#
# Markers are scoped per-repo using a hash of the repo root path,
# so push-main in repo A won't collide with push-main in repo B.

set -euo pipefail

MARKER_BASE="${PROCTOR_MARKER_DIR:-$HOME/.proctor/markers}"

MARKER_NAME="${1:-}"
if [ -z "$MARKER_NAME" ]; then
  echo "Usage: proctor-write-marker.sh <marker-name> [repo-path]" >&2
  exit 1
fi

REPO_PATH="${2:-}"
GIT_CMD="git"
if [ -n "$REPO_PATH" ] && [ -d "$REPO_PATH" ]; then
  GIT_CMD="git -C $REPO_PATH"
fi

REPO_ROOT=$($GIT_CMD rev-parse --show-toplevel 2>/dev/null || echo "unknown")
REPO_ID=$(printf '%s' "$REPO_ROOT" | shasum -a 256 | cut -c1-12)
MARKER_DIR="$MARKER_BASE/$REPO_ID"
mkdir -p "$MARKER_DIR"

# Migrate markers from legacy flat directory on first use per-repo
for legacy in "$MARKER_BASE/$MARKER_NAME" "$MARKER_BASE"/checkpoint-*; do
  [ -f "$legacy" ] || continue
  dest="$MARKER_DIR/$(basename "$legacy")"
  [ -f "$dest" ] || mv "$legacy" "$dest" 2>/dev/null || true
done

# Migrate from legacy /tmp/proctor/
if [ -d "/tmp/proctor" ] && [ "$MARKER_DIR" != "/tmp/proctor" ]; then
  for legacy in /tmp/proctor/*; do
    [ -f "$legacy" ] || continue
    dest="$MARKER_DIR/$(basename "$legacy")"
    [ -f "$dest" ] || mv "$legacy" "$dest" 2>/dev/null || true
  done
  rmdir /tmp/proctor 2>/dev/null || true
fi

MERGE_BASE=$($GIT_CMD merge-base HEAD develop 2>/dev/null || $GIT_CMD merge-base HEAD main 2>/dev/null || $GIT_CMD merge-base HEAD master 2>/dev/null || echo "")
CURRENT_HEAD=$($GIT_CMD rev-parse HEAD 2>/dev/null || echo "")
DIFF_HASH=""
if [ -n "$MERGE_BASE" ] && [ "$MERGE_BASE" != "$CURRENT_HEAD" ]; then
  DIFF_HASH=$($GIT_CMD diff "$MERGE_BASE" HEAD | git hash-object --stdin)
fi

printf '%s\n%s\n' "$CURRENT_HEAD" "$DIFF_HASH" > "$MARKER_DIR/$MARKER_NAME"
