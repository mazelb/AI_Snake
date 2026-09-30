#!/usr/bin/env bash
# PreToolUse hook: stop the coding agent reading the acceptance cases.
#
# Acceptance cases are derived from the PRD before code exists. If the agent can
# see them while implementing, it writes code that passes those specific cases
# rather than code that satisfies the requirement they came from — and the tests
# stop being independent evidence.
#
# Wired to every tool that can read a file, run a command or write a file
# (assets/settings.hook.json; build item 27, DECISIONS.md B9):
# Read|Grep|Glob|Bash|PowerShell|Monitor|Write|Edit|NotebookEdit|Skill|DesignSync.
# The PowerShell tool (Windows) and Monitor send their command in `command`, as
# Bash does, and are read the same way: `Get-Content`, `gc`, `cat`, `type`, `-Path`
# or `-LiteralPath` all name the file, so the same checks apply. NotebookEdit is a
# write (`notebook_path`). Skill is read by its `skill` and `args`, where only a
# concrete specs/<N>-<slug>/acceptance.md counts (B13). DesignSync,
# whose input is not documented, by its whole tool input. Every tool the
# Claude Code release offers is classed in tests/test_guards.py (TOOL_CLASSES),
# which fails on a tool it does not know, so a new one cannot slip past unseen.
#
#   Reading   blocked, unless a stage that reads the cases has unlocked issue N
#             and every acceptance.md the call names is
#             `specs/<N>-<slug>/acceptance.md` for an unlocked N. Issue N is
#             unlocked while .dev-flow-run/verifying-<N> or
#             .dev-flow-run/authoring-<N> exists and .dev-flow-run/implementing-<N>
#             does not: `/implement <N>` creates the last and `/verify <N>`
#             removes it, so a stale or forged unlock marker never unlocks an
#             issue that is being implemented. A mention it cannot tie to one issue (a bare
#             `acceptance.md`, `specs/*/acceptance.md`, `acceptance*`) stays
#             blocked, even during /verify. So does a Grep over a spec
#             directory, or over specs/, that could search acceptance.md.
#             Two things are not mentions (build item 28): in a command, a git
#             exclusion pathspec (`':!specs/1-x/acceptance.md'`), which leaves
#             the file out (B12); in a Skill call's arguments, anything but a
#             concrete specs/<N>-<slug>/acceptance.md: the name in prose ("do not
#             read any acceptance.md file") and a glob over every spec ("do not
#             read specs/*/acceptance.md") pass (B13).
#   Unlock    `/verify <N>` touches .dev-flow-run/verifying-<N>, and `/acceptance
#             <N>` and `/harness <N>` touch .dev-flow-run/authoring-<N>, in a
#             preprocessing line (commands/verify.md, acceptance.md, harness.md;
#             DECISIONS.md B8). Preprocessing is not a tool call, so no hook sees
#             it, and it is the only thing that should create one: a tool call
#             that would create a verifying- or authoring- marker is blocked. A
#             plain `rm` of those markers is allowed, since removing one only
#             locks; each stage removes its own that way when it finishes.
#   Writing   Write, Edit or NotebookEdit of an acceptance.md is blocked while any issue is
#             being implemented or verified (a .dev-flow-run/implementing-* or
#             verifying-* marker exists). /acceptance writes the file before
#             that, so it is not blocked: an authoring- marker does not start
#             that phase.
#   The tests /harness generates (build item 30, DECISIONS.md B15) are locked
#             the same way when flow.json's `acceptance_tests` glob is set: a
#             call naming a file that matches it (a concrete path; a word with
#             * or ? only in a Grep's glob or a Glob's pattern) is blocked while
#             any issue is being implemented, and unless a verifying- or
#             authoring- marker exists, since the tests belong to no one issue's
#             directory; a Write, Edit or NotebookEdit of one is blocked during
#             the phase. So is a Grep over the glob's literal leading directory
#             or one holding it (tests/acceptance for tests/acceptance/**). With the
#             key unset or empty, nothing here changes.
#
# Markers are looked up in .dev-flow-run/ at the root of the working tree the
# call runs in: the nearest directory, from the hook's working directory up,
# that holds a `.git` (a worktree has its own). Claude Code runs the hook in the
# session's current directory, which follows a `cd` in Bash, so a plain relative
# path would miss the marker from a subdirectory. Which tree the marker belongs
# in when /implement and /verify run in different worktrees is build item 18's
# decision (DECISIONS.md B5).
#
# Plain bash, no jq, python or any other program, not even a subshell: it runs in
# milliseconds, so a slow process spawn cannot make it time out (DR4). The tool
# input is read as the JSON text Claude Code sends. JSON.stringify escapes only
# quotes, backslashes and control characters, so a path or command can be
# searched as it stands.
#
# This is a speed bump, not a vault. A command that reaches the file without
# naming it (a shell glob, `grep -r` from the repository root, a script that
# opens it, a PowerShell name split by a backtick or built from strings) is not
# seen, and neither are the `!` lines of a skill the model invokes by name: the
# Skill tool's input holds the skill and its arguments, not what they run. Nor is
# a word dressed as an exclusion pathspec and then unwrapped by another program
# (`sed 's/^:!//' <<< ':!specs/…' | xargs cat`), as a name built from strings is
# not. For the generated tests, a shell glob (`cat src/*.acceptance.test.ts`), a
# Grep whose path is not the glob's literal leading directory or one holding it
# (so any Grep, for a glob such as **/*.acceptance.test.*), and running them
# through a command that names no file are not seen either: the project's `test`
# command leaving them out is what covers that last one (B15). It is here to make the boundary explicit and to catch
# the ordinary case, which is the agent helpfully reading every file in the spec
# directory because they were all right there.

