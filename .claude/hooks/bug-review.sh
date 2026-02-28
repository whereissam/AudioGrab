#!/bin/bash
# Bug review hook — runs after git commit (PostToolUse)
# Launches headless claude -p to review the commit, with progress spinner
# Saves review to file, returns short JSON so Claude reads + presents it

set -euo pipefail

COMMIT_HASH=$(git rev-parse HEAD 2>/dev/null)
if [ -z "$COMMIT_HASH" ]; then
  exit 0
fi

DIFF_CMD="git diff ${COMMIT_HASH}~1 ${COMMIT_HASH}"
COMMIT_INFO=$(git log -1 --oneline "$COMMIT_HASH" 2>/dev/null)
CHANGED_FILES=$($DIFF_CMD --name-only 2>/dev/null | grep -E '\.(py|ts|tsx|js|jsx|rs|swift)$' || true)

if [ -z "$CHANGED_FILES" ]; then
  exit 0
fi

FILE_COUNT=$(echo "$CHANGED_FILES" | wc -l | tr -d ' ')
DIFF_LINES=$($DIFF_CMD --stat 2>/dev/null | tail -1 | grep -oE '[0-9]+ insertion|[0-9]+ deletion' | awk '{s+=$1} END{print s+0}')
FILE_LIST=$(echo "$CHANGED_FILES" | sed 's/^/  - /')

REVIEW_FILE="/tmp/bug-review-commit.md"

# Progress spinner (writes to stderr)
spin_pid=""
claude_pid=""
PROMPT_FILE=""
REVIEW_TMPFILE=""
start_spinner() {
  local frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
  local start_time=$SECONDS
  while true; do
    local elapsed=$(( SECONDS - start_time ))
    local mins=$(( elapsed / 60 ))
    local secs=$(( elapsed % 60 ))
    for frame in "${frames[@]}"; do
      printf "\r  ${frame} Bug review: ${FILE_COUNT} files, ~${DIFF_LINES} lines... %dm%02ds (Ctrl+C to cancel)" "$mins" "$secs" >&2
      sleep 0.1
      elapsed=$(( SECONDS - start_time ))
      mins=$(( elapsed / 60 ))
      secs=$(( elapsed % 60 ))
    done
  done
}
stop_spinner() {
  if [ -n "$spin_pid" ]; then
    kill "$spin_pid" 2>/dev/null || true
    wait "$spin_pid" 2>/dev/null || true
    printf "\r%80s\r" "" >&2
    spin_pid=""
  fi
}
cleanup() {
  stop_spinner
  if [ -n "$claude_pid" ]; then
    kill "$claude_pid" 2>/dev/null || true
    kill -- -"$claude_pid" 2>/dev/null || true
    wait "$claude_pid" 2>/dev/null || true
    claude_pid=""
  fi
  rm -f "$PROMPT_FILE" "$REVIEW_TMPFILE"
}
abort() {
  printf "\r%80s\r" "" >&2
  echo "Bug review cancelled." >&2
  cleanup
  exit 130
}
trap cleanup EXIT
trap abort INT TERM

# Build prompt
PROMPT_FILE=$(mktemp)
REVIEW_TMPFILE=$(mktemp)

cat > "$PROMPT_FILE" <<EOF
You are a senior code reviewer performing a bug review on a git commit.

Commit: ${COMMIT_INFO}

Changed files:
${FILE_LIST}

Instructions:
1. Run \`$DIFF_CMD\` to see the full diff
2. For each changed code file, also read the full file to understand context

3. **Trace the dependency chain** — this is critical:
   a. For every function/type/interface that was ADDED, CHANGED, or REMOVED:
      - Use Grep to find all callers and importers across the codebase
      - Read those caller files to check if the change breaks them
   b. For every changed function signature (params added/removed/retyped):
      - Verify ALL call sites pass the correct arguments
   c. For changed types/interfaces:
      - Check all files that import or implement them
   d. For changed API routes or response shapes:
      - Check frontend code that calls those endpoints
   e. For changed DB queries or schema:
      - Check all services that read/write those tables or columns

4. Check the changed code itself for:
   - Logic bugs, off-by-one errors, null/undefined handling
   - Missing error handling or uncaught exceptions
   - Security issues (injection, XSS, exposed secrets, path traversal)
   - Race conditions, deadlocks, or async/await issues
   - Type mismatches or wrong API contracts between frontend and backend
   - Broken imports or missing dependencies
   - Edge cases not handled

5. Output a structured review:

## Bug Review: ${COMMIT_INFO}

### Issues Found
(list each issue with severity: critical/warning/info, file, line, and description)

### Chain Reaction Risks
(issues in RELATED files — callers, importers, downstream consumers — that break due to these changes)

### Verdict
(CLEAN / NEEDS ATTENTION / HAS BUGS)

If no issues found, say the code looks clean and explain why you are confident.
EOF

# Run headless review with spinner
start_spinner &
spin_pid=$!

claude -p "$(cat "$PROMPT_FILE")" --allowedTools "Bash(git diff*),Bash(git log*),Bash(git show*),Read,Glob,Grep" --max-turns 25 2>/dev/null > "$REVIEW_TMPFILE" &
claude_pid=$!

wait "$claude_pid" 2>/dev/null || true
claude_pid=""

stop_spinner

# Save review to file
cp "$REVIEW_TMPFILE" "$REVIEW_FILE"
rm -f "$REVIEW_TMPFILE"
REVIEW_TMPFILE=""

# Return short JSON — Claude reads the file and presents it
jq -n --arg file "$REVIEW_FILE" \
  '{
    decision: "block",
    reason: ("Bug review complete (" + $file + "). Read this file and present the review findings to the user as formatted markdown.")
  }'

exit 0
