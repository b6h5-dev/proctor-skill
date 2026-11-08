#!/bin/bash
#
# Log a proctor quiz result to ~/.proctor/history.jsonl
#
# Usage: proctor-log.sh '<json-entry>'
# Example: proctor-log.sh '{"timestamp":"2024-01-01T00:00:00Z","repo":"/path","branch":"main",...}'
#
# The JSON entry is appended as a single line. The caller is responsible
# for constructing valid JSON.

set -euo pipefail

ENTRY="${1:-}"
if [ -z "$ENTRY" ]; then
  echo "Usage: proctor-log.sh '<json-entry>'" >&2
  exit 1
fi

mkdir -p ~/.proctor
printf '%s\n' "$ENTRY" >> ~/.proctor/history.jsonl