set -uo pipefail
INPUT=''
IFS= read -r -d '' INPUT || true

# The first string value of a JSON key, or empty. A key inside a string value
# cannot match: its quotes are escaped.
field() {
  local re="\"$1\"[[:space:]]*:[[:space:]]*\"(([^\"\\\\]|\\\\.)*)\""
  if [[ $INPUT =~ $re ]]; then VALUE=${BASH_REMATCH[1]}; else VALUE=''; fi
}

# The working tree's root: the nearest directory holding .git, else the project.
find_root() {
  local d=$PWD
  while :; do
    if [ -e "$d/.git" ]; then ROOT=$d; return; fi
    if [ -z "$d" ] || [ "$d" = / ]; then break; fi
    d=${d%/*}
  done
  ROOT=${CLAUDE_PROJECT_DIR:-$PWD}
}

# Is an issue being implemented or verified in this tree? The markers that say
# so, as .dev-flow-run/<name>, in MARKERS, so the write block can name them: the
# model may not list .dev-flow-run/ (build item 29).
phase_active() {
  local f
  MARKERS=''
  for f in "$ROOT"/.dev-flow-run/implementing-* "$ROOT"/.dev-flow-run/verifying-*; do
    [ -e "$f" ] && MARKERS+=" .dev-flow-run/${f##*/}"
  done
  [ -n "$MARKERS" ]
}

block() {
  printf '%s\n' "$@" >&2
  exit 2
}

