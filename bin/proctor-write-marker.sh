#!/bin/bash
#
# Write a proctor quiz-pass marker.
#
# Usage: proctor-write-marker.sh <marker-name>
# Example: proctor-write-marker.sh push-main
#          proctor-write-marker.sh merge-feature--foo-into-develop
#
# Markers store the HEAD commit hash (line 1) and a diff content hash (line 2).
# The hook checks both — the commit hash is the fast path, the diff hash
# handles content-preserving rebases.

set -euo pipefail

MARKER_DIR="${PROCTOR_MARKER_DIR:-$HOME/.proctor/markers}"
mkdir -p "$MARKER_DIR"

# Migrate markers from legacy /tmp/proctor/ on first use
if [ -d "/tmp/proctor" ] && [ "$MARKER_DIR" != "/tmp/proctor" ]; then
  for legacy in /tmp/proctor/*; do
    [ -f "$legacy" ] || continue
    dest="$MARKER_DIR/$(basename "$legacy")"
    [ -f "$dest" ] || mv "$legacy" "$dest" 2>/dev/null || true
  done
  rmdir /tmp/proctor 2>/dev/null || true
fi

MARKER_NAME="${1:-}"
if [ -z "$MARKER_NAME" ]; then
  echo "Usage: proctor-write-marker.sh <marker-name>" >&2
  exit 1
fi

MERGE_BASE=$(git merge-base HEAD develop 2>/dev/null || git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null || echo "")
CURRENT_HEAD=$(git rev-parse HEAD 2>/dev/null || echo "")
DIFF_HASH=""
if [ -n "$MERGE_BASE" ] && [ "$MERGE_BASE" != "$CURRENT_HEAD" ]; then
  DIFF_HASH=$(git diff "$MERGE_BASE" HEAD | git hash-object --stdin)
fi

printf '%s\n%s\n' "$CURRENT_HEAD" "$DIFF_HASH" > "$MARKER_DIR/$MARKER_NAME"
