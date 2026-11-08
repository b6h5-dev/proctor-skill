#!/bin/bash
#
# Uninstall proctor-skill from a project or globally.
#
# Usage:
#   bash uninstall.sh                              # uninstall from current project (Claude Code)
#   bash uninstall.sh /path/to/project             # uninstall from a specific project
#   bash uninstall.sh --global                     # uninstall globally (~/.claude)
#   bash uninstall.sh --copilot                    # uninstall Copilot from current project
#   bash uninstall.sh --copilot /path/to/project   # uninstall Copilot from a specific project
#   bash uninstall.sh --copilot --global           # uninstall Copilot globally (~/.copilot)

set -euo pipefail

COPILOT=false
GLOBAL=false
PROJECT_DIR=""

print_usage() {
  local cmd
  cmd=$(basename "$0")
  [ "$cmd" = "proctor-skill" ] && cmd="proctor-skill uninstall" || cmd="bash uninstall.sh"
  echo "Usage:"
  echo "  $cmd                              # uninstall from current project (Claude Code)"
  echo "  $cmd /path/to/project             # uninstall from a specific project"
  echo "  $cmd --global                     # uninstall globally (~/.claude)"
  echo "  $cmd --copilot                    # uninstall Copilot from current project"
  echo "  $cmd --copilot /path/to/project   # uninstall Copilot from a specific project"
  echo "  $cmd --copilot --global           # uninstall Copilot globally (~/.copilot)"
}

for arg in "$@"; do
  case "$arg" in
    --copilot) COPILOT=true ;;
    --global) GLOBAL=true ;;
    --help|-h) print_usage; exit 0 ;;
    *) PROJECT_DIR="$arg" ;;
  esac
done

if [ "$COPILOT" = true ]; then
  if [ "$GLOBAL" = true ]; then
    TARGET_DIR="$HOME/.copilot"
  else
    PROJECT_DIR="${PROJECT_DIR:-.}"
    TARGET_DIR="$PROJECT_DIR/.github"
  fi
  echo "Uninstalling proctor (Copilot) from $TARGET_DIR"
else
  if [ "$GLOBAL" = true ]; then
    TARGET_DIR="$HOME/.claude"
  else
    PROJECT_DIR="${PROJECT_DIR:-.}"
    TARGET_DIR="$PROJECT_DIR/.claude"
  fi
  echo "Uninstalling proctor from $TARGET_DIR"
fi

for f in proctor.sh proctor-write-marker.sh proctor-log.sh; do
  if [ -f "$TARGET_DIR/hooks/$f" ]; then
    rm "$TARGET_DIR/hooks/$f"
    echo "  Removed hooks/$f"
  fi
done

if [ "$COPILOT" = true ]; then
  if [ -f "$TARGET_DIR/hooks/proctor.json" ]; then
    rm "$TARGET_DIR/hooks/proctor.json"
    echo "  Removed hooks/proctor.json"
  fi
  rmdir "$TARGET_DIR/hooks" 2>/dev/null && echo "  Removed empty hooks/" || true
else
  rmdir "$TARGET_DIR/hooks" 2>/dev/null && echo "  Removed empty hooks/" || true
fi

if [ -d "$TARGET_DIR/skills/proctor" ]; then
  rm -r "$TARGET_DIR/skills/proctor"
  echo "  Removed skills/proctor/"
  rmdir "$TARGET_DIR/skills" 2>/dev/null && echo "  Removed empty skills/" || true
fi

if [ "$COPILOT" = false ]; then
  SETTINGS_FILE="$TARGET_DIR/settings.json"
  if [ -f "$SETTINGS_FILE" ]; then
    python3 -c "
import json
from pathlib import Path
data = json.loads(Path('$SETTINGS_FILE').read_text())
pre = data.get('hooks', {}).get('PreToolUse', [])
data['hooks']['PreToolUse'] = [
    h for h in pre
    if not any('proctor' in hk.get('command', '') for hk in h.get('hooks', []))
]
if not data['hooks']['PreToolUse']:
    del data['hooks']['PreToolUse']
if not data.get('hooks'):
    del data['hooks']
# Remove proctor permission rules
allow = data.get('permissions', {}).get('allow', [])
data.setdefault('permissions', {})['allow'] = [
    p for p in allow if 'proctor' not in p
]
if not data['permissions']['allow']:
    del data['permissions']['allow']
if not data.get('permissions'):
    del data['permissions']
if data:
    Path('$SETTINGS_FILE').write_text(json.dumps(data, indent=2) + '\n')
    print('  Removed hook and permissions from settings.json')
else:
    Path('$SETTINGS_FILE').unlink()
    print('  Removed empty settings.json')
"
  fi
fi

# Clean up markers from both legacy and new locations
rm -r /tmp/proctor 2>/dev/null && echo "  Cleaned up legacy marker files (/tmp/proctor)" || true
rm -r "$HOME/.proctor/markers" 2>/dev/null && echo "  Cleaned up marker files (~/.proctor/markers)" || true

echo ""
echo "Done! Proctor has been removed."
