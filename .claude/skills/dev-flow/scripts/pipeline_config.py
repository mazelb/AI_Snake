#!/usr/bin/env python3
"""
Project configuration for the development agents.

The flow does not know what language your project is in or what test runner it
uses. It knows the *names* of those operations and reads the commands from
`flow.json`. That is the whole trick: the agents that build and verify are
config-driven, so the same flow drives a TypeScript project and a Python one
without special cases.

Deployment is deliberately *not* here. It varies too much per project to
generalise usefully, and lives in `optional-delivery/` for projects that want it.
The `deploy` block and the `smoke`/`metric` commands are still accepted and
validated when present, so attaching that layer later needs no config migration.

Two consequences worth understanding:

  - An unconfigured command is not an error. A project with no `lint` command
    simply has no lint step. Steps skip loudly rather than failing, so a partly
    configured project still gets value from the parts it has configured.

  - Autonomy is per project, not per pipeline, and there are two tiers. `manual`
    means the agent readies the pull request and you merge; `autonomous` means the
    agent merges on green. Neither deploys: that belongs to `optional-delivery/`.
    The gates that never move regardless of tier are listed in GATES below — those
    exist because of what they protect, not because of how much you trust the agent.

One key that is not a command: `acceptance_junit`, the path (from the project
root) of a JUnit XML report the `acceptance` command writes. When it is set,
`ac_trace.py` reads verdicts from that report instead of scraping the runner's
text output. It is optional; a runner that cannot write JUnit XML leaves it out.

Usage:
    python3 pipeline_config.py --check          validate flow.json
    python3 pipeline_config.py --get test       print one command
    python3 pipeline_config.py --autonomy       print the autonomy tier
"""

from __future__ import annotations

import argparse
import json
import sys

# Piping into head/tail is normal usage; a broken pipe should not print a traceback.
try:
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (ImportError, AttributeError, ValueError):
    pass
from pathlib import Path

# The report prints dashes and arrows, and on Windows Python's stdout codec is
# cp1252 whenever output is piped or redirected. Write UTF-8 regardless, as
# issue_envelope.py and spec_lib.py do.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # already wrapped, or not a real stream
        pass

CONFIG_NAMES =["flow.json", ".flow.json", ".claude/flow.json"]

# Two tiers, and only `autonomous` lets the agent merge. There is deliberately no
# third tier and no alias for the removed `assisted`: an unknown tier is an
# error, never read as permission to merge.
AUTONOMY_TIERS = {
    "manual": "Agent reviews and readies the PR when clean; the human merges.",
    "autonomous": "Agent reviews and merges the PR when clean.",
}

# Gates that hold at every autonomy tier, including autonomous. Each is here
# because of a specific failure it prevents, not as a general precaution.
GATES = [
    "Plan approval is always human — status: approved is never set by an agent.",
    "A requirement judged wrong always returns to the human, never gets rewritten.",
    "Acceptance cases are never edited to match the code.",
    "Tests are generated from the cases, never from the implementation.",
    "Autonomous fix attempts on a failing case are capped at 2.",
]

KNOWN_COMMANDS = [
    "install",     # restore dependencies
    "lint",
    "typecheck",
    "test",        # the project's own test suite
    "acceptance",  # runs only the AC-tagged tests
    "build",
    # Below here are used only by the optional delivery layer. They are accepted
    # in core so that attaching delivery later needs no config migration.
    "smoke",       # post-deploy check; receives $DEPLOY_URL
    "metric",      # queries the success metric source; prints a number
]

DELIVERY_COMMANDS = ["smoke", "metric"]

KNOWN_TARGETS = ["vercel", "netlify", "docker-vps", "none"]


def junit_problems(data: dict) -> list[str]:
    """What is wrong with `acceptance_junit`, if anything. ac_trace.py refuses to
    trace on any of these rather than fall back to scraping text."""
    value = data.get("acceptance_junit")
    if value is None or value == "":
        return []
    if not isinstance(value, str) or not value.strip():
        return ["acceptance_junit must be the path of the JUnit XML report the "
                "acceptance command writes, as a string"]
    commands = data.get("commands")
    if not (isinstance(commands, dict) and commands.get("acceptance")):
        return ["acceptance_junit is set but no acceptance command is configured "
                "to write it"]
    return []


