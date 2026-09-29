#!/usr/bin/env python3
"""
Check a project's Claude Code settings before a CI job lets Claude run.

A `claude -p` run silently ignores a settings file that fails validation: no
error, no warning, and the run goes ahead without it (`claude --help`). The
file is ignored whole, so one wrong value anywhere in it switches off the
acceptance guard, the spec validator, every deny rule and
`autoMemoryEnabled: false` at once. The same is true of a file passed with
`--settings`. This script is the first step of every workflow that runs Claude,
and it fails the job instead.

Two levels, both deterministic:

  static (always)   Needs only Python. `.claude/settings.json` exists and parses
                    strictly (no duplicate key, no byte-order mark, an object at
                    the top level); merging dev-flow's shipped settings into it
                    would change nothing, so every shipped hook, deny rule, `env`
                    value and `autoMemoryEnabled: false` is present (the merge
                    rules are settings_merge.py's, imported, not repeated); the
                    script each shipped hook runs exists under `.claude/hooks/`;
                    and nothing switches hooks off (`disableAllHooks`) or
                    overrides a shipped value from a file that outranks
                    `settings.json` (`settings.local.json`, and each file given
                    with --extra-settings, which the job passes to Claude with
                    `--settings`).

  --doctor          Needs Claude Code installed; run it after the install step
                    and before Claude runs. Claude Code's own schema is the only
                    complete statement of what "fails validation" means, and
                    `claude doctor` reports it without a model call. Its output
                    is text, so the check calibrates itself first: doctor must
                    report a deliberately invalid file, or the check fails
                    (a changed output format cannot turn it into a pass). Then
                    doctor must report no invalid settings for the project, nor
                    for any --extra-settings file.

A hook entry whose matcher or timeout differs from the shipped one is reported
as a warning and passes: settings_merge.py keeps such entries on purpose.

Usage (from the project root, as the workflows run it):
    python3 .claude/skills/dev-flow/scripts/settings_preflight.py \\
        [--extra-settings FILE]... [--doctor] [--project DIR] [--shipped FILE]

Exit codes: 0 the settings will load as shipped; 1 they will not (the job must
stop), or the check itself could not run. It never writes to the project.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import settings_merge as sm  # noqa: E402  (installed beside this script)

SHIPPED_REL = Path(".claude/skills/dev-flow/assets/settings.hook.json")
SETTINGS_REL = Path(".claude/settings.json")
LOCAL_REL = Path(".claude/settings.local.json")
HOOKS_REL = Path(".claude/hooks")

# The deliberately invalid file doctor must report (a string where Claude Code's
# schema wants a number). The key is inert: nothing in dev-flow sets it.
CALIBRATION_KEY = "cleanupPeriodDays"
CALIBRATION = '{\n  "cleanupPeriodDays": "dev-flow preflight calibration"\n}\n'
DOCTOR_TIMEOUT = 180
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

problems: list[str] = []
warnings: list[str] = []


def fail(text: str) -> None:
    problems.append(text)


def warn(text: str) -> None:
    warnings.append(text)


# --- static checks --------------------------------------------------------------

def describe(verb: str, text: str) -> str:
    """Turn a change settings_merge would make into what is wrong now."""
    if verb == "add hook":
        return f"hook missing: {text} (the entry is absent, so this hook never runs)"
    if verb.startswith("add "):
        return f"{verb[4:]} rule missing: {text}"
    if verb == "set env":
        return f"env not as shipped: {text}"
    if verb == "set":
        return f"setting not as shipped: {text}"
    return f"{verb}: {text}"


def overrides(obj: dict, shipped: dict, label: str) -> None:
    """A file that outranks settings.json must not undo a shipped value."""
    if obj.get("disableAllHooks") is True:
        fail(f"{label} sets disableAllHooks: true, which switches every hook off")
    for key, value in shipped.items():
        if key in ("hooks", "permissions"):
            continue  # hooks add up across files, and a deny rule anywhere wins
        if key == "env":
            env = obj.get("env")
            if isinstance(env, dict):
                for name, v in value.items():
                    if name in env and not sm.same(env[name], v):
                        fail(f"{label} sets env {name}={sm.show(env[name])}, "
                             f"overriding {v}")
        elif key in obj and not sm.same(obj[key], value):
            fail(f"{label} sets {key}: {sm.show(obj[key])}, overriding {sm.show(value)}")


def static_checks(project: Path, shipped_path: Path, extras: list[Path]) -> None:
    try:
        shipped, _ = sm.load_object(shipped_path, f"the shipped settings ({shipped_path.as_posix()})")
        sm.check_shipped(shipped)
    except sm.Refused as e:
        fail(f"{e}; there is nothing to check the project against")
        return

    target_path = project / SETTINGS_REL
    label = SETTINGS_REL.as_posix()
    if not target_path.is_file():
        fail(f"{label} does not exist, so Claude would run with no hooks, no deny "
             f"rules and auto memory on")
    else:
        try:
            target, _ = sm.load_object(target_path, label)
            sm.check_target_shape(target, shipped, label)
        except sm.Refused as e:
            fail(f"{e}; Claude Code would silently ignore the whole file")
        else:
            _, changes, notes = sm.merge(target, shipped)
            for verb, text in changes:
                fail(f"{label}: {describe(verb, text)}")
            for verb, text in notes:
                warn(f"{label}: {verb} {text}")
            if target.get("disableAllHooks") is True:
                fail(f"{label} sets disableAllHooks: true, which switches every hook off")
            hook_scripts(project, target, shipped)

    local_path = project / LOCAL_REL
    if local_path.exists():
        try:
            local, _ = sm.load_object(local_path, LOCAL_REL.as_posix())
        except sm.Refused as e:
            warn(f"{e}; Claude Code ignores it, so it cannot weaken anything")
        else:
            overrides(local, shipped, LOCAL_REL.as_posix())

    for extra in extras:
        name = extra.as_posix()
        if not extra.is_file():
            fail(f"{name} (passed to Claude with --settings) does not exist")
            continue
        try:
            obj, _ = sm.load_object(extra, name)
        except sm.Refused as e:
            fail(f"{e}; Claude Code would silently ignore it, and its rules with it")
            continue
        overrides(obj, shipped, name)


def hook_scripts(project: Path, target: dict, shipped: dict) -> None:
    """Each shipped hook's entry must run a script that exists in the project."""
    for event, groups in shipped.get("hooks", {}).items():
        for g in groups:
            for h in g["hooks"]:
                ident = sm.hook_identity(event, h)
                for tg in target.get("hooks", {}).get(event, []):
                    for th in tg.get("hooks", []):
                        if sm.hook_identity(event, th) != ident:
                            continue
                        m = sm.HOOK_SCRIPT_RE.search(th.get("command") or "")
                        if m and not (project / HOOKS_REL / m.group(1)).is_file():
                            fail(f"hook script missing: {(HOOKS_REL / m.group(1)).as_posix()} "
                                 f"({event}); the entry is there but runs nothing")


