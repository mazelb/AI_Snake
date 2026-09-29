#!/usr/bin/env bash
# PreToolUse hook: stop the agent weakening the checks instead of fixing the code.
#
# Wired to every tool that can write a file or run a command
# (assets/settings.hook.json; build item 27, DECISIONS.md B9):
# Write|Edit|NotebookEdit|Bash|PowerShell|Monitor|Skill. PowerShell (the Windows
# shell tool) and Monitor send their command in `command`, as Bash does, and are
# read the same way, with PowerShell's own writers (Set-Content, Out-File,
# Copy-Item and the rest, and their aliases) added to the list below. NotebookEdit
# is a write (`notebook_path`). A Skill call's `args` can reach the skill's `!`
# lines, so the always-rules apply to them. It blocks, with exit 2:
#
#   Always
#     - `--no-verify` anywhere in a command, and `git commit -n`: they skip the
#       repository's own pre-commit and commit-msg hooks.
#     - Any mention of `core.hooksPath` in a command, and a Write or Edit of
#       .git/config that mentions it: pointing git at another hooks directory
#       switches the same hooks off.
#     - A Write or Edit of specs/<N>-<slug>/prd.md or plan.md that drops a REQ- or
#       TASK- id the file has now. Ids are permanent: a withdrawn requirement is
#       marked [WITHDRAWN] in place, never deleted or renumbered.
#
#   While an issue is being implemented or verified (a .dev-flow-run/implementing-*
#   or verifying-* marker exists; /implement and /verify create them)
#     - A Write or Edit of flow.json (or .flow.json), a lint, format or
#       git-hook config (the list below), or an acceptance.md.
#     - A command that writes one of those: a redirection into it, or sed -i,
#       perl -i, tee, mv, cp, rm, truncate, dd, ln, install, touch, unlink,
#       shred, rsync, or git checkout / restore / rm / mv naming it; through
#       PowerShell or Monitor also Set-Content, Add-Content, Clear-Content,
#       Out-File, Tee-Object, Remove-Item, Move-Item, Copy-Item, Rename-Item,
#       New-Item, Set-Item, their aliases, or a .NET file API ([IO.File]::...).
#     - A command that touches .dev-flow-run/ other than to rm a verifying- or
#       authoring- marker, so the implementing marker cannot be removed from
#       inside the session. /verify removes it, in a preprocessing line no hook
#       sees. (Removing an unlock marker only locks, and /acceptance or /harness
#       for one issue may finish while another is being implemented.)
#
# Outside those phases, flow.json and the configs are yours and the agents' to
# edit: /spec-setup fills in flow.json, and /acceptance writes acceptance.md.
# The authoring- marker /acceptance and /harness set is not such a phase
# (DECISIONS.md B8).
#
# The config list is file names that mean "lint or format configuration" in most
# ecosystems. pyproject.toml, setup.cfg, tox.ini, package.json and tsconfig.json
# are left out on purpose: implementing a task legitimately edits them (a new
# dependency, a new path), so blocking them would block the work itself.
#
# Markers are looked up at the root of the working tree, exactly as
# acceptance-guard.sh does (see its header). Plain bash, no jq or any other
# program (DR4): a Write of a 200-task plan.md, the slowest case, took about half
# a second on the Windows box, and a typical call a few hundredths.
#
# A speed bump, not a vault: a script that writes the file (python -c, node -e),
# a variable holding its name, or a change made outside Claude is not seen.

set -uo pipefail
INPUT=''
IFS= read -r -d '' INPUT || true

field() {
  local re="\"$1\"[[:space:]]*:[[:space:]]*\"(([^\"\\\\]|\\\\.)*)\""
  if [[ $INPUT =~ $re ]]; then VALUE=${BASH_REMATCH[1]}; else VALUE=''; fi
}

