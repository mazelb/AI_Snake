#!/usr/bin/env python3
"""
Merge dev-flow's shipped settings into a project's `.claude/settings.json`.

`bootstrap.sh` calls this instead of copying the file or giving up when one
exists. What gets merged is data, in `assets/settings.hook.json`: the hooks,
the tier-1 deny rules (DR1), `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` and
`"autoMemoryEnabled": false` (DR2). This script knows how to merge, not what.

The rules:

  - **Hooks, one entry at a time, by identity.** A hook that runs a script under
    `.claude/hooks/` is identified by the script's name within its event
    (`PreToolUse acceptance-guard.sh`); any other hook by its command. A shipped
    hook already present is left exactly as it is, even when its matcher or
    timeout differ from the shipped one (a WARNING, `kept`), so a project that
    diverged keeps its divergence. A missing one is appended as a group of its
    own; the project's own groups are never edited.
  - **`--update-hooks`** (bootstrap.sh's flag of the same name, DECISIONS.md B4)
    is how a project wired before a shipped matcher or timeout changed picks the
    change up: an existing entry for a hook script dev-flow ships gets the
    shipped matcher and timeout, each change printed, after the same backup, and
    `--dry-run` shows it without doing it. Nothing else in the entry changes, and
    hooks dev-flow does not ship are never touched: when one shares the entry's
    group, the entry moves to a group of its own, so that hook keeps its matcher.
  - **Permission lists** (`permissions.deny`, ...): each missing rule is
    appended; nothing is removed or reordered.
  - **`env` and top-level settings:** set to the shipped value, and reported
    with the old value when there was one. These are the decisions themselves
    (DR1, DR2), so a project value that contradicts them is replaced, visibly.
  - **Every other key is left alone.** `statusLine`, `model`, the project's own
    hooks, `permissions.allow` and the rest come through unchanged.

It fails closed. A settings file that is not valid JSON, has a duplicate key or a
byte-order mark, is not an object, or has the wrong shape where the merge has to
write, is refused with exit 1 and left untouched; nothing is written. So is
shipped data carrying a machine-specific absolute path: those belong in
`.claude/settings.local.json`, which stays out of version control, and this
script never writes that file. It only reads it, to warn when it would override
a merged setting on this machine (it takes precedence over `settings.json`).

Before changing an existing file it copies it to `settings.json.bak-<UTC time>`
beside it, then writes through a temporary file and a rename. A re-run that
has nothing to add writes nothing at all. The indentation and line endings of
the existing file are kept; other formatting (escapes, number spellings) is
re-serialised by Python's `json`.

Usage:
    python3 settings_merge.py SHIPPED TARGET            merge, printing each change
    python3 settings_merge.py SHIPPED TARGET --dry-run  print each change, write nothing
    python3 settings_merge.py SHIPPED TARGET --check    only check both files can be merged
    ... --update-hooks   also give existing entries for shipped hook scripts the
                         shipped matcher and timeout (combines with --dry-run)

Exit codes: 0 merged, nothing to do, or checked; 1 refused (nothing written).
"""

from __future__ import annotations

import argparse
import copy
import datetime
import json
import os
import re
import shutil
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

HOOK_SCRIPT_RE = re.compile(r"\.claude[/\\]hooks[/\\]([A-Za-z0-9_.-]+)")
# A string that names a place on one machine: a POSIX home or mount, or a
# Windows drive. `~/...` and `$CLAUDE_PROJECT_DIR/...` are portable and allowed.
MACHINE_PATH_RE = re.compile(r"""(?:^|[\s"'(=:])(?:/Users/|/home/|/mnt/[A-Za-z]/|/[A-Za-z]/|[A-Za-z]:[\\/])""")


class Refused(Exception):
    """The merge cannot be done safely; nothing may be written."""


def say(verb: str, text: str = "") -> None:
    print(f"  {verb:<13} {text}".rstrip())


# --- loading ------------------------------------------------------------------

def _no_duplicates(pairs):
    seen: dict = {}
    for key, value in pairs:
        if key in seen:
            raise Refused(f"duplicate key {key!r}")
        seen[key] = value
    return seen


