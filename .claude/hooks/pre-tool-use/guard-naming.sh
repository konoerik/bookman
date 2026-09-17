#!/usr/bin/env bash
# Hook: pre-tool-use/guard-naming.sh
# Fires before file edits/writes. Blocks creation of non-canonical doc files.

set -euo pipefail

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null || true)

if [[ "$TOOL_NAME" != "Write" && "$TOOL_NAME" != "Edit" ]]; then
  exit 0
fi

FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null || true)
BASENAME=$(basename "$FILE_PATH")
BASENAME_LOWER=$(echo "$BASENAME" | tr '[:upper:]' '[:lower:]')

if [[ "$BASENAME_LOWER" =~ ^(backlog|tasks?|todos?|notes?)\.md$ ]]; then
  echo "Blocked: '$BASENAME' is not a canonical filename. Use PLAN.md with ## Active and ## Backlog sections instead." >&2
  exit 1
fi