# --- doctor ---------------------------------------------------------------------

def run_doctor(claude: list[str], cwd: Path) -> tuple[int | None, str]:
    try:
        p = subprocess.run(claude + ["doctor"], cwd=cwd, stdin=subprocess.DEVNULL,
                           capture_output=True, timeout=DOCTOR_TIMEOUT)
    except FileNotFoundError:
        return None, f"cannot run {claude[0]!r}"
    except subprocess.TimeoutExpired:
        return None, f"`claude doctor` did not finish within {DOCTOR_TIMEOUT} s"
    out = (p.stdout + b"\n" + p.stderr).decode("utf-8", errors="replace")
    return p.returncode, ANSI_RE.sub("", out).replace("\r\n", "\n")


def invalid_entries(output: str) -> list[str] | None:
    """The entries under doctor's "Invalid settings" heading; None if no heading."""
    lines = output.split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "Invalid settings":
            entries = []
            for nxt in lines[i + 1:]:
                if not nxt.strip():
                    break
                if nxt.lstrip().startswith("- "):
                    entries.append(nxt.strip()[2:])
            return entries
    return None


def doctor_dir(settings_text: str) -> tempfile.TemporaryDirectory:
    tmp = tempfile.TemporaryDirectory(prefix="dev-flow-preflight-")
    (Path(tmp.name) / ".claude").mkdir()
    (Path(tmp.name) / SETTINGS_REL).write_text(settings_text, encoding="utf-8")
    return tmp


