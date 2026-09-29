#!/usr/bin/env python3
"""
Evidence ledger: a check counts only if it ran here, on this tree, through this.

The problem this solves: "the tests pass" is a claim, and a model makes it
easily -- about a run from before its last edit, a run on another tree, or a run
that never happened. This script turns the claim into a record. It runs a
`flow.json` command, passes its output through untouched, exits with the
command's own exit code, and appends one line to a ledger:

    label, command, command sha256, exit code, commit,
    tree fingerprint before the run, tree fingerprint after it, times

`check` then grades each label against the tree as it is now:

    FRESH    the last record's command is still the one in flow.json, the tree
             did not change while it ran, and the tree is the same now
    STALE    any of those three is false: an edit since, an edit during the
             run, or a different command
    MISSING  no record, or the command is not configured in flow.json

A FRESH record still carries its exit code: FRESH with exit 1 is fresh proof
that the check failed. Only FRESH with exit 0 is a pass.

The tree fingerprint is git's own tree id for every file git would see -- all
tracked files as they are on disk, plus untracked files that are not ignored --
computed in a temporary index, so the project's real index is never touched.
It leaves out the pipeline's own state: `.dev-flow-run/` (where the ledger
lives), `.claude/spec-pipeline/` (retry counters and markers) and the ledger
file itself. Ignored files (`node_modules/`, `.env`, build output) are not part
of it: changing one does not make evidence STALE. `check --against HEAD` grades
against the last commit's tree instead of the working tree, which is what
`/review` needs: the evidence must describe what the branch actually commits.

Computing the fingerprint writes the tree's blobs into `.git/objects`, as
`git stash create` does; `git gc` prunes them in time. That is also what lets
`check` name the files that changed since a record.

What the ledger holds is exit codes and tree ids, never command output. The
`acceptance` command's output names acceptance cases, and a ledger that kept it
would be a new route by which hidden cases reach a session that must not see
them. The output goes to stdout, exactly as if the command had run directly.

The ledger is a plain file, not a vault. It stops a model *claiming* a result it
did not produce; it does not stop a session that sets out to forge a record.

Usage:
    python3 evidence.py run LABEL                  run flow.json's LABEL command and record it
    python3 evidence.py check LABEL...             grade the last record of each label
    python3 evidence.py check --against HEAD LABEL...
    python3 evidence.py check --json LABEL...      the same, as JSON
    python3 evidence.py fingerprint [--against HEAD]
    ... [--ledger PATH]   default .dev-flow-run/evidence.jsonl under the repo root

Exit codes:
    run          the command's own exit code; 3 cannot run (no flow.json, not a
                 git repository, no shell, the fingerprint or the ledger write
                 failed on a command that exited 0); 4 LABEL is not configured,
                 nothing run and nothing recorded
    check        0 every label FRESH with exit 0; 1 a label is FRESH with a
                 non-zero exit (a real failure); 2 otherwise a label is STALE or
                 MISSING; 3 cannot check
    fingerprint  0, or 3
    usage error  64
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# Piping into head/tail is normal usage; a broken pipe is not an error worth a
# traceback.
try:
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (ImportError, AttributeError, ValueError):
    pass

# Windows pipes default to cp1252; the report prints dashes. Same fix as
# pipeline_config.py and spec_lib.py.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_config  # noqa: E402

SCHEMA = 1
DEFAULT_LEDGER = Path(".dev-flow-run") / "evidence.jsonl"
# Pipeline state that changes between runs without changing the code under test.
# Leaving it in would make every record STALE the moment a retry was counted.
EXCLUDED = [".dev-flow-run", ".claude/spec-pipeline"]
RECORD_KEYS = {"schema", "label", "command", "command_sha256", "exit_code", "commit",
               "tree_before", "tree_after", "started", "finished"}

EXIT_RUN_ERROR = 3
EXIT_NOT_CONFIGURED = 4
EXIT_USAGE = 64


class EvidenceError(Exception):
    """Something that stops a run or a check before it can say anything true."""


def say(message: str) -> None:
    # One prefix for every line of our own. `run`'s output is often piped into
    # ac_trace.py together with the command's, so these lines must never carry
    # an AC id, a verdict word ("ok", "pass", "fail", "error") or a file name.
    print(f"evidence: {message}", file=sys.stderr, flush=True)


def git(root: Path, *args: str, env: dict | None = None, check: bool = True) -> str:
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)
    if check and proc.returncode != 0:
        raise EvidenceError(f"git {' '.join(args[:2])} exited {proc.returncode}: "
                            f"{proc.stderr.strip()[:300]}")
    return proc.stdout.strip()


def repo_root() -> Path:
    proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise EvidenceError("not inside a git repository; evidence is tied to a git tree")
    return Path(proc.stdout.strip())


def head_commit(root: Path) -> str | None:
    out = git(root, "rev-parse", "--verify", "--quiet", "HEAD^{commit}", check=False)
    return out or None


def excluded_paths(root: Path, ledger: Path) -> list[str]:
    paths = list(EXCLUDED)
    try:
        rel = ledger.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = None  # the ledger lives outside the repository
    if rel and not any(rel == p or rel.startswith(p + "/") for p in paths):
        paths.append(rel)
    return paths


def fingerprint(root: Path, ledger: Path, against: str | None = None) -> str:
    """Git's tree id for the working tree (or for `against`), minus pipeline state."""
    fd, index = tempfile.mkstemp(prefix="devflow-evidence-index-")
    os.close(fd)
    os.unlink(index)  # git wants to create it; an empty file is not a valid index
    env = dict(os.environ, GIT_INDEX_FILE=index)
    excluded = excluded_paths(root, ledger)
    try:
        if against:
            git(root, "read-tree", against, env=env)
        else:
            # Relative to the repository root, or absolute in a linked worktree.
            real = root / git(root, "rev-parse", "--git-path", "index")
            if real.is_file():
                # Starting from a copy of the real index lets git reuse its stat
                # cache, so only changed files are hashed.
                shutil.copyfile(real, index)
            # No exclusion pathspecs here: naming a path that is gitignored and
            # present (`.dev-flow-run/`, which bootstrap ignores) makes `git
            # add` refuse it and exit 1. The excluded paths are dropped by the
            # `rm --cached` below instead, whether ignored or not.
            git(root, "add", "--all", "--", ".", env=env)
        git(root, "rm", "-r", "-q", "--cached", "--ignore-unmatch", "--",
            *[f":(top){p}" for p in excluded], env=env)
        return git(root, "write-tree", env=env)
    finally:
        for leftover in (index, index + ".lock"):
            try:
                os.unlink(leftover)
            except OSError:
                pass