def load_object(path: Path, label: str) -> tuple[dict, str]:
    """Parse a settings file strictly. Returns the object and its text."""
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise Refused(f"{label} cannot be read ({e.strerror})")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise Refused(f"{label} is not UTF-8 text")
    if text.startswith("﻿"):
        raise Refused(f"{label} starts with a byte-order mark")
    try:
        obj = json.loads(text, object_pairs_hook=_no_duplicates)
    except json.JSONDecodeError as e:
        raise Refused(f"{label} is not valid JSON (line {e.lineno}, column {e.colno}: {e.msg})")
    except Refused as e:
        raise Refused(f"{label} has a {e}")
    if not isinstance(obj, dict):
        raise Refused(f"{label} is not a JSON object at the top level")
    return obj, text


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def check_shipped(shipped: dict) -> None:
    """The shipped data must be in a shape this script knows how to merge."""
    for key, value in shipped.items():
        if key == "hooks":
            if not isinstance(value, dict):
                raise Refused("shipped `hooks` is not an object")
            for event, groups in value.items():
                if not isinstance(groups, list) or not all(
                        isinstance(g, dict) and isinstance(g.get("hooks"), list)
                        and all(isinstance(h, dict) for h in g["hooks"]) for g in groups):
                    raise Refused(f"shipped `hooks.{event}` is not a list of hook groups")
        elif key == "permissions":
            if not isinstance(value, dict) or not all(
                    isinstance(v, list) and all(isinstance(r, str) for r in v)
                    for v in value.values()):
                raise Refused("shipped `permissions` must map each key to a list of rules")
        elif key == "env":
            if not isinstance(value, dict) or not all(isinstance(v, str) for v in value.values()):
                raise Refused("shipped `env` must map each name to a string")
        elif isinstance(value, (dict, list)):
            raise Refused(f"shipped key {key!r} is an object or list this script cannot merge")
    for s in _strings(shipped):
        if MACHINE_PATH_RE.search(s):
            raise Refused(f"shipped data contains a machine-specific path ({s!r}); "
                          "that belongs in .claude/settings.local.json, not settings.json")


def check_target_shape(target: dict, shipped: dict, label: str) -> None:
    """Where the merge writes, the project's file must have the expected types."""
    if "hooks" in shipped and "hooks" in target:
        hooks = target["hooks"]
        if not isinstance(hooks, dict):
            raise Refused(f"{label}: `hooks` is not an object")
        for event in shipped["hooks"]:
            if event not in hooks:
                continue
            groups = hooks[event]
            if not isinstance(groups, list):
                raise Refused(f"{label}: `hooks.{event}` is not a list")
            for i, g in enumerate(groups):
                if not isinstance(g, dict):
                    raise Refused(f"{label}: `hooks.{event}[{i}]` is not an object")
                inner = g.get("hooks", [])
                if not isinstance(inner, list) or not all(isinstance(h, dict) for h in inner):
                    raise Refused(f"{label}: `hooks.{event}[{i}].hooks` is not a list of objects")
    if "permissions" in shipped and "permissions" in target:
        perms = target["permissions"]
        if not isinstance(perms, dict):
            raise Refused(f"{label}: `permissions` is not an object")
        for key in shipped["permissions"]:
            if key in perms and not isinstance(perms[key], list):
                raise Refused(f"{label}: `permissions.{key}` is not a list")
    if "env" in shipped and "env" in target and not isinstance(target["env"], dict):
        raise Refused(f"{label}: `env` is not an object")


# --- merging ------------------------------------------------------------------

def hook_identity(event: str, hook: dict) -> tuple[str, str]:
    command = hook.get("command")
    if isinstance(command, str):
        m = HOOK_SCRIPT_RE.search(command)
        return (event, m.group(1) if m else command.strip())
    return (event, json.dumps(hook, sort_keys=True))


