#!/usr/bin/env bash
# Hook: stop/session-wrap.sh
# Fires at the end of every Claude Code session.
# 1. Archives completed tasks from docs/PLAN.md ## Done to .claude/archive/YYYY-MM.md
# 2. Warns if docs/PLAN.md ## Active is getting long
# 3. Flags docs/CONTEXT.md as stale if /save was not run this session

set -euo pipefail

PLAN="docs/PLAN.md"
ARCHIVE_DIR=".claude/archive"
ARCHIVE_FILE="$ARCHIVE_DIR/$(date +%Y-%m).md"

# --- Archive completed tasks ---

if [[ ! -f "$PLAN" ]]; then
  exit 0
fi

DONE_CONTENT=$(awk '/^## Done/{found=1; next} found && /^## /{exit} found{print}' "$PLAN")
DONE_CONTENT=$(echo "$DONE_CONTENT" | sed '/./,$!d' | sed -e :a -e '/^\s*$/{ $d; N; ba }')

if [[ -n "$DONE_CONTENT" ]]; then
  mkdir -p "$ARCHIVE_DIR"
  {
    echo ""
    echo "## Archived $(date +%Y-%m-%d)"
    echo "$DONE_CONTENT"
  } >> "$ARCHIVE_FILE"

  awk '
    /^## Done/ { print; in_done=1; next }
    in_done && /^## / { in_done=0 }
    !in_done { print }
  ' "$PLAN" > "$PLAN.tmp" && mv "$PLAN.tmp" "$PLAN"

  echo "[session-wrap] Archived $(echo "$DONE_CONTENT" | grep -c '^\- \[x\]' || true) completed task(s) to $ARCHIVE_FILE"
fi

# --- Warn if Active section is long ---

ACTIVE_COUNT=$(awk '/^## Active/{found=1; next} found && /^## /{exit} found && /^\- /{print}' "$PLAN" | wc -l | tr -d ' ')

if [[ "$ACTIVE_COUNT" -gt 10 ]]; then
  echo "[session-wrap] Warning: docs/PLAN.md ## Active has $ACTIVE_COUNT items. Consider moving lower-priority items to ## Backlog."
fi

# --- Check if CONTEXT.md was updated this session ---

CONTEXT="docs/CONTEXT.md"
TODAY=$(date +%Y-%m-%d)

if [[ -f "$CONTEXT" ]]; then
  if ! grep -q "wrapped: $TODAY" "$CONTEXT" 2>/dev/null; then
    echo "[session-wrap] docs/CONTEXT.md was not updated this session. Run /save before your next session to keep context fresh."
  fi
fi
