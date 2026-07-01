# AgentRunbook

[![CI](https://github.com/KingRainIce/agentrunbook/actions/workflows/ci.yml/badge.svg)](https://github.com/KingRainIce/agentrunbook/actions/workflows/ci.yml)

Run auditable AI agents from readable TOML runbooks.

AgentRunbook is a tiny Python framework for repeatable agent workflows: role-based LLM steps, safe tool steps, strict budgets, and JSONL traces. It is designed for teams that want useful agents without pulling in a large platform before they know the workflow works.

## Why This Exists

The agent projects people star tend to share the same virtues:

- AutoGPT proved people want goal-driven automation, but long-running autonomy needs hard limits and observability.
- LangChain and LangGraph showed the value of composable integrations and controllable workflows.
- CrewAI and MetaGPT made role-based collaboration easy to understand.
- OpenAI Agents SDK and smolagents keep the "small core, powerful tools" path attractive.
- browser-use showed that one practical capability beats a broad abstract promise.

AgentRunbook keeps the useful parts: readable workflows, roles, tool use, guardrails, traces, and local-first execution. It cuts the painful parts: heavyweight setup, hidden state, surprise shell execution, and unbounded loops.

## Features

- TOML runbooks: no Python required to describe a workflow.
- Zero runtime dependencies on Python 3.11+.
- Provider modes: deterministic `mock` by default, OpenAI-compatible chat completions when you set an API key.
- Role-based agents with system prompts, goals, and instructions.
- Built-in step types: `llm`, `shell`, `http`, and `write`.
- Shell safety: shell steps are dry-run unless you pass `--allow-shell`, and commands must be allowlisted.
- Budgets: max steps, max run seconds, and max tool seconds.
- Traceability: each run writes `trace.jsonl`, `summary.json`, and `report.md`.

## Quickstart

```bash
python -m pip install -e .
python -m agentrunbook init demo.toml
python -m agentrunbook run demo.toml
```

The default provider is `mock`, so the first run works without keys.

Use a real model:

```bash
export OPENAI_API_KEY="sk-..."
python -m agentrunbook run examples/support-triage.toml --provider openai --model gpt-4.1-mini
```

On PowerShell:

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

## A Runbook

```toml
[runbook]
name = "support-triage"
provider = "mock"
model = "mock-smart"
max_steps = 6
max_seconds = 180

[context]
ticket = "Customer says the export job is stuck at 92% after upgrading."

[[agents]]
id = "triager"
role = "Senior support triage agent"
goal = "Classify customer issues and produce practical next actions."

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

Every run creates:

```text
.agentrunbook/runs/<timestamp>/
  artifacts/
  report.md
  summary.json
  trace.jsonl
```

## Shell Steps Are Bounded

Shell tools are useful for code and ops workflows, but they should not be magic. A shell step is dry-run by default:

```bash
python -m agentrunbook run examples/repo-review.toml
```

Actually execute allowlisted commands:

```bash
python -m agentrunbook run examples/repo-review.toml --allow-shell
```

The runbook must explicitly allow command heads:

```toml
[tools.shell]
allow = ["git", "python", "pytest"]
```

## Step Types

| Type | Purpose |
| --- | --- |
| `llm` | Ask a configured agent to produce structured text. |
| `shell` | Run an allowlisted local command with timeout and trace. |
| `http` | Fetch an HTTP resource for research and context gathering. |
| `write` | Write generated artifacts inside the run directory. |

Templates use `{{ value }}` and nested paths such as `{{ steps.classify.output }}`.

## Example Ideas

- Issue triage: fetch a GitHub issue, classify it, draft a maintainer response.
- Repo review: inspect `git status`, summarize risk, write a review checklist.
- Release notes: gather merged PR titles, cluster changes, draft a release note.
- Support ops: classify tickets, draft answers, write escalation notes.
- Research brief: fetch public data, summarize implications, produce a markdown brief.

## Roadmap

- MCP tool step.
- JSON schema validation for runbooks.
- Resume from a previous run directory.
- Native eval step for checking outputs.
- GitHub issue and PR helper steps.

## License

MIT
