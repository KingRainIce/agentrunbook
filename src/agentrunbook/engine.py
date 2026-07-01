from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import Agent, RunResult, Runbook, Step, StepResult
from .providers import ModelProvider, make_provider
from .templating import render_template
from .tools import http_get, run_shell_command, write_artifact
from .tracing import Tracer


class RunError(RuntimeError):
    """Raised when a runbook fails."""


class Runner:
    def __init__(
        self,
        runbook: Runbook,
        *,
        runbook_path: Path | None = None,
        provider: ModelProvider | None = None,
        workspace: Path | None = None,
        allow_shell: bool = False,
        cwd: Path | None = None,
    ) -> None:
        self.runbook = runbook
        self.runbook_path = runbook_path
        self.provider = provider or make_provider(runbook.provider)
        self.workspace = workspace or Path(runbook.workspace)
        self.allow_shell = allow_shell
        self.cwd = cwd or (runbook_path.parent if runbook_path else Path.cwd())

    def run(self) -> RunResult:
        run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        run_dir = (self.cwd / self.workspace / "runs" / run_id).resolve()
        run_dir.mkdir(parents=True, exist_ok=True)
        tracer = Tracer(run_dir / "trace.jsonl")
        context = self._initial_context(run_id, run_dir)
        started = time.monotonic()
        results: list[StepResult] = []
        status = "ok"

        tracer.emit("run_start", run_id=run_id, runbook=self.runbook.name, cwd=str(self.cwd))
        try:
            if len(self.runbook.steps) > self.runbook.max_steps:
                raise RunError(
                    f"runbook defines {len(self.runbook.steps)} steps, exceeding max_steps={self.runbook.max_steps}"
                )
            for index, step in enumerate(self.runbook.steps, start=1):
                if time.monotonic() - started > self.runbook.max_seconds:
                    raise RunError(f"run exceeded max_seconds={self.runbook.max_seconds}")
                tracer.emit("step_start", step=step.id, index=index, type=step.type, agent=step.agent)
                step_started = time.monotonic()
                try:
                    result = self._run_step(step, context)
                except Exception as exc:
                    if not step.allow_failure:
                        tracer.emit("step_error", step=step.id, error=str(exc))
                        raise
                    result = StepResult(
                        id=step.id,
                        type=step.type,
                        status="failed",
                        output=str(exc),
                        metadata={"allow_failure": True},
                    )
                result.metadata["elapsed_seconds"] = round(time.monotonic() - step_started, 3)
                results.append(result)
                self._save_step_context(context, step, result)
                tracer.emit(
                    "step_end",
                    step=step.id,
                    status=result.status,
                    elapsed_seconds=result.metadata["elapsed_seconds"],
                    output_preview=result.output[:300],
                )
        except Exception as exc:
            status = "failed"
            tracer.emit("run_error", error=str(exc))
            self._write_summary(run_dir, run_id, status, results, error=str(exc))
            self._write_report(run_dir, run_id, status, results, error=str(exc))
            raise RunError(str(exc)) from exc

        summary_path = self._write_summary(run_dir, run_id, status, results)
        report_path = self._write_report(run_dir, run_id, status, results)
        tracer.emit("run_end", status=status, steps=len(results))
        return RunResult(
            run_id=run_id,
            run_dir=run_dir,
            status=status,
            steps=results,
            summary_path=summary_path,
            trace_path=tracer.path,
            report_path=report_path,
        )

    def _run_step(self, step: Step, context: dict[str, Any]) -> StepResult:
        if step.type == "llm":
            return self._run_llm_step(step, context)
        if step.type == "shell":
            return self._run_shell_step(step, context)
        if step.type == "http":
            return self._run_http_step(step, context)
        if step.type == "write":
            return self._run_write_step(step, context)
        raise RunError(f"unsupported step type: {step.type}")

    def _run_llm_step(self, step: Step, context: dict[str, Any]) -> StepResult:
        agent = self.runbook.agent_by_id(step.agent)
        prompt = render_template(step.prompt or "", context)
        messages = [
            {"role": "system", "content": self._system_prompt(agent)},
            {"role": "user", "content": prompt},
        ]
        output = self.provider.generate(messages, self.runbook.model)
        return StepResult(
            id=step.id,
            type=step.type,
            status="ok",
            output=output,
            metadata={"agent": step.agent, "model": self.runbook.model},
        )

    def _run_shell_step(self, step: Step, context: dict[str, Any]) -> StepResult:
        command = render_template(step.command or "", context)
        timeout = step.timeout_seconds or self.runbook.max_tool_seconds
        output, metadata = run_shell_command(
            command=command,
            cwd=self.cwd,
            timeout_seconds=timeout,
            allowed_shell=self.runbook.allowed_shell,
            allow_shell=self.allow_shell,
        )
        return StepResult(id=step.id, type=step.type, status="ok", output=output, metadata=metadata)

    def _run_http_step(self, step: Step, context: dict[str, Any]) -> StepResult:
        url = render_template(step.url or "", context)
        timeout = step.timeout_seconds or self.runbook.max_tool_seconds
        output, metadata = http_get(url, timeout)
        return StepResult(id=step.id, type=step.type, status="ok", output=output, metadata=metadata)

    def _run_write_step(self, step: Step, context: dict[str, Any]) -> StepResult:
        path = render_template(step.path or "", context)
        content = render_template(step.content or "", context)
        target = write_artifact(context["run"]["dir_path"], path, content)
        return StepResult(
            id=step.id,
            type=step.type,
            status="ok",
            output=str(target),
            metadata={"path": str(target)},
        )

    def _initial_context(self, run_id: str, run_dir: Path) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        context: dict[str, Any] = {
            **self.runbook.context,
            "context": dict(self.runbook.context),
            "runbook": {
                "name": self.runbook.name,
                "description": self.runbook.description,
            },
            "run": {
                "id": run_id,
                "dir": str(run_dir),
                "dir_path": run_dir,
            },
            "now": now.isoformat(),
            "date": now.date().isoformat(),
            "steps": {},
        }
        return context

    def _save_step_context(self, context: dict[str, Any], step: Step, result: StepResult) -> None:
        context["steps"][step.id] = result.to_context()
        if step.save_as:
            context[step.save_as] = result.output

    def _system_prompt(self, agent: Agent | None) -> str:
        if agent is None:
            return (
                "You are a precise runbook agent. Follow the user's task, be concise, "
                "name assumptions, and produce useful artifacts."
            )
        sections = [
            f"You are {agent.role}.",
            f"Goal: {agent.goal}" if agent.goal else "",
            agent.instructions,
            "Be specific, practical, and traceable. Prefer structured output when helpful.",
        ]
        return "\n".join(section for section in sections if section)

    def _write_summary(
        self,
        run_dir: Path,
        run_id: str,
        status: str,
        results: list[StepResult],
        *,
        error: str | None = None,
    ) -> Path:
        path = run_dir / "summary.json"
        payload = {
            "run_id": run_id,
            "runbook": self.runbook.name,
            "status": status,
            "error": error,
            "steps": [result.to_context() for result in results],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path

    def _write_report(
        self,
        run_dir: Path,
        run_id: str,
        status: str,
        results: list[StepResult],
        *,
        error: str | None = None,
    ) -> Path:
        path = run_dir / "report.md"
        lines = [
            f"# {self.runbook.name}",
            "",
            f"- Run: `{run_id}`",
            f"- Status: `{status}`",
        ]
        if error:
            lines.append(f"- Error: `{error}`")
        lines.append("")
        for result in results:
            lines.extend(
                [
                    f"## {result.id}",
                    "",
                    f"- Type: `{result.type}`",
                    f"- Status: `{result.status}`",
                    "",
                    "```text",
                    result.output,
                    "```",
                    "",
                ]
            )
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
