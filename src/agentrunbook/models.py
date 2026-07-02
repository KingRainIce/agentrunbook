from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Agent:
    id: str
    role: str
    goal: str = ""
    instructions: str = ""


@dataclass(frozen=True)
class Step:
    id: str
    type: str
    agent: str | None = None
    prompt: str | None = None
    command: str | None = None
    url: str | None = None
    repo: str | None = None
    issue: str | None = None
    tool: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    path: str | None = None
    content: str | None = None
    save_as: str | None = None
    allow_failure: bool = False
    timeout_seconds: int | None = None
    max_comments: int = 10
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Runbook:
    name: str
    description: str
    agents: tuple[Agent, ...]
    steps: tuple[Step, ...]
    context: dict[str, Any] = field(default_factory=dict)
    provider: str = "mock"
    model: str = "mock-smart"
    workspace: str = ".agentrunbook"
    max_steps: int = 20
    max_seconds: int = 300
    max_tool_seconds: int = 30
    allowed_shell: tuple[str, ...] = ()

    def agent_by_id(self, agent_id: str | None) -> Agent | None:
        if agent_id is None:
            return None
        return next((agent for agent in self.agents if agent.id == agent_id), None)


@dataclass
class StepResult:
    id: str
    type: str
    status: str
    output: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_context(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "output": self.output,
            "metadata": self.metadata,
        }


@dataclass
class RunResult:
    run_id: str
    run_dir: Path
    status: str
    steps: list[StepResult]
    summary_path: Path
    trace_path: Path
    report_path: Path
