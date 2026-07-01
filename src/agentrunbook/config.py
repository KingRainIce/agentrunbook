from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

from .models import Agent, Runbook, Step


class ConfigError(ValueError):
    """Raised when a runbook is invalid."""


STEP_TYPES = {"llm", "shell", "http", "write"}
ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def load_runbook(path: str | Path) -> Runbook:
    runbook_path = Path(path)
    with runbook_path.open("rb") as file:
        data = tomllib.load(file)
    return parse_runbook(data, default_name=runbook_path.stem)


def parse_runbook(data: dict[str, Any], default_name: str = "runbook") -> Runbook:
    meta = _as_dict(data.get("runbook", {}), "runbook")
    context = _as_dict(data.get("context", {}), "context")
    tools = _as_dict(data.get("tools", {}), "tools")
    shell_tools = _as_dict(tools.get("shell", {}), "tools.shell")

    agents = tuple(_parse_agent(item) for item in data.get("agents", []))
    steps = tuple(_parse_step(item) for item in data.get("steps", []))
    allowed_shell = tuple(str(item) for item in shell_tools.get("allow", []))

    runbook = Runbook(
        name=str(meta.get("name", default_name)),
        description=str(meta.get("description", "")),
        provider=str(meta.get("provider", "mock")),
        model=str(meta.get("model", "mock-smart")),
        workspace=str(meta.get("workspace", ".agentrunbook")),
        max_steps=int(meta.get("max_steps", 20)),
        max_seconds=int(meta.get("max_seconds", 300)),
        max_tool_seconds=int(meta.get("max_tool_seconds", 30)),
        context=context,
        agents=agents,
        steps=steps,
        allowed_shell=allowed_shell,
    )
    validate_runbook(runbook)
    return runbook


def validate_runbook(runbook: Runbook) -> None:
    if not runbook.name:
        raise ConfigError("runbook.name cannot be empty")
    if runbook.max_steps < 1:
        raise ConfigError("runbook.max_steps must be at least 1")
    if runbook.max_seconds < 1:
        raise ConfigError("runbook.max_seconds must be at least 1")
    if not runbook.steps:
        raise ConfigError("runbook must define at least one [[steps]] entry")

    agent_ids = set()
    for agent in runbook.agents:
        _validate_id(agent.id, f"agent id {agent.id!r}")
        if agent.id in agent_ids:
            raise ConfigError(f"duplicate agent id: {agent.id}")
        agent_ids.add(agent.id)

    step_ids = set()
    for step in runbook.steps:
        _validate_id(step.id, f"step id {step.id!r}")
        if step.id in step_ids:
            raise ConfigError(f"duplicate step id: {step.id}")
        step_ids.add(step.id)
        if step.type not in STEP_TYPES:
            raise ConfigError(f"step {step.id!r} has unsupported type {step.type!r}")
        if step.agent and step.agent not in agent_ids:
            raise ConfigError(f"step {step.id!r} references unknown agent {step.agent!r}")
        if step.type == "llm" and not step.prompt:
            raise ConfigError(f"llm step {step.id!r} requires prompt")
        if step.type == "shell" and not step.command:
            raise ConfigError(f"shell step {step.id!r} requires command")
        if step.type == "http" and not step.url:
            raise ConfigError(f"http step {step.id!r} requires url")
        if step.type == "write" and (not step.path or step.content is None):
            raise ConfigError(f"write step {step.id!r} requires path and content")


def _parse_agent(data: Any) -> Agent:
    item = _as_dict(data, "agents entry")
    return Agent(
        id=str(_required(item, "id", "agents entry")),
        role=str(item.get("role", item.get("id", ""))),
        goal=str(item.get("goal", "")),
        instructions=str(item.get("instructions", "")),
    )


def _parse_step(data: Any) -> Step:
    item = _as_dict(data, "steps entry")
    return Step(
        id=str(_required(item, "id", "steps entry")),
        type=str(_required(item, "type", f"step {item.get('id', '<unknown>')}")),
        agent=_optional_str(item.get("agent")),
        prompt=_optional_str(item.get("prompt")),
        command=_optional_str(item.get("command")),
        url=_optional_str(item.get("url")),
        path=_optional_str(item.get("path")),
        content=_optional_str(item.get("content")),
        save_as=_optional_str(item.get("save_as")),
        allow_failure=bool(item.get("allow_failure", False)),
        timeout_seconds=_optional_int(item.get("timeout_seconds")),
        raw=dict(item),
    )


def _as_dict(value: Any, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"{label} must be a table")
    return value


def _required(item: dict[str, Any], key: str, label: str) -> Any:
    value = item.get(key)
    if value in (None, ""):
        raise ConfigError(f"{label} requires {key}")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _validate_id(value: str, label: str) -> None:
    if not ID_PATTERN.match(value):
        raise ConfigError(f"{label} must start with a letter and contain only letters, numbers, _ or -")