# --- the generated acceptance tests (build item 30, DECISIONS.md B15) -------------
# flow.json's `acceptance_tests` glob, from the first of flow.json, .flow.json and
# .claude/flow.json at ROOT (the order pipeline_config.py reads them in), in
# TESTS_GLOB, made into regular expressions over a path as the JSON text holds it
# once each \\ is read as /. TESTS_RE finds a concrete name matching the glob: a
# word holding * or ? is not one, so a test command's `--exclude
# '**/*.acceptance.test.*'` names nothing. TESTS_WILD lets the name hold * and ?,
# for a pattern that picks the files to read. TESTS_DIR is the glob's literal
# leading directory, if any; TESTS_ALL is 1 when every file under it matches.
# A * or ? matches within one path component, ** any number of them, and a glob
# with no / may match at any depth. All empty when the key is unset or empty.
# This function is the same in acceptance-guard.sh and integrity-guard.sh
# (tests/test_guards.py compares them).
tests_glob() {
  local f raw re g rest comp c i n s w lit=1 all=1
  local pc='[^/\\[:space:]"'"'"'`;&|<>()$=:,'
  local p="${pc}*?]" pw="${pc}]"
  local b='[/\\[:space:]"'"'"'`;&|<>()$=:,]' e='[\\[:space:]"'"'"'`;&|<>()$=:,]'
  TESTS_GLOB='' TESTS_RE='' TESTS_WILD='' TESTS_DIR='' TESTS_ALL=''
  for f in flow.json .flow.json .claude/flow.json; do
    [ -f "$ROOT/$f" ] || continue
    raw=''
    IFS= read -r -d '' raw 2>/dev/null < "$ROOT/$f"
    re='"acceptance_tests"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)"'
    [[ $raw =~ $re ]] && TESTS_GLOB=${BASH_REMATCH[1]}
    break
  done
  g=${TESTS_GLOB//\\\\//}; g=${g//\\\//}
  while [[ $g == ./* ]]; do g=${g#./}; done
  [ -n "$g" ] || return 0
  s='' w='' rest=$g
  while :; do
    comp=${rest%%/*}
    if [[ $rest == */* ]]; then rest=${rest#*/}; n=1; else rest=''; n=0; fi
    if [ -z "$comp" ]; then
      :
    elif [ "$comp" = '**' ]; then
      lit=0
      if [ "$n" = 1 ]; then s+="(${p}+/)*"; w+="(${pw}+/)*"
      else s+="${p}+(/${p}+)*"; w+="${pw}+(/${pw}+)*"; fi
    else
      [[ $comp == *[*?]* ]] && lit=0
      [ "$lit" = 1 ] && [ "$n" = 1 ] && TESTS_DIR+="${TESTS_DIR:+/}$comp"
      [ "$lit" = 0 ] && [[ $comp == *[!*?]* ]] && all=0
      for ((i = 0; i < ${#comp}; i++)); do
        c=${comp:i:1}
        case $c in
          '*') s+="${p}*"; w+="${pw}*" ;;
          '?') s+=$p; w+=$pw ;;
          [[:alnum:]_@%~#-]) s+=$c; w+=$c ;;
          '^') s+='\^'; w+='\^' ;;
          *) s+="[$c]"; w+="[$c]" ;;
        esac
      done
      [ "$n" = 1 ] && { s+=/; w+=/; }
    fi
    [ "$n" = 1 ] || break
  done
  TESTS_RE="(^|${b})${s}(${e}|\$)"
  TESTS_WILD="(^|${b})${w}(${e}|\$)"
  [ -n "$TESTS_DIR" ] && [ "$lit" = 0 ] && [ "$all" = 1 ] && TESTS_ALL=1
  return 0
}

GLOB=''
field tool_name; TOOL=$VALUE
case "$TOOL" in
  Read|Write|Edit) field file_path; TARGET=$VALUE ;;
  NotebookEdit)    field notebook_path; TARGET=$VALUE ;;
  Bash|PowerShell|Monitor)
                   field command; TARGET=$VALUE ;;
  Skill)           field skill; TARGET=$VALUE; field args; TARGET+=" $VALUE" ;;
  Grep)            field path; GREP_PATH=$VALUE; field glob; GLOB=$VALUE; field pattern
                   TARGET="$GREP_PATH $GLOB $VALUE" ;;
  Glob)            field pattern; TARGET=$VALUE; GLOB=$VALUE; field path; TARGET+=" $VALUE" ;;
  # A tool whose input is not documented (DesignSync): the whole tool input.
  *)               TARGET=${INPUT#*'"tool_input"'} ;;
esac

# Paths are case-insensitive on Windows and macOS.
shopt -s nocasematch

# --- the unlock markers are the stages' to create ---------------------------------
if [[ $TARGET == *verifying-* || $TARGET == *authoring-* ]]; then
  case "$TOOL" in
    Write|Edit|NotebookEdit)
      [[ $TARGET == *dev-flow-run* ]] && block \
        "Blocked: the acceptance unlock markers are created by /verify, /acceptance and /harness, not by a tool call." ;;
    Bash|PowerShell|Monitor)
      # Allowed: one rm (in PowerShell also Remove-Item) of files whose names
      # contain verifying- or authoring-, and nothing else. An escaped backslash (\\, a Windows path separator) is
      # read as / first, so the \t in C:\\tmp is not taken for a tab (this match
      # ignores case, so C:\\Temp would be too).
      cmd=${TARGET//\\\\//}
      cmd=${cmd//\\n/ ; }; cmd=${cmd//\\r/ ; }; cmd=${cmd//\\t/ }
      # The marker's own name may not hold a path separator, so no `..` climbs out of
      # it; it may end in a closing quote (\" in the JSON text).
      w='[^][:space:];&|<>()$`]'
      nm='[^][:space:];&|<>()$`/\"'"'"']'
      qt='(\\"|'"'"'|")?'
      rm_only="^[[:space:]]*(rm|remove-item)([[:space:]]+-[[:alpha:]]+)*([[:space:]]+${w}*(verifying|authoring)-${nm}*${qt})+[[:space:]]*$"
      [[ $cmd =~ $rm_only ]] || block \
        "Blocked: the acceptance unlock markers are created by /verify, /acceptance and /harness, not by a tool call." \
        "Removing one is allowed as a command of its own: rm -f .dev-flow-run/verifying-<issue>" \
        "(or authoring-<issue>)." ;;
  esac
fi

# --- a Grep over a spec directory searches acceptance.md without naming it --------
if [ "$TOOL" = Grep ] && [ -n "$GREP_PATH" ]; then
  # Could the search reach a file named acceptance.md? (A brace glob is not
  # expanded here, so it counts as yes.)
  reaches=1
  if [ -n "$GLOB" ] && [[ $GLOB != *'{'* ]]; then
    g=${GLOB##*/}
    # shellcheck disable=SC2053  # the glob is meant as a pattern
    [[ acceptance.md == $g ]] || reaches=0
  fi
  one_spec='specs[/\\]+([0-9]+)-[^/\\]*[/\\]*$'
  all_specs='(^|[/\\])specs[/\\]*$'
  if [ "$reaches" = 1 ]; then
    if [[ $GREP_PATH =~ $one_spec ]]; then
      TARGET+=" specs/${BASH_REMATCH[1]}-x/acceptance.md"
    elif [[ $GREP_PATH =~ $all_specs ]]; then
      TARGET+=" acceptance.md"
    fi
  fi
fi

mention='acceptance(\.md|[*?[])'
case "$TOOL" in
  # --- a git exclusion pathspec leaves the file out; it does not read it (B12) ---
  # `git diff … -- . ':!specs/1-x/acceptance.md'` names the cases only to hide
  # them. Such a word is blanked before the search, so a command whose every
  # mention sits inside one passes, and any other mention in it is still read as
  # a read. tests/judge_review_run.py applies the same rule, and test_guards.py
  # feeds both the same commands (B14): the forms
  # ':!…' ':^…' ':(exclude)…', single- or double-quoted or bare, each a whole shell
  # word (whitespace, one of | & ; ( ) < > or the end on each side; only the word
  # is removed, so a redirection after it is still read) holding no quote, space, backslash, `$`,
  # backtick or shell operator of its own, so it can neither swallow a second
  # mention nor run a command substitution.
  Bash|PowerShell|Monitor)
    s=${TARGET//\\\\//}                     # an escaped backslash (\\) as /, first,
    s=${s//\\n/ ; }; s=${s//\\r/ ; }; s=${s//\\t/ }   # so C:\\new is no newline
    magic=':(!|\^|\(exclude\))'
    body='[^][:space:]'"'"'"\$`;&|<>()]*'
    edge='[[:space:]|&;()<>]'               # what ends a shell word
    xword="${edge}('${magic}${body}'|"'\\"'"${magic}${body}"'\\"'"|${magic}${body})${edge}"
    s=" $s "
    while [[ $s =~ $xword ]]; do        # the word goes; the characters around it stay
      m=${BASH_REMATCH[0]}; s=${s/"$m"/"${m:0:1} ${m: -1}"}
    done
    TARGET=$s ;;
  # --- a Skill's arguments: one issue's cases file, not words (B13) ---------------
  # "do not read any acceptance.md file" and "do not read specs/*/acceptance.md"
  # are what a stage tells a skill it hands work to. Only a path tied to one issue,
  # specs/<N>-<slug>/acceptance.md, counts, and it blocks while issue N is locked.
  Skill) mention='specs[/\\]+[0-9]+-[^/\\[:space:]]*[/\\]+acceptance\.md' ;;
esac

CASES=0
[[ $TARGET =~ $mention ]] && CASES=1

find_root

# --- the generated acceptance tests: locked as the cases are (B15) -----------------
# A call names them when its text holds a concrete path matching flow.json's
# acceptance_tests glob; when a Grep's glob or a Glob's pattern could pick them;
# or when a Grep searches the glob's own directory, one that holds it, or (when
# every file under it is a test) one inside it, as a Grep over a spec directory
# searches acceptance.md.
tests_glob
TESTS=0
if [ -n "$TESTS_RE" ]; then
  if [[ ${TARGET//\\\\//} =~ $TESTS_RE ]]; then
    TESTS=1
  elif { [ "$TOOL" = Grep ] || [ "$TOOL" = Glob ]; } && [[ ${GLOB//\\\\//} =~ $TESTS_WILD ]]; then
    TESTS=1
  elif [ "$TOOL" = Grep ] && [ -n "$TESTS_DIR" ] && [ -n "$GREP_PATH" ]; then
    gp=${GREP_PATH//\\\\//}; gp=${gp%/}
    while [[ $gp == ./* ]]; do gp=${gp#./}; done
    d=$TESTS_DIR
    while :; do
      [[ $gp == "$d" || $gp == */"$d" ]] && TESTS=1
      [[ $d == */* ]] || break
      d=${d%/*}
    done
    [ "$TESTS_ALL" = 1 ] && [[ $gp == "$TESTS_DIR"/* || $gp == */"$TESTS_DIR"/* ]] && TESTS=1
  fi
fi

# --- anything else that names neither the cases nor the tests passes ---------------
[ "$CASES" = 1 ] || [ "$TESTS" = 1 ] || exit 0

if [ "$TOOL" = Write ] || [ "$TOOL" = Edit ] || [ "$TOOL" = NotebookEdit ]; then
  phase_active || exit 0
  [ "$TESTS" = 1 ] && block \
    "Blocked: the acceptance tests /harness generated cannot be written while an issue is being implemented or verified." \
    "" \
    "They match flow.json's acceptance_tests ($TESTS_GLOB) and encode the acceptance cases," \
    "which are frozen against the PRD. If one is wrong, that is a finding for the person" \
    "who owns the PRD: report it, and do not edit the test to match the code." \
    "" \
    "The phase is on because of:${MARKERS}" \
    "(For the person: /verify <issue> ends the phase. If no issue is being worked on," \
    "a marker was left behind: delete it yourself.)"
  block \
    "Blocked: acceptance.md cannot be written while an issue is being implemented or verified." \
    "" \
    "The cases are frozen against the PRD. If one is wrong, that is a finding for the" \
    "person who owns the PRD: report it, and do not edit the case to match the code." \
    "" \
    "The phase is on because of:${MARKERS}" \
    "(For the person: /verify <issue> ends the phase. If no issue is being worked on," \
    "a marker was left behind: delete it yourself.)"
fi

# --- reading the tests: no issue is being implemented, and a stage has unlocked ----
# The tests belong to no one issue's directory, so any implementing- marker locks
# them, and any verifying- or authoring- marker unlocks them otherwise.
if [ "$TESTS" = 1 ]; then
  held='' open=''
  for f in "$ROOT"/.dev-flow-run/implementing-*; do [ -e "$f" ] && held+=" .dev-flow-run/${f##*/}"; done
  for f in "$ROOT"/.dev-flow-run/verifying-* "$ROOT"/.dev-flow-run/authoring-*; do [ -e "$f" ] && open=1; done
  if [ -n "$held" ]; then
    why="An issue is being implemented:${held}."
  elif [ -z "$open" ]; then
    why="No /verify, /acceptance or /harness session has unlocked them."
  fi
  [ -n "$held" ] || [ -z "$open" ] && block \
    "Blocked: the acceptance tests /harness generated are not readable during implementation." \
    "" \
    "$why They match flow.json's acceptance_tests ($TESTS_GLOB)." \
    "" \
    "They spell out the acceptance cases, which were derived from the PRD before any code" \
    "existed and only work as independent evidence if the implementation is written" \
    "without them in view. Read the requirement a task cites in prd.md instead. Your own" \
    "tests are yours to read and run; flow.json's test command leaves these out." \
    "" \
    "Run /verify <issue> when the implementation is complete."
  [ "$CASES" = 1 ] || exit 0
fi

# --- reading: every mention must be one unlocked issue's specs/<N>-*/acceptance.md -
mentions=0 rest=$TARGET
while [[ $rest =~ $mention ]]; do
  mentions=$((mentions + 1)); rest=${rest#*"${BASH_REMATCH[0]}"}
done
issued='specs[/\\]+([0-9]+)-[^/\\[:space:]]*[/\\]+acceptance\.md'
tied=0 locked='' rest=$TARGET
while [[ $rest =~ $issued ]]; do
  tied=$((tied + 1)); n=${BASH_REMATCH[1]}
  if [ -e "$ROOT/.dev-flow-run/implementing-$n" ] \
     || { [ ! -e "$ROOT/.dev-flow-run/verifying-$n" ] && [ ! -e "$ROOT/.dev-flow-run/authoring-$n" ]; }; then
    locked+=" #$n"
  fi
  rest=${rest#*"${BASH_REMATCH[0]}"}
done
if [ "$tied" -eq "$mentions" ] && [ -z "$locked" ]; then
  exit 0
fi

if [ "$tied" -ne "$mentions" ]; then
  why="This call reaches acceptance.md without tying it to one issue's specs/<N>-<slug>/ directory."
else
  why="Not unlocked:${locked} (no /verify session for it, or it is being implemented)."
fi
block \
  "Blocked: acceptance.md is not readable during implementation." \
  "" \
  "$why" \
  "" \
  "These cases were derived from the PRD before any code existed, and they only work" \
  "as independent evidence if the implementation is written without them in view." \
  "" \
  "If you need to know what \"done\" means for a task, read the requirement it cites in" \
  "prd.md. If the requirement is ambiguous, that ambiguity is the actual problem —" \
  "raise it rather than resolving it by reading the tests." \
  "" \
  "Run /verify <issue> when the implementation is complete."