def doctor_checks(project: Path, extras: list[Path], claude: list[str]) -> None:
    with doctor_dir(CALIBRATION) as cal:
        code, out = run_doctor(claude, Path(cal))
        if code is None:
            fail(f"the doctor check could not run: {out}")
            return
        entries = invalid_entries(out)
        if not entries or not any(CALIBRATION_KEY in e for e in entries):
            fail("calibration failed: `claude doctor` did not report a deliberately "
                 f"invalid settings file ({CALIBRATION_KEY} given a string), so its "
                 "silence about the project's files would prove nothing. Its output "
                 "format may have changed; see the log.")
            print(out[-3000:])
            return

    code, out = run_doctor(claude, project)
    if code is None:
        fail(f"the doctor check could not run: {out}")
        return
    for e in invalid_entries(out) or []:
        fail(f"Claude Code's schema rejects a settings file, so it would be "
             f"silently ignored: {e}")

    for extra in extras:
        if not extra.is_file():
            continue  # already reported by the static check
        with doctor_dir(extra.read_text(encoding="utf-8", errors="replace")) as d:
            code, out = run_doctor(claude, Path(d))
            if code is None:
                fail(f"the doctor check could not run on {extra.as_posix()}: {out}")
                continue
            for e in invalid_entries(out) or []:
                fail(f"Claude Code's schema rejects {extra.as_posix()} (checked as a "
                     f"copy), so --settings would silently drop it: {e}")


# --- main -----------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"settings_preflight.py: {message}", file=sys.stderr)
        sys.exit(1)


def report(title: str) -> None:
    for w in warnings:
        print(f"  WARNING  {w}")
    for p in problems:
        print(f"  FAIL     {p}")
    if os.environ.get("GITHUB_ACTIONS") == "true":
        for p in problems:
            print(f"::error title={title}::{p}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        lines = [f"### {title}", ""]
        lines += [f"- FAIL: {p}" for p in problems] or ["- passed"]
        lines += [f"- warning: {w}" for w in warnings]
        try:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n\n")
        except OSError:
            pass


def main(argv: list[str] | None = None) -> int:
    p = _Parser(description="Check a project's Claude Code settings before a CI job runs Claude.")
    p.add_argument("--project", default=".", help="the project root (default: .)")
    p.add_argument("--shipped", help=f"dev-flow's shipped settings (default: <project>/{SHIPPED_REL.as_posix()})")
    p.add_argument("--extra-settings", action="append", default=[], metavar="FILE",
                   help="a file the job passes to Claude with --settings (repeatable)")
    p.add_argument("--doctor", action="store_true",
                   help="also check the files against Claude Code's own schema, via `claude doctor`")
    p.add_argument("--claude", default="claude",
                   help="the command that runs Claude Code, for --doctor (default: claude)")
    args = p.parse_args(argv)

    project = Path(args.project)
    shipped = Path(args.shipped) if args.shipped else project / SHIPPED_REL
    extras = [Path(e) if Path(e).is_absolute() else project / e for e in args.extra_settings]

    static_checks(project, shipped, extras)
    title = "Settings preflight"
    if args.doctor:
        title += " (Claude Code's schema)"
        claude = shlex.split(args.claude)
        resolved = shutil.which(claude[0]) if claude else None
        if not resolved:
            fail(f"--doctor needs Claude Code, and {args.claude!r} is not on PATH")
        else:
            doctor_checks(project, extras, [resolved] + claude[1:])

    report(title)
    if problems:
        print(f"{title}: FAILED — {len(problems)} problem(s). Claude must not run with "
              f"these settings: a -p run would ignore or override them without a word.")
        return 1
    print(f"{title}: passed ({SETTINGS_REL.as_posix()}"
          + "".join(f", {e.as_posix()}" for e in extras) + ").")
    return 0


if __name__ == "__main__":
    sys.exit(main())
