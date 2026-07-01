from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

from . import __version__
from .config import ConfigError, load_runbook
from .engine import RunError, Runner
from .models import Runbook


STARTER = '''\
[runbook]
name = "starter"
description = "A tiny auditable agent runbook."
provider = "mock"
model = "mock-smart"
max_steps = 6
max_seconds = 180
max_tool_seconds = 20

[context]
goal = "Turn a rough idea into a practical next-step plan."
audience = "busy builders"

[[agents]]
id = "planner"
role = "Product-minded planning agent"
goal = "Convert vague goals into concrete, shippable work."
instructions = "Return crisp markdown. Avoid hype. Include risks and next actions."

[[steps]]
id = "plan"
type = "llm"
agent = "planner"
save_as = "plan"
prompt = \"\"\"
Goal: {{ goal }}
Audience: {{ audience }}

Create:
1. A one-paragraph product angle
2. Three concrete use cases
3. A two-day build plan
4. The biggest risk
\"\"\"

[[steps]]
id = "write_report"
type = "write"
path = "starter-report.md"
content = \"\"\"
# Starter report

{{ plan }}
\"\"\"
'''


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ConfigError, RunError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentrunbook",
        description="Run auditable AI agents from readable TOML runbooks.",
    )
    parser.add_argument("--version", action="version", version=f"agentrunbook {__version__}")
    subparsers = parser.add_subparsers(required=True)

    init_parser = subparsers.add_parser("init", help="write a starter runbook")
    init_parser.add_argument("path", nargs="?", default="agentrunbook.toml")
    init_parser.set_defaults(func=cmd_init)

    validate_parser = subparsers.add_parser("validate", help="validate a runbook")
    validate_parser.add_argument("runbook")
    validate_parser.set_defaults(func=cmd_validate)

    run_parser = subparsers.add_parser("run", help="execute a runbook")
    run_parser.add_argument("runbook")
    run_parser.add_argument("--provider", choices=("mock", "openai"), help="override runbook provider")
    run_parser.add_argument("--model", help="override runbook model")
    run_parser.add_argument("--workspace", help="override runbook workspace")
    run_parser.add_argument("--allow-shell", action="store_true", help="execute allowlisted shell steps")
    run_parser.add_argument("--json", action="store_true", help="print machine-readable run summary")
    run_parser.set_defaults(func=cmd_run)
    return parser


def cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.path)
    if target.exists():
        raise ConfigError(f"{target} already exists")
    target.write_text(STARTER, encoding="utf-8")
    print(f"created {target}")
    print("run: agentrunbook run " + str(target))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    runbook = load_runbook(args.runbook)
    print(f"ok: {runbook.name} ({len(runbook.steps)} steps)")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    runbook_path = Path(args.runbook).resolve()
    runbook = load_runbook(runbook_path)
    runbook = override_runbook(runbook, provider=args.provider, model=args.model, workspace=args.workspace)
    result = Runner(
        runbook,
        runbook_path=runbook_path,
        allow_shell=args.allow_shell,
        cwd=runbook_path.parent,
    ).run()
    if args.json:
        print(
            json.dumps(
                {
                    "run_id": result.run_id,
                    "status": result.status,
                    "run_dir": str(result.run_dir),
                    "summary": str(result.summary_path),
                    "trace": str(result.trace_path),
                    "report": str(result.report_path),
                },
                indent=2,
            )
        )
        return 0
    print_run_result(result)
    return 0


def override_runbook(
    runbook: Runbook,
    *,
    provider: str | None = None,
    model: str | None = None,
    workspace: str | None = None,
) -> Runbook:
    return Runbook(
        name=runbook.name,
        description=runbook.description,
        agents=runbook.agents,
        steps=runbook.steps,
        context=runbook.context,
        provider=provider or runbook.provider,
        model=model or runbook.model,
        workspace=workspace or runbook.workspace,
        max_steps=runbook.max_steps,
        max_seconds=runbook.max_seconds,
        max_tool_seconds=runbook.max_tool_seconds,
        allowed_shell=runbook.allowed_shell,
    )


def print_run_result(result) -> None:
    print(f"run {result.run_id}: {result.status}")
    for step in result.steps:
        print(f"- {step.id}: {step.status}")
    print(
        textwrap.dedent(
            f"""\

            artifacts:
            - report:  {result.report_path}
            - trace:   {result.trace_path}
            - summary: {result.summary_path}
            """
        ).strip()
    )
