#!/usr/bin/env bash
# PostToolUse hook: validate any spec artifact the moment Claude writes or edits it.
# Routes prd.md / plan.md / acceptance.md to their own validators.
#
# Wired to Write|Edit in .claude/settings.json. Claude Code passes the tool call
# as JSON on stdin; the file path is the only reliable place to read it from.
#
# The point of this hook is that nobody has to remember to validate. It also
# translates validator exit codes into the two things the agent should do:
#
#   validator 1 (malformed)  -> hook exit 2, findings on stderr
#                               Claude sees this as blocking feedback and fixes it
#                               without being asked.
#   validator 2 (needs input)-> hook exit 0, note on stdout
#                               Correct state. Must never block, or the agent
#                               learns to invent numbers to clear it.
#   validator 0 (clean)      -> hook exit 0, silent.

set -uo pipefail

INPUT="$(cat)"

if command -v jq >/dev/null 2>&1; then
  FILE="$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')"
else
  FILE="$(printf '%s' "$INPUT" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
fi
# On Windows Claude Code passes a backslashed path (E:\repo\specs\1-x\prd.md), which
# the patterns below never match, so the hook said nothing there. Read each
# backslash as / (the sed route leaves them doubled; // is still a path).
FILE="${FILE//\\//}"

# Only care about spec artifacts. Pick the validator by filename.
case "$FILE" in
  */specs/*/prd.md|specs/*/prd.md)               VALIDATOR_NAME=validate_prd.py ;;
  */specs/*/plan.md|specs/*/plan.md)             VALIDATOR_NAME=validate_plan.py ;;
  */specs/*/acceptance.md|specs/*/acceptance.md) VALIDATOR_NAME=validate_acceptance.py ;;
  */specs/*/delivery.md|specs/*/delivery.md)     VALIDATOR_NAME=validate_delivery.py ;;
  *) exit 0 ;;
esac

[ -f "$FILE" ] || exit 0

VALIDATOR="${CLAUDE_PROJECT_DIR:-.}/.claude/skills/dev-flow/scripts/$VALIDATOR_NAME"
# A missing validator means that layer is not attached (delivery is opt-in), which
# is not an error — the hook simply has nothing to say about this file.
[ -f "$VALIDATOR" ] || exit 0

OUTPUT="$(python3 "$VALIDATOR" "$FILE" 2>&1)"
CODE=$?

case "$CODE" in
  1)
    {
      echo "Spec artifact has structural errors. Fix these before continuing —"
      echo "do not invent values for any [NEEDS INPUT] markers while doing so."
      echo
      echo "$OUTPUT"
    } >&2
    exit 2
    ;;
  2)
    echo "$OUTPUT"
    echo "Artifact is well-formed and blocked on human input. This is the expected"
    echo "state for a first draft — report the blocked items, do not fill them in."
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