find_root() {
  local d=$PWD
  while :; do
    if [ -e "$d/.git" ]; then ROOT=$d; return; fi
    if [ -z "$d" ] || [ "$d" = / ]; then break; fi
    d=${d%/*}
  done
  ROOT=${CLAUDE_PROJECT_DIR:-$PWD}
}

phase_active() {
  local f
  for f in "$ROOT"/.dev-flow-run/implementing-* "$ROOT"/.dev-flow-run/verifying-*; do
    [ -e "$f" ] && return 0
  done
  return 1
}

block() {
  printf '%s\n' "$@" >&2
  exit 2
}

# Protected while implementing: a path whose last component is one of these, or
# anything under .husky/ or .git/hooks/. Extended regular expression, matched
# without regard to case.
NAMES='flow\.json|\.flow\.json|acceptance\.md'
NAMES+='|\.eslintrc(\.[a-z]+)?|eslint\.config\.[a-z]+|\.eslintignore'
NAMES+='|\.prettierrc(\.[a-z]+)?|prettier\.config\.[a-z]+|\.prettierignore'
NAMES+='|biome\.jsonc?|\.stylelintrc(\.[a-z]+)?|stylelint\.config\.[a-z]+|tslint\.json|\.oxlintrc\.json|\.?dprint\.json'
NAMES+='|\.flake8|\.?pylintrc|\.?ruff\.toml|\.?mypy\.ini|\.isort\.cfg|\.pre-commit-config\.ya?ml'
NAMES+='|\.rubocop(_todo)?\.yml|\.standard\.yml'
NAMES+='|\.golangci\.(ya?ml|toml|json)'
NAMES+='|\.?rustfmt\.toml|\.?clippy\.toml|\.clang-format|\.clang-tidy'
NAMES+='|\.editorconfig|\.markdownlint(\.[a-z]+|rc)?|\.yamllint(\.ya?ml)?|\.shellcheckrc|\.hadolint\.ya?ml'
NAMES+='|\.?lefthook\.ya?ml|\.lintstagedrc(\.[a-z]+)?|lint-staged\.config\.[a-z]+'
NAMES+='|commitlint\.config\.[a-z]+|\.commitlintrc(\.[a-z]+)?'
NAMES+='|\.swiftlint\.yml|detekt\.yml|checkstyle\.xml|\.scalafmt\.conf'
NAMES+='|\.php-cs-fixer(\.dist)?\.php|phpcs\.xml(\.dist)?|phpstan\.neon(\.dist)?'
NAMES+='|\.credo\.exs|\.formatter\.exs|analysis_options\.yaml'
# A name is protected when it is a whole path component: preceded by the start, a
# separator, whitespace, a quote, `=`, `>`, `:`, `,` or `(` (PowerShell's
# `-Path:x`, `a,b` and `(x)`), and followed by the end, whitespace, a quote, `,`
# or a separator. (\\ is an escaped backslash in the JSON text.)
PROTECTED="(^|[/\\\\[:space:]\"'=>:,(])(${NAMES})([[:space:]\"';&|),]|\\\\|$)|(\\.husky|\\.git[/\\\\]+hooks)[/\\\\]"

# The JSON text escapes a backslash as a pair; a Windows path is read with / instead.
bs='\\'

field tool_name; TOOL=$VALUE

# A command line (Bash, PowerShell, Monitor) or a skill's arguments, in CMD; the
# file a Write, Edit or NotebookEdit changes, in FILE.
CMD='' FILE=''
case "$TOOL" in
  Bash|PowerShell|Monitor) field command; CMD=$VALUE ;;
  Skill)                   field args; CMD=$VALUE ;;
  Write|Edit)              field file_path; FILE=$VALUE ;;
  NotebookEdit)            field notebook_path; FILE=$VALUE ;;
esac

# --- always: hooks are not skipped or redirected -------------------------------------
if [ -n "$CMD" ]; then
  # A newline in the command is \n in the JSON text; treat it as a separator. An
  # escaped backslash (\\, a Windows path separator) is read as / first, so the
  # \t in C:\\tmp or the \n in C:\\new is not taken for a tab or a newline.
  CMD=${CMD//\\\\//}
  CMD=${CMD//\\n/ ; }; CMD=${CMD//\\r/ ; }; CMD=${CMD//\\t/ }
  no_verify='(^|[^[:alnum:]-])--no-verify([^[:alnum:]-]|$)'
  [[ $CMD =~ $no_verify ]] && block \
    "Blocked: --no-verify skips the repository's own git hooks." \
    "If a hook fails, fix what it reports, or tell me it is wrong. Do not skip it."
  # git commit -n is --no-verify's short form, alone or in a cluster (-nm).
  commit_n='(^|[;&|[:space:]])git([[:space:]]+[^;&|[:space:]]+)*[[:space:]]+commit([[:space:]]+[^;&|[:space:]]+)*[[:space:]]+-[[:alpha:]]*n[[:alpha:]]*([[:space:]]|$)'
  [[ $CMD =~ $commit_n ]] && block \
    "Blocked: git commit -n is --no-verify; it skips the repository's own git hooks." \
    "If a hook fails, fix what it reports, or tell me it is wrong. Do not skip it."
fi

shopt -s nocasematch

if [ -n "$CMD" ]; then
  [[ $CMD == *core.hookspath* ]] && block \
    "Blocked: core.hooksPath points git at a different hooks directory, which switches the" \
    "repository's own git hooks off. Leave it as it is."
else
  git_config='(^|[/\\])\.git[/\\]+config$'
  if [[ $FILE =~ $git_config ]] && [[ $INPUT == *hookspath* ]]; then
    block "Blocked: setting hooksPath in .git/config switches the repository's own git hooks off."
  fi
fi

# --- always: requirement and task ids are permanent ----------------------------------
spec_doc='specs[/\\]+[^/\\]+[/\\]+(prd|plan)\.md$'
if { [ "$TOOL" = Write ] || [ "$TOOL" = Edit ]; } && [[ $FILE =~ $spec_doc ]]; then
  path=${FILE//"$bs"//}
  OLD=''
  # $(<file) is read by bash itself; `read -d ''` reads a byte at a time.
  if [ -f "$path" ]; then OLD=$(<"$path"); fi
  if [ -n "$OLD" ]; then
    shopt -u nocasematch
    id_re='(REQ|TASK)-[0-9]+'
    # The distinct ids in $1, as " ID ID ... ", in IDS. The text is split into
    # words first: a regular expression run over the whole of a long plan once per
    # id took most of a second on Windows.
    ids_of() {
      local w id IFS=$' \t\n\r\\"\'`,;:.()[]{}<>|/*#=!?&+~^%@$'
      IDS=' '
      set -f
      for w in $1; do
        case $w in *REQ-[0-9]*|*TASK-[0-9]*) ;; *) continue ;; esac
        while [[ $w =~ $id_re ]]; do
          id=${BASH_REMATCH[0]}; w=${w#*"$id"}
          [[ $IDS == *" $id "* ]] || IDS+="$id "
        done
      done
      set +f
    }
    # How many times the id $1 occurs in $2 (REQ-01 inside REQ-012 does not count).
    occurrences() {
      local w id IFS=$' \t\n\r\\"\'`,;:.()[]{}<>|/*#=!?&+~^%@$'
      COUNT=0
      set -f
      for w in $2; do
        [[ $w == *"$1"* ]] || continue
        while [[ $w =~ $id_re ]]; do
          id=${BASH_REMATCH[0]}; w=${w#*"$id"}
          [ "$id" = "$1" ] && COUNT=$((COUNT + 1))
        done
      done
      set +f
    }
    dropped=''
    if [ "$TOOL" = Write ]; then
      field content; ids_of "$VALUE"; new_ids=$IDS
      ids_of "$OLD"
      for id in $IDS; do
        [[ $new_ids == *" $id "* ]] || dropped+=" $id"
      done
    else
      # Dropped when the edit removes an id and it occurs nowhere else in the file.
      field old_string; GONE=$VALUE; field new_string; ids_of "$VALUE"; new_ids=$IDS
      ids_of "$GONE"
      for id in $IDS; do
        [[ $new_ids == *" $id "* ]] && continue
        occurrences "$id" "$OLD"; in_file=$COUNT
        occurrences "$id" "$GONE"
        [ "$in_file" -le "$COUNT" ] && dropped+=" $id"
      done
    fi
    [ -n "$dropped" ] && block \
      "Blocked: this change removes${dropped} from ${path##*/}." \
      "" \
      "Requirement and task ids are permanent: other artifacts, tests and commits cite them." \
      "Keep the id. Mark a withdrawn requirement or task [WITHDRAWN] in place, and never" \
      "renumber. If an id really must go, that is a decision for the person who owns the spec."
    shopt -s nocasematch
  fi
fi

# --- while implementing: the checks and the cases are not edited ---------------------
case "$TOOL" in
  Write|Edit|NotebookEdit) [[ $FILE =~ $PROTECTED ]] || exit 0 ;;
  Bash|PowerShell|Monitor) [[ $CMD =~ $PROTECTED || $CMD == *dev-flow-run* ]] || exit 0 ;;
  *)                       exit 0 ;;