def list_changed(root: Path, old: str, new: str) -> list[str] | None:
    """The files that differ between two tree ids; None when git cannot say."""
    out = subprocess.run(["git", "-C", str(root), "diff-tree", "-r", "--name-only",
                          "--no-renames", old, new],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        return None  # the old tree's objects were pruned; the grade stands regardless
    return [p for p in out.stdout.splitlines() if p.strip()]


def changed_paths(root: Path, old: str, new: str, limit: int = 8) -> str:
    """The same, as one line for a human; '' if unknown."""
    paths = list_changed(root, old, new)
    if not paths:
        return ""
    shown = ", ".join(paths[:limit])
    return shown + (f" and {len(paths) - limit} more" if len(paths) > limit else "")


def command_sha(command: str) -> str:
    return hashlib.sha256(command.encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def find_shell() -> str:
    """bash, as the commands in flow.json are written for it.

    On Windows `bash` can resolve to the WSL launcher in System32, which would
    run the command in another operating system's checkout. Skip it.
    """
    for name in ("bash", "sh"):
        found = shutil.which(name)
        if found and "system32" not in found.lower().replace("\\", "/"):
            return found
    raise EvidenceError("no bash or sh on PATH to run the command with")


def load_config(root: Path) -> pipeline_config.Config:
    cfg = pipeline_config.load(root)
    if cfg is None:
        raise EvidenceError("no flow.json at the repository root")
    return cfg


def resolve_ledger(root: Path, given: str | None) -> Path:
    path = Path(given) if given else DEFAULT_LEDGER
    return path if path.is_absolute() else root / path


def read_ledger(ledger: Path) -> tuple[dict[str, dict], int]:
    """The last well-formed record per label, and how many lines were unreadable."""
    last: dict[str, dict] = {}
    bad = 0
    if not ledger.is_file():
        return last, bad
    with open(ledger, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            if (not isinstance(rec, dict) or not RECORD_KEYS <= set(rec)
                    or not isinstance(rec.get("exit_code"), int)
                    or not isinstance(rec.get("label"), str)):
                bad += 1
                continue
            last[rec["label"]] = rec
    return last, bad


def append_record(ledger: Path, record: dict) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
    with open(ledger, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())


# --- run ---------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> int:
    root = repo_root()
    ledger = resolve_ledger(root, args.ledger)
    cfg = load_config(root)
    command = cfg.command(args.label)
    if not command:
        say(f"{args.label} is not configured in flow.json; nothing run, nothing recorded")
        return EXIT_NOT_CONFIGURED
    shell = find_shell()

    commit = head_commit(root)
    before = fingerprint(root, ledger)
    started, t0 = now(), time.monotonic()
    proc = subprocess.run([shell, "-c", command], cwd=str(root))
    code = proc.returncode
    if code < 0:  # killed by a signal (POSIX); report it the way a shell would
        code = 128 - code
    finished, seconds = now(), round(time.monotonic() - t0, 3)

    try:
        after = fingerprint(root, ledger)
        append_record(ledger, {
            "schema": SCHEMA, "label": args.label, "command": command,
            "command_sha256": command_sha(command), "exit_code": code, "commit": commit,
            "tree_before": before, "tree_after": after,
            "started": started, "finished": finished, "seconds": seconds,
        })
    except (EvidenceError, OSError) as exc:
        # The reason goes to stderr on its own line after ours, unprefixed: it
        # may hold file names, and our own lines must not (see say()).
        say(f"{args.label} ran (exit {code}) but was NOT recorded; the reason follows")
        print(str(exc), file=sys.stderr)
        return code if code != 0 else EXIT_RUN_ERROR

    note = ""
    if before != after:
        n = len(list_changed(root, before, after) or [])
        note = (f"; the tree changed while it ran ({n} path(s)), so this record is "
                "already STALE -- `check` names them")
    say(f"{args.label} recorded, exit {code}{note}")
    return code


# --- check -------------------------------------------------------------------

def grade(label: str, cfg: pipeline_config.Config, rec: dict | None,
          current: str, root: Path) -> dict:
    command = cfg.command(label)
    out: dict = {"label": label, "grade": "MISSING", "exit_code": None, "reasons": []}
    if not command:
        out["reasons"].append("not configured in flow.json")
        return out
    if rec is None:
        out["reasons"].append("never run through evidence.py")
        return out
    out.update(exit_code=rec["exit_code"], recorded=rec["finished"], commit=rec["commit"],
               tree=rec["tree_after"])
    reasons = out["reasons"]
    if rec["command_sha256"] != command_sha(command):
        reasons.append("the command in flow.json changed since it ran")
    if rec["tree_before"] != rec["tree_after"]:
        paths = changed_paths(root, rec["tree_before"], rec["tree_after"])
        reasons.append("the tree changed while it ran" + (f": {paths}" if paths else ""))
    if rec["tree_after"] != current:
        paths = changed_paths(root, rec["tree_after"], current)
        reasons.append("the tree changed since it ran" + (f": {paths}" if paths else ""))
    out["grade"] = "STALE" if reasons else "FRESH"
    return out


def cmd_check(args: argparse.Namespace) -> int:
    root = repo_root()
    ledger = resolve_ledger(root, args.ledger)
    cfg = load_config(root)
    against = None
    if args.against:
        against = git(root, "rev-parse", "--verify", "--quiet", f"{args.against}^{{commit}}",
                      check=False)
        if not against:
            raise EvidenceError(f"cannot resolve {args.against} to a commit")
    current = fingerprint(root, ledger, against)
    records, bad = read_ledger(ledger)
    rows = [grade(label, cfg, records.get(label), current, root) for label in args.labels]

    if any(r["grade"] == "FRESH" and r["exit_code"] != 0 for r in rows):
        code = 1
    elif all(r["grade"] == "FRESH" for r in rows):
        code = 0
    else:
        code = 2

    if args.json:
        print(json.dumps({"against": args.against or "working tree", "commit": against,
                          "tree": current, "ledger": str(ledger), "unreadable_lines": bad,
                          "exit": code, "checks": rows}, indent=2))
        return code

    where = f"{args.against} ({against[:7]})" if against else "the working tree"
    try:
        shown = ledger.relative_to(root).as_posix()
    except ValueError:
        shown = str(ledger)
    print(f"evidence for {where}, tree {current[:12]}, from {shown}")
    for r in rows:
        exit_txt = f"exit {r['exit_code']}" if r["exit_code"] is not None else ""
        when = f"ran {r['recorded']}" if r.get("recorded") else ""
        detail = "; ".join(r["reasons"])
        line = f"  {r['label']:<11} {r['grade']:<8} {exit_txt:<8} {when}"
        print(line.rstrip() + (f" -- {detail}" if detail else ""))
    if bad:
        print(f"  ({bad} unreadable ledger line(s) ignored)")
    verdicts = {0: "every check FRESH with exit 0",
                1: "a check is FRESH and exited non-zero: it failed on this tree",
                2: "not every check is FRESH: STALE or MISSING evidence proves nothing "
                   "about this tree"}
    print(f"  => {verdicts[code]}")
    return code


def cmd_fingerprint(args: argparse.Namespace) -> int:
    root = repo_root()
    against = args.against
    if against and not git(root, "rev-parse", "--verify", "--quiet", f"{against}^{{commit}}",
                           check=False):
        raise EvidenceError(f"cannot resolve {against} to a commit")
    print(fingerprint(root, resolve_ledger(root, args.ledger), against))
    return 0


class Parser(argparse.ArgumentParser):
    # argparse exits 2 on a usage error, which here would read as "STALE".
    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        sys.exit(EXIT_USAGE)


def main(argv: list[str] | None = None) -> int:
    ap = Parser(prog="evidence.py", description="Record and grade check evidence.")
    sub = ap.add_subparsers(dest="action", required=True, parser_class=Parser)
    labels = pipeline_config.KNOWN_COMMANDS

    p = sub.add_parser("run", help="run a flow.json command and record it")
    p.add_argument("label", choices=labels)
    p.add_argument("--ledger")

    p = sub.add_parser("check", help="grade the latest record of each label")
    p.add_argument("labels", nargs="+", choices=labels, metavar="LABEL")
    p.add_argument("--against", metavar="REV",
                   help="grade against this commit's tree instead of the working tree")
    p.add_argument("--json", action="store_true")
    p.add_argument("--ledger")

    p = sub.add_parser("fingerprint", help="print the current tree fingerprint")
    p.add_argument("--against", metavar="REV")
    p.add_argument("--ledger")

    args = ap.parse_args(argv)
    handler = {"run": cmd_run, "check": cmd_check, "fingerprint": cmd_fingerprint}[args.action]
    try:
        return handler(args)
    except EvidenceError as exc:
        say(f"cannot {args.action}: {exc}")
        return EXIT_RUN_ERROR


if __name__ == "__main__":
    sys.exit(main())
