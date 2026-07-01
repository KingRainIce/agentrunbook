# Contributing

Thanks for helping make AgentRunbook better.

## Local Setup

```bash
python -m pip install -e .
python -m unittest discover -s tests
```

## Project Principles

- Keep the first-run experience boringly reliable.
- Prefer readable runbook behavior over hidden magic.
- Add dependencies only when they unlock a clear user benefit.
- Tool steps must be auditable, bounded, and explicit.
- Examples should solve real workflows, not only toy prompts.

## Pull Requests

Please include:

- A short description of the workflow or bug being improved.
- Tests for runtime behavior.
- README or example updates when user-facing behavior changes.
