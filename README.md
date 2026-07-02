# AgentRunbook

[![CI](https://github.com/KingRainIce/agentrunbook/actions/workflows/ci.yml/badge.svg)](https://github.com/KingRainIce/agentrunbook/actions/workflows/ci.yml)

Run auditable AI agents from readable TOML runbooks.

![AgentRunbook demo](https://raw.githubusercontent.com/KingRainIce/agentrunbook/main/docs/demo.gif)

AgentRunbook turns repeatable AI workflows into versioned runbooks. You describe the agents, context, tool steps, budgets, and output artifacts in TOML; AgentRunbook runs the workflow and writes a trace you can inspect later.

It is built for developers and small teams who want useful agents without adopting a large platform before the workflow has proved itself.

## Contents

- [What You Can Build](#what-you-can-build)
- [Quickstart](#quickstart)
- [Core Concepts](#core-concepts)
- [Runbook Anatomy](#runbook-anatomy)
- [CLI Reference](#cli-reference)
- [Step Reference](#step-reference)
- [Templates And Context](#templates-and-context)
- [Safety Model](#safety-model)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

## What You Can Build

- GitHub issue triage that fetches an issue, summarizes severity, suggests labels, and drafts a maintainer reply.
- Support ticket triage that turns rough customer reports into escalation notes.
- Repository review checklists that collect local signals and produce focused review prompts.
- Research briefs that fetch public data, ask an analyst agent to reason over it, and write a markdown artifact.
- MCP-backed workflows that call local stdio tools through explicit allowlists.
- Team SOPs where every run leaves `report.md`, `summary.json`, and `trace.jsonl`.

## Why This Exists

Many agent demos are impressive once and hard to trust twice. Common pain points are hidden state, surprise tool execution, heavyweight setup, unclear outputs, and workflows that cannot be reviewed like code.

AgentRunbook keeps the useful parts of popular agent projects:

- Readable workflows and reusable roles.
- Tool use with clear boundaries.
- Local-first execution.
- Hard limits on steps and time.
- Trace files for debugging and audit.

It avoids making unbounded autonomy the default. A runbook is a contract: what context enters, what agents do, what tools may run, and what artifacts should come out.

## Features

- TOML runbooks: no Python required to define a workflow.
- Zero runtime dependencies on Python 3.11+.
- `mock` provider by default, so examples run without API keys.
- OpenAI-compatible chat completions when you set an API key.
- Role-based agents with goals and instructions.
- Built-in step types: `llm`, `shell`, `http`, `write`, `github_issue_triage`, and `mcp_tool`.
- Shell and MCP safety: dry-run by default, real execution only with `--allow-shell` and an allowlist.
- Budgets: `max_steps`, `max_seconds`, and `max_tool_seconds`.
- Traceability: every run writes `report.md`, `summary.json`, and `trace.jsonl`.

## Install

From a cloned repository:

```bash
git clone https://github.com/KingRainIce/agentrunbook.git
cd agentrunbook
python -m pip install -e .
```

After the package is published to PyPI:

```bash
python -m pip install agentrunbook
```

Requirements:

- Python 3.11 or newer.
- No runtime dependencies.
- Optional `OPENAI_API_KEY` for real model calls.
- Optional `GITHUB_TOKEN` or `GH_TOKEN` for private GitHub issues or higher rate limits.

## Quickstart

Create and run a starter runbook:

```bash
python -m agentrunbook init demo.toml
python -m agentrunbook validate demo.toml
python -m agentrunbook run demo.toml
```

The default provider is `mock`, so the first run works without keys or network model calls.

You should see output like:

```text
run 20260702T093312Z-a18f42c9: ok
- plan: ok
- write_report: ok

artifacts:
- report:  .agentrunbook/runs/.../report.md
- trace:   .agentrunbook/runs/.../trace.jsonl
- summary: .agentrunbook/runs/.../summary.json
```

Run a real example:

```bash
python -m agentrunbook run examples/support-triage.toml
```

Use a real model:

```bash
export OPENAI_API_KEY="sk-..."
python -m agentrunbook run examples/support-triage.toml --provider openai --model gpt-4.1-mini
```

PowerShell:

```powershell
$env:OPENAI_API_KEY="sk-..."
python -m agentrunbook run examples/support-triage.toml --provider openai --model gpt-4.1-mini
```

Use any OpenAI-compatible endpoint:

```bash
export OPENAI_BASE_URL="https://api.your-provider.example"
export OPENAI_API_KEY="..."
python -m agentrunbook run examples/research-brief.toml --provider openai --model your-model
```

## Core Concepts

| Concept | Meaning |
| --- | --- |
| Runbook | A TOML file that defines context, agents, tools, budgets, and ordered steps. |
| Context | Named values available to templates, such as `ticket`, `repo`, or `goal`. |
| Agent | A role with a goal and instructions. LLM steps use agents to form system prompts. |
| Step | One executable unit, such as an LLM call, HTTP fetch, shell command, MCP call, or file write. |
| Artifact | A file written inside the run directory. Artifacts are safe to inspect and share selectively. |
| Trace | JSONL event stream showing run start, step start/end, previews, errors, and timing. |

## Runbook Anatomy

```toml
[runbook]
name = "support-triage"
description = "Classify a support ticket and draft a reply."
provider = "mock"
model = "mock-smart"
workspace = ".agentrunbook"
max_steps = 6
max_seconds = 180
max_tool_seconds = 20

[context]
ticket = "Customer says the export job is stuck at 92% after upgrading."

[[agents]]
id = "triager"
role = "Senior support triage agent"
goal = "Classify customer issues and produce practical next actions."
instructions = "Separate facts from hypotheses. Be concise."

[[steps]]
id = "classify"
type = "llm"
agent = "triager"
save_as = "classification"
prompt = """
Ticket:
{{ ticket }}

Return severity, likely component, missing information, and first response.
"""

[[steps]]
id = "write"
type = "write"
path = "triage.md"
content = "{{ classification }}"
```

## CLI Reference

```bash
python -m agentrunbook --version
python -m agentrunbook init [path]
python -m agentrunbook validate <runbook.toml>
python -m agentrunbook run <runbook.toml> [--provider mock|openai] [--model MODEL] [--workspace PATH] [--allow-shell] [--json]
```

Useful commands:

```bash
python -m agentrunbook run examples/repo-review.toml
python -m agentrunbook run examples/repo-review.toml --allow-shell
python -m agentrunbook run examples/github-issue-triage.toml --json
python -m agentrunbook run examples/mcp-echo.toml --allow-shell
```

## Step Reference

### `llm`

Ask a configured agent to produce text.

```toml
[[steps]]
id = "draft"
type = "llm"
agent = "writer"
save_as = "draft"
prompt = "Write a reply for {{ customer_name }}."
```

Fields:

| Field | Required | Notes |
| --- | --- | --- |
| `id` | Yes | Unique step id. |
| `type` | Yes | Must be `llm`. |
| `agent` | No | References an `[[agents]]` id. |
| `prompt` | Yes | Supports templates. |
| `save_as` | No | Stores output in context under this name. |
| `allow_failure` | No | Records failure and continues when true. |

### `shell`

Run a local command. Shell steps are dry-run unless `--allow-shell` is passed.

```toml
[tools.shell]
allow = ["git", "python"]

[[steps]]
id = "status"
type = "shell"
command = "git status --short"
save_as = "git_status"
allow_failure = true
```

Fields:

| Field | Required | Notes |
| --- | --- | --- |
| `command` | Yes | Split into argv; no shell expansion is used. |
| `timeout_seconds` | No | Overrides `max_tool_seconds`. |
| `allow_failure` | No | Useful for optional repo probes. |

### `http`

Fetch an HTTP resource and store the response text.

```toml
[[steps]]
id = "fetch_repo"
type = "http"
url = "https://api.github.com/repos/{{ repo }}"
save_as = "repo_json"
```

### `write`

Write a file inside the run's `artifacts/` directory.

```toml
[[steps]]
id = "write_report"
type = "write"
path = "report.md"
content = "{{ draft }}"
```

Artifact paths cannot escape the run directory.

### `github_issue_triage`

Fetch a GitHub issue and comments, then ask an agent to triage it.

```toml
[[steps]]
id = "triage"
type = "github_issue_triage"
agent = "maintainer"
repo = "KingRainIce/agentrunbook"
issue = "1"
max_comments = 20
save_as = "triage"
```

Use `GITHUB_TOKEN` or `GH_TOKEN` for private repositories or higher API rate limits. The raw issue payload is also written as an artifact under `artifacts/github/`.

### `mcp_tool`

Call a stdio MCP tool through the same allowlist model as shell steps.

```toml
[tools.shell]
allow = ["python"]

[[steps]]
id = "echo"
type = "mcp_tool"
command = "python mcp-echo-server.py"
tool = "echo"
save_as = "echoed"

[steps.arguments]
text = "Hello from MCP"
```

Run with:

```bash
python -m agentrunbook run examples/mcp-echo.toml --allow-shell
```

Without `--allow-shell`, the MCP call is recorded as a dry-run.

## Templates And Context

Templates use double braces:

```text
{{ ticket }}
{{ steps.classify.output }}
{{ steps.status.metadata.returncode }}
```

Values available by default:

| Name | Description |
| --- | --- |
| `context` | Copy of the `[context]` table. |
| Direct context keys | Values from `[context]`, such as `ticket` or `repo`. |
| `runbook.name` | Runbook name. |
| `runbook.description` | Runbook description. |
| `run.id` | Unique run id. |
| `run.dir` | Run directory path as text. |
| `now` | Current UTC timestamp. |
| `date` | Current UTC date. |
| `steps.<id>.output` | Output from a completed step. |
| `steps.<id>.metadata` | Metadata from a completed step. |
| `save_as` aliases | A step with `save_as = "draft"` creates `{{ draft }}`. |

Missing template values fail fast with a clear error.

## Output Files

Every run creates a directory like:

```text
.agentrunbook/runs/20260702T093312Z-a18f42c9/
  artifacts/
    github/
    report-or-generated-files.md
  report.md
  summary.json
  trace.jsonl
```

| File | Purpose |
| --- | --- |
| `report.md` | Human-readable report for the whole run. |
| `summary.json` | Machine-readable status and step outputs. |
| `trace.jsonl` | Event log for debugging and audit. |
| `artifacts/` | Files written by `write` steps and raw data captured by specialized steps. |

## Safety Model

AgentRunbook is conservative by default:

- `shell` and `mcp_tool` steps do not execute unless you pass `--allow-shell`.
- Even with `--allow-shell`, the command head must match `[tools.shell].allow`.
- Commands are executed as argv, not through a shell string.
- Tool steps have timeouts.
- Runbooks have max step and max runtime budgets.
- Artifacts are restricted to the run directory.

Do not run untrusted runbooks with `--allow-shell`.

## Examples

| File | What it demonstrates |
| --- | --- |
| `examples/support-triage.toml` | Multi-agent support classification and customer reply drafting. |
| `examples/repo-review.toml` | Dry-run shell probes and review checklist generation. |
| `examples/research-brief.toml` | HTTP fetch plus analyst-style synthesis. |
| `examples/github-issue-triage.toml` | GitHub issue fetch, raw artifact capture, and maintainer triage. |
| `examples/mcp-echo.toml` | Calling a local stdio MCP server with an allowlist. |

## Troubleshooting

`No module named agentrunbook`

Install the package from the repository root:

```bash
python -m pip install -e .
```

`OPENAI_API_KEY is required`

You are using `provider = "openai"` or `--provider openai`. Set `OPENAI_API_KEY` or run with the default `mock` provider.

`command is not in the runbook allowlist`

Add the command head to `[tools.shell].allow`, then pass `--allow-shell`.

`missing template value`

Check the spelling of the template key and confirm the referenced step has already run.

`GitHub API returned HTTP 403`

Set `GITHUB_TOKEN` or `GH_TOKEN` to raise rate limits or access private repositories.

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests
python -m build
python -m twine check dist/*
```

Useful project files:

- `docs/runbook-reference.md`: detailed runbook schema and field reference.
- `docs/research.md`: research notes behind the project positioning.
- `docs/publishing.md`: PyPI publishing steps and Trusted Publishing setup.
- `SECURITY.md`: security notes for local tool execution.
- `CONTRIBUTING.md`: contribution guidelines.

## Roadmap

- JSON schema validation for runbooks.
- Resume from a previous run directory.
- Native eval step for checking outputs.
- GitHub PR helper step.
- More MCP examples with real-world tools.
- Optional HTML report renderer.

## License

MIT
