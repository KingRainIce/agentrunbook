from __future__ import annotations

import os
import shlex
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


class ToolError(RuntimeError):
    """Raised when a tool step fails."""


def run_shell_command(
    command: str,
    cwd: Path,
    timeout_seconds: int,
    allowed_shell: tuple[str, ...],
    allow_shell: bool,
) -> tuple[str, dict[str, object]]:
    if not allow_shell:
        return f"DRY RUN: {command}", {"dry_run": True, "command": command}

    if not is_command_allowed(command, allowed_shell):
        allowed = ", ".join(allowed_shell) or "<empty>"
        raise ToolError(f"command is not in the runbook allowlist: {command!r}; allowed: {allowed}")

    args = split_command(command)
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ToolError(f"command not found: {args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ToolError(f"command timed out after {timeout_seconds}s: {command}") from exc

    output = _join_streams(completed.stdout, completed.stderr)
    metadata = {
        "dry_run": False,
        "command": command,
        "returncode": completed.returncode,
    }
    if completed.returncode != 0:
        raise ToolError(f"command exited with {completed.returncode}: {output.strip()}")
    return output.strip(), metadata


def http_get(url: str, timeout_seconds: int) -> tuple[str, dict[str, object]]:
    request = urllib.request.Request(url, headers={"User-Agent": "agentrunbook/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
            metadata = {
                "status": response.status,
                "url": response.geturl(),
                "content_type": response.headers.get("content-type", ""),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ToolError(f"HTTP {exc.code} from {url}: {_truncate(body)}") from exc
    except urllib.error.URLError as exc:
        raise ToolError(f"HTTP request failed for {url}: {exc}") from exc
    return _truncate(body), metadata


def write_artifact(run_dir: Path, relative_path: str, content: str) -> Path:
    artifacts_dir = run_dir / "artifacts"
    target = (artifacts_dir / relative_path).resolve()
    artifacts_root = artifacts_dir.resolve()
    if artifacts_root != target and artifacts_root not in target.parents:
        raise ToolError(f"artifact path escapes run directory: {relative_path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def is_command_allowed(command: str, allowed_shell: tuple[str, ...]) -> bool:
    if not allowed_shell:
        return False
    try:
        head = Path(split_command(command)[0]).name.lower()
    except (IndexError, ValueError):
        return False
    normalized = command.strip().lower()
    for item in allowed_shell:
        allowed = item.strip().lower()
        if not allowed:
            continue
        if " " in allowed and (normalized == allowed or normalized.startswith(f"{allowed} ")):
            return True
        if " " not in allowed and head in {allowed, f"{allowed}.exe", f"{allowed}.cmd", f"{allowed}.bat"}:
            return True
    return False


def split_command(command: str) -> list[str]:
    return shlex.split(command, posix=(os.name != "nt"))


def _join_streams(stdout: str, stderr: str) -> str:
    if stdout and stderr:
        return f"{stdout}\n{stderr}"
    return stdout or stderr


def _truncate(value: str, limit: int = 12000) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 24] + "\n... <truncated output>"