def same(a, b) -> bool:
    # `False == 0` in Python; settings are JSON, so compare as JSON.
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def show(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def update_entry(existing: list, have_group: dict, have_hook: dict,
                 group: dict, hook: dict) -> tuple[list[str], dict]:
    """Give an existing entry for a shipped hook script the shipped matcher and
    timeout (DECISIONS.md B4). Returns what changed, and the entry's group now.
    The matcher belongs to the group: when the group also holds other hooks, the
    entry moves to a group of its own, so they keep their matcher."""
    done = []
    if not same(have_hook.get("timeout"), hook.get("timeout")):
        done.append(f"timeout {show(have_hook.get('timeout'))} -> {show(hook.get('timeout'))}")
        if "timeout" in hook:
            have_hook["timeout"] = copy.deepcopy(hook["timeout"])
        else:
            del have_hook["timeout"]
    if not same(have_group.get("matcher"), group.get("matcher")):
        old = show(have_group.get("matcher"))
        if len(have_group.get("hooks", [])) == 1:
            if "matcher" in group:
                have_group["matcher"] = copy.deepcopy(group["matcher"])
            else:
                del have_group["matcher"]
            done.append(f"matcher {old} -> {show(group.get('matcher'))}")
        else:
            inner = have_group["hooks"]
            inner.pop(next(i for i, h in enumerate(inner) if h is have_hook))
            have_group = {k: copy.deepcopy(v) for k, v in group.items() if k != "hooks"}
            have_group["hooks"] = [have_hook]
            existing.append(have_group)
            done.append(f"matcher {old} -> {show(group.get('matcher'))}, in a group of its "
                        f"own (the other hooks in its old group keep {old})")
    return done, have_group


def merge(target: dict, shipped: dict, update_hooks: bool = False
          ) -> tuple[dict, list[tuple[str, str]], list[tuple[str, str]]]:
    """Returns (merged, changes, notes). `target` is not modified.

    With `update_hooks` (bootstrap.sh --update-hooks), an existing entry for a
    shipped hook script takes the shipped matcher and timeout; without it, the
    entry is kept as it is and a note says so."""
    merged = copy.deepcopy(target)
    changes: list[tuple[str, str]] = []
    notes: list[tuple[str, str]] = []

    for key, value in shipped.items():
        if key == "hooks":
            hooks = merged.setdefault("hooks", {})
            for event, groups in value.items():
                existing = hooks.setdefault(event, [])
                present = {}
                for g in existing:
                    for h in g.get("hooks", []):
                        present.setdefault(hook_identity(event, h), (g, h))
                for g in groups:
                    missing = []
                    for h in g["hooks"]:
                        ident = hook_identity(event, h)
                        if ident not in present:
                            missing.append(h)
                            changes.append(("add hook", f"{event} {ident[1]}"))
                            continue
                        have_group, have_hook = present[ident]
                        if update_hooks:
                            done, have_group = update_entry(existing, have_group, have_hook, g, h)
                            changes += [("update hook", f"{event} {ident[1]}: {d}") for d in done]
                        diffs, updatable = [], False
                        if not same(have_group.get("matcher"), g.get("matcher")):
                            updatable = True
                            diffs.append(f"matcher {show(have_group.get('matcher'))}, "
                                         f"shipped {show(g.get('matcher'))}")
                        for field in sorted(set(h) | set(have_hook)):
                            if not same(have_hook.get(field), h.get(field)):
                                updatable = updatable or field == "timeout"
                                diffs.append(f"{field} {show(have_hook.get(field))}, "
                                             f"shipped {show(h.get(field))}")
                        if updatable:
                            diffs.append("bootstrap.sh --update-hooks takes the shipped "
                                         "matcher and timeout")
                        if diffs:
                            notes.append(("kept", f"{event} {ident[1]} as it is: "
                                          + "; ".join(diffs)))
                    if missing:
                        group = {k: copy.deepcopy(v) for k, v in g.items() if k != "hooks"}
                        group["hooks"] = copy.deepcopy(missing)
                        existing.append(group)
        elif key == "permissions":
            perms = merged.setdefault("permissions", {})
            for list_key, rules in value.items():
                have = perms.setdefault(list_key, [])
                for rule in rules:
                    if rule not in have:
                        have.append(rule)
                        changes.append((f"add {list_key}", rule))
        elif key == "env":
            env = merged.setdefault("env", {})
            for name, v in value.items():
                if name not in env:
                    changes.append(("set env", f"{name}={v}"))
                elif not same(env[name], v):
                    changes.append(("set env", f"{name}={v} (was {show(env[name])})"))
                env[name] = v
        else:
            if key not in merged:
                changes.append(("set", f"{key}: {show(value)}"))
            elif not same(merged[key], value):
                changes.append(("set", f"{key}: {show(value)} (was {show(merged[key])})"))
            merged[key] = copy.deepcopy(value)

    return merged, changes, notes


def local_overrides(local_path: Path, shipped: dict) -> list[str]:
    """What `settings.local.json` would override on this machine."""
    if not local_path.exists():
        return []
    try:
        local, _ = load_object(local_path, str(local_path.as_posix()))
    except Refused as e:
        return [f"{e}; Claude Code may ignore it, so check it by hand"]
    warnings = []
    for key, value in shipped.items():
        if key in ("hooks", "permissions"):
            continue  # hooks add up across files, and a deny rule anywhere wins
        if key == "env":
            env = local.get("env")
            if isinstance(env, dict):
                for name, v in value.items():
                    if name in env and not same(env[name], v):
                        warnings.append(f"{local_path.as_posix()} sets env {name}={show(env[name])}, "
                                        f"overriding {v} on this machine")
        elif key in local and not same(local[key], value):
            warnings.append(f"{local_path.as_posix()} sets {key}: {show(local[key])}, "
                            f"overriding {show(value)} on this machine")
    return warnings


# --- writing ------------------------------------------------------------------

def style_of(text: str) -> tuple[str | int, str]:
    """Indent unit and newline of an existing file (2 spaces and LF by default)."""
    newline = "\r\n" if "\r\n" in text else "\n"
    m = re.search(r"^([ \t]+)\S", text, re.MULTILINE)
    if not m:
        return 2, newline
    unit = m.group(1)
    return ("\t" if "\t" in unit else len(unit)), newline


def render(obj: dict, indent, newline: str) -> bytes:
    text = json.dumps(obj, indent=indent, ensure_ascii=False) + "\n"
    return text.replace("\n", newline).encode("utf-8")


def backup_path(target: Path) -> Path:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = target.with_name(f"{target.name}.bak-{stamp}")
    n = 1
    while candidate.exists():
        candidate = target.with_name(f"{target.name}.bak-{stamp}-{n}")
        n += 1
    return candidate


def write_atomically(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.dev-flow-tmp")
    tmp.write_bytes(data)
    if target.exists():
        shutil.copymode(target, tmp)
    os.replace(tmp, target)


# --- main ---------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    def error(self, message):  # usage errors exit 1, not argparse's 2
        self.print_usage(sys.stderr)
        print(f"settings_merge.py: {message}", file=sys.stderr)
        sys.exit(1)


def main(argv: list[str] | None = None) -> int:
    p = _Parser(description="Merge dev-flow's shipped settings into .claude/settings.json.")
    p.add_argument("shipped", help="assets/settings.hook.json")
    p.add_argument("target", help="the project's .claude/settings.json (may not exist)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print each change, write nothing")
    mode.add_argument("--check", action="store_true", help="only check the merge can be done")
    p.add_argument("--update-hooks", action="store_true",
                   help="give existing entries for shipped hook scripts the shipped matcher and timeout")
    args = p.parse_args(argv)

    shipped_path, target_path = Path(args.shipped), Path(args.target)
    label = args.target.replace("\\", "/")
    try:
        shipped, _ = load_object(shipped_path, f"the shipped settings ({shipped_path.as_posix()})")
        check_shipped(shipped)
        exists = target_path.exists()
        if exists:
            target, text = load_object(target_path, label)
            check_target_shape(target, shipped, label)
            indent, newline = style_of(text)
        else:
            target, text, indent, newline = {}, "", 2, "\n"
        merged, changes, notes = merge(target, shipped, update_hooks=args.update_hooks)
    except Refused as e:
        say("REFUSED", f"{e}.")
        say("", "Nothing was written. Fix or move the file, then re-run.")
        return 1

    if args.check:
        return 0

    would = "would " if args.dry_run else ""
    for verb, text_ in notes:  # an entry kept although it differs from the shipped one
        say("WARNING", f"{verb} {text_}")
    for warning in local_overrides(target_path.with_name("settings.local.json"), shipped):
        say("WARNING", warning)

    if not changes:
        say("skip (wired)", f"{label} already has every dev-flow setting")
        return 0

    for verb, text_ in changes:
        say(f"{would}{verb}", text_)
    if exists:
        backup = backup_path(target_path)
        if not args.dry_run:
            shutil.copy2(target_path, backup)
        say("would back up" if args.dry_run else "backup", f"{label} -> {backup.name}")
    if not args.dry_run:
        write_atomically(target_path, render(merged, indent, newline))
    say(f"{would}write" if args.dry_run else "wrote",
        f"{label} ({'merged' if exists else 'new'}: {len(changes)} change"
        f"{'' if len(changes) == 1 else 's'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
