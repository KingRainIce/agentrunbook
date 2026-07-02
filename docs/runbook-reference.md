# Runbook Reference

This document describes the AgentRunbook TOML format.

## Top-Level Tables

| Table | Required | Purpose |
| --- | --- | --- |
| `[runbook]` | No | Metadata, provider settings, workspace, and budgets. |
| `[context]` | No | User-defined values available to templates. |
| `[tools.shell]` | No | Allowlist for commands used by `shell` and `mcp_tool` steps. |
| `[[agents]]` | No | Role definitions used by LLM-backed steps. |
| `[[steps]]` | Yes | Ordered executable steps. |

## `[runbook]`

| Field | Default | Description |
| --- | --- | --- |
| `name` | File stem | Human-readable runbook name. |
| `description` | `""` | Short description shown in reports. |
| `provider` | `"mock"` | `mock` or `openai`. |
| `model` | `"mock-smart"` | Model name passed to the provider. |
| `workspace` | `".agentrunbook"` | Directory where run outputs are stored. |
| `max_steps` | `20` | Maximum number of steps allowed in the runbook. |
| `max_seconds` | `300` | Maximum runtime for the whole run. |
| `max_tool_seconds` | `30` | Default timeout for tool steps. |

Example:

```toml
[runbook]
name = "release-notes"
description = "Draft release notes from repository context."
provider = "openai"
model = "gpt-4.1-mini"
max_steps = 8
max_seconds = 240
max_tool_seconds = 30
```

## `[context]`

Context values are available directly by key and through the `context` namespace.

```toml
[context]
repo = "KingRainIce/agentrunbook"
audience = "open-source maintainers"
```

These can be referenced as:

```text
{{ repo }}
{{ context.repo }}
{{ audience }}
```

## `[tools.shell]`

Shell and MCP server commands are dry-run unless `--allow-shell` is passed. Even then, the command head must match this allowlist.

```toml
[tools.shell]
allow = ["git", "python", "pytest"]
```

Allowed values can be command heads such as `git`, or command prefixes such as `python scripts/tool.py`.

## `[[agents]]`

| Field | Required | Description |
| --- | --- | --- |
| `id` | Yes | Unique agent id. |
| `role` | No | Role text used in the system prompt. Defaults to the id. |
| `goal` | No | Goal text added to the system prompt. |
| `instructions` | No | Additional behavioral instructions. |

Example:

```toml
[[agents]]
id = "maintainer"
role = "Open-source maintainer"
goal = "Triage issues quickly without losing user context."
instructions = "Separate facts from guesses and suggest concrete next actions."
```

## `[[steps]]`

All steps share these fields:

| Field | Required | Description |
| --- | --- | --- |
| `id` | Yes | Unique step id. |
| `type` | Yes | One of the supported step types. |
| `save_as` | No | Saves `output` into context under this alias. |
| `allow_failure` | No | Continue the run if the step fails. |
| `timeout_seconds` | No | Tool timeout override for steps that call tools. |

Step ids must start with a letter and contain only letters, numbers, `_`, or `-`.

## `llm` Step

| Field | Required | Description |
| --- | --- | --- |
| `agent` | No | Agent id to use for the system prompt. |
| `prompt` | Yes | User prompt with template support. |

```toml
[[steps]]
id = "summarize"
type = "llm"
agent = "analyst"
save_as = "summary"
prompt = "Summarize this issue: {{ issue_text }}"
```

## `shell` Step

| Field | Required | Description |
| --- | --- | --- |
| `command` | Yes | Local command to run as argv. |

```toml
[[steps]]
id = "status"
type = "shell"
command = "git status --short"
save_as = "git_status"
allow_failure = true
```

## `http` Step

| Field | Required | Description |
| --- | --- | --- |
| `url` | Yes | HTTP URL to fetch. |

```toml
[[steps]]
id = "fetch_repo"
type = "http"
url = "https://api.github.com/repos/{{ repo }}"
save_as = "repo_json"
```

## `write` Step

| Field | Required | Description |
| --- | --- | --- |
| `path` | Yes | Relative artifact path. |
| `content` | Yes | File content with template support. |

```toml
[[steps]]
id = "write"
type = "write"
path = "brief.md"
content = "{{ summary }}"
```

## `github_issue_triage` Step

| Field | Required | Description |
| --- | --- | --- |
| `agent` | No | Agent id to use for triage. |
| `repo` | Yes | GitHub repository in `owner/name` form. |
| `issue` | Yes | Issue number. |
| `max_comments` | No | Number of comments to fetch, from 0 to 100. Defaults to 10. |
| `prompt` | No | Optional triage instructions. |

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

The step writes compact raw issue data to `artifacts/github/`.

## `mcp_tool` Step

| Field | Required | Description |
| --- | --- | --- |
| `command` | Yes | Local stdio MCP server command. |
| `tool` | Yes | MCP tool name. |
| `[steps.arguments]` | No | Tool arguments. Values support templates. |

```toml
[[steps]]
id = "echo"
type = "mcp_tool"
command = "python mcp-echo-server.py"
tool = "echo"

[steps.arguments]
text = "Hello {{ name }}"
```

MCP server commands follow the same dry-run and allowlist behavior as `shell` steps.

## Template Values

The template engine supports dotted paths:

```text
{{ run.id }}
{{ date }}
{{ steps.fetch_repo.output }}
{{ steps.status.metadata.returncode }}
{{ summary }}
```

Template resolution is strict. Missing values stop the run with an explicit error.

## Failure Behavior

By default, any failed step fails the run. Set `allow_failure = true` on optional probes:

```toml
[[steps]]
id = "diff_stat"
type = "shell"
command = "git diff --stat"
allow_failure = true
save_as = "diff_stat"
```

Failed optional steps still appear in `summary.json` and `trace.jsonl`.