class Config:
    def __init__(self, path: Path, data: dict):
        self.path = path
        self.data = data

    @property
    def domain(self) -> str:
        return self.data.get("domain", "general")

    @property
    def autonomy(self) -> str:
        return self.data.get("autonomy", "manual")

    @property
    def commands(self) -> dict:
        return self.data.get("commands", {})

    @property
    def deploy(self) -> dict:
        return self.data.get("deploy", {})

    def command(self, name: str) -> str | None:
        value = self.commands.get(name)
        return value or None

    @property
    def acceptance_junit(self) -> str | None:
        value = self.data.get("acceptance_junit")
        return value if isinstance(value, str) and value.strip() else None

    def validate(self) -> list[str]:
        problems = []
        if self.autonomy not in AUTONOMY_TIERS:
            problems.append(
                f"autonomy '{self.autonomy}' is not one of: {', '.join(AUTONOMY_TIERS)}")

        for name in self.commands:
            if name not in KNOWN_COMMANDS:
                problems.append(
                    f"unknown command '{name}' — known: {', '.join(KNOWN_COMMANDS)}")

        problems.extend(junit_problems(self.data))

        target = self.deploy.get("target", "none")
        if not self.deploy:
            return problems  # no delivery layer attached; nothing more to check
        if target not in KNOWN_TARGETS:
            problems.append(
                f"deploy.target '{target}' is not one of: {', '.join(KNOWN_TARGETS)}")

        if target == "docker-vps":
            for key in ("host", "rollback"):
                if not self.deploy.get(key):
                    problems.append(
                        f"deploy.{key} is required for target 'docker-vps'. A VPS deploy "
                        "with no recorded rollback is a one-way door.")

        if target != "none" and not self.deploy.get("prod_branch"):
            problems.append("deploy.prod_branch is required when a deploy target is set")

        if self.autonomy == "autonomous":
            missing = [c for c in ("test", "acceptance") if not self.command(c)]
            if missing:
                problems.append(
                    f"autonomy 'autonomous' requires {' and '.join(missing)} to be configured — "
                    "merging on green is meaningless when nothing runs")

        return problems

    def report(self) -> str:
        lines = [f"{self.path}", f"  domain:   {self.domain}",
                 f"  autonomy: {self.autonomy} — {AUTONOMY_TIERS.get(self.autonomy, '?')}"]
        if self.deploy:
            target = self.deploy.get("target", "none")
            lines.append(f"  deploy:   {target}" + (
                f" → {self.deploy.get('host')}" if self.deploy.get("host") else ""))
        else:
            lines.append("  deploy:   (no delivery layer attached)")
        lines.append("  commands:")
        for name in KNOWN_COMMANDS:
            if name in DELIVERY_COMMANDS and not self.deploy:
                continue
            value = self.command(name)
            lines.append(f"    {name:<11} {value if value else '(not configured — step skips)'}")
        lines.append("  acceptance results: " + (
            f"JUnit report {self.acceptance_junit}" if self.acceptance_junit
            else "runner text output (no acceptance_junit)"))
        return "\n".join(lines)


def load(start: Path | None = None) -> Config | None:
    root = start or Path.cwd()
    for name in CONFIG_NAMES:
        candidate = root / name
        if candidate.exists():
            try:
                return Config(candidate, json.loads(candidate.read_text()))
            except json.JSONDecodeError as exc:
                print(f"{candidate}: invalid JSON — {exc}", file=sys.stderr)
                sys.exit(1)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Read and validate flow.json.")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--get", metavar="COMMAND")
    ap.add_argument("--autonomy", action="store_true")
    ap.add_argument("--gates", action="store_true")
    args = ap.parse_args()

    cfg = load()
    if cfg is None:
        print("No flow.json found. Run bootstrap.sh, or copy "
              "assets/flow.example.json to flow.json.", file=sys.stderr)
        return 3

    if args.gates:
        for gate in GATES:
            print(f"- {gate}")
        return 0

    if args.autonomy:
        # /review branches on this output, so an unknown tier must not print as
        # if it were one: it would be a merge decision taken on a typo.
        if cfg.autonomy not in AUTONOMY_TIERS:
            print(f"autonomy '{cfg.autonomy}' is not one of: {', '.join(AUTONOMY_TIERS)}",
                  file=sys.stderr)
            return 1
        print(cfg.autonomy)
        return 0

    if args.get:
        value = cfg.command(args.get)
        if not value:
            print(f"(not configured: {args.get})", file=sys.stderr)
            return 4
        print(value)
        return 0

    print(cfg.report())
    problems = cfg.validate()
    if problems:
        print("\n  problems:")
        for p in problems:
            print(f"    - {p}")
        return 1
    print("\n  config valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