esac

find_root
phase_active || exit 0

MSG_WHY=(
  ""
  "While an issue is being implemented or verified, flow.json, the lint, format and"
  "git-hook configuration, and the acceptance cases are fixed. Weakening a check to get"
  "a green run hides the failure instead of fixing it. If a check or a case is wrong,"
  "stop and say so; the person who owns it decides."
  ""
  "(For the person: /verify <issue> ends the phase. If no issue is being worked on,"
  "a marker was left behind: delete .dev-flow-run/implementing-* and verifying-* yourself.)"
)

if [ -n "$FILE" ]; then
  block "Blocked: ${FILE//"$bs"//} is protected while an issue is being implemented or verified." "${MSG_WHY[@]}"
fi

# A command line: look at each simple command on its own.
# The marker's own name may not hold a path separator, so no `..` climbs out of
# it; it may end in a closing quote (\" in the JSON text).
w='[^][:space:];&|<>()$`]'
nm='[^][:space:];&|<>()$`/\"'"'"']'
qt='(\\"|'"'"'|")?'
rm_only="^[[:space:]]*(rm|remove-item)([[:space:]]+-[[:alpha:]]+)*([[:space:]]+${w}*(verifying|authoring)-${nm}*${qt})+[[:space:]]*$"
if [[ $CMD == *dev-flow-run* ]] && ! [[ $CMD =~ $rm_only ]]; then
  block "Blocked: .dev-flow-run/ holds the markers the dev-flow stages set; leave it to them." \
        "Removing a verifying- or authoring- marker is allowed as a command of its own."
fi

redirect="(>|>>)[[:space:]]*[\\\\\"']*[^[:space:]\"';&|]*(${PROTECTED})"
writer='(^|[[:space:](])(tee|mv|cp|rm|truncate|dd|ln|install|touch|unlink|shred|rsync)([[:space:]]|$)'
inplace='(^|[[:space:](])(sed|perl)[[:space:]]([^;]*[[:space:]])?(-[[:alpha:]]*i|--in-place)'
gitwrite='(^|[[:space:](])git([[:space:]]+[^[:space:]]+)*[[:space:]]+(checkout|restore|rm|mv)([[:space:]]|$)'
# PowerShell's writers and their aliases (rm, mv, cp and tee are aliases there
# too), and the .NET file APIs a PowerShell line can call directly. Matched only
# for PowerShell and Monitor (which may run either shell), not for Bash.
pswriter='(^|[[:space:](])(set-content|add-content|clear-content|out-file|tee-object|remove-item|move-item|copy-item|rename-item|new-item|set-item|sc|ac|clc|ri|del|erase|rd|rmdir|mi|move|cpi|copy|rni|ren|ni)([[:space:]]|$)'
netwrite='\[(system\.)?io\.(file|fileinfo|directory|streamwriter|filestream)\]|new-object[[:space:]]+(-typename[[:space:]]+)?(system\.)?io\.'
ps=''
[ "$TOOL" = Bash ] || ps=1
s=$CMD; s=${s//&&/;}; s=${s//||/;}; s=${s//|/;}
while :; do
  seg=${s%%;*}
  if [[ $seg =~ $PROTECTED ]]; then
    if [[ $seg =~ $redirect || $seg =~ $writer || $seg =~ $inplace || $seg =~ $gitwrite ]] \
       || { [ -n "$ps" ] && [[ $seg =~ $pswriter || $seg =~ $netwrite ]]; }; then
      block "Blocked: this command changes a file that is protected while an issue is being implemented or verified." "${MSG_WHY[@]}"
    fi
  fi
  [[ $s == *";"* ]] || break
  s=${s#*;}
done
exit 0
