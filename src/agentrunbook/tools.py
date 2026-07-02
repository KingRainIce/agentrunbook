from __future__ import annotations

import json
import os
import queue
import shlex
import subprocess
import threading
import time
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


def run_mcp_tool(
    command: str,
    cwd: Path,
    tool_name: str,
    arguments: dict[str, object],
    timeout_seconds: int,
    allowed_shell: tuple[str, ...],
    allow_shell: bool,
) -> tuple[str, dict[str, object]]:
    if not allow_shell:
        return (
            f"DRY RUN: MCP tool {tool_name} via {command} with {json.dumps(arguments, ensure_ascii=False)}",
            {"dry_run": True, "command": command, "tool": tool_name},
        )

    if not is_command_allowed(command, allowed_shell):
        allowed = ", ".join(allowed_shell) or "<empty>"
        raise ToolError(f"MCP server command is not in the runbook allowlist: {command!r}; allowed: {allowed}")

    args = split_command(command)
    try:
        process = subprocess.Popen(
            args,
            cwd=str(cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError as exc:
        raise ToolError(f"MCP server command not found: {args[0]}") from exc

    if process.stdin is None or process.stdout is None:
        raise ToolError("MCP server did not expose stdio pipes")

    stdout_queue = _start_stdout_reader(process.stdout)
    deadline = time.monotonic() + timeout_seconds
    try:
        _send_json(
            process.stdin,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "agentrunbook", "version": "0.1.0"},
                },
            },
        )
        _read_json_response(stdout_queue, 1, deadline, process)
        _send_json(
            process.stdin,
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
        )
        _send_json(
            process.stdin,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            },
        )
        response = _read_json_response(stdout_queue, 2, deadline, process)
    finally:
        _terminate_process(process)

    if "error" in response:
        raise ToolError(f"MCP tool {tool_name!r} failed: {response['error']}")
    result = response.get("result", {})
    return _format_mcp_result(result), {"dry_run": False, "command": command, "tool": tool_name}


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


def fetch_github_issue(repo: str, issue: str, max_comments: int, timeout_seconds: int) -> dict[str, object]:
    issue_data = github_api_get(f"/repos/{repo}/issues/{issue}", timeout_seconds)
    if not isinstance(issue_data, dict):
        raise ToolError(f"GitHub issue response was not an object for {repo}#{issue}")
    comments: list[dict[str, object]] = []
    if max_comments > 0 and int(issue_data.get("comments", 0)) > 0:
        comments_url = f"/repos/{repo}/issues/{issue}/comments?per_page={max_comments}"
        comments_data = github_api_get(comments_url, timeout_seconds)
        if isinstance(comments_data, list):
            comments = [_compact_comment(item) for item in comments_data[:max_comments]]

    return {
        "repo": repo,
        "issue": issue,
        "url": issue_data.get("html_url", ""),
        "api_url": issue_data.get("url", ""),
        "title": issue_data.get("title", ""),
        "state": issue_data.get("state", ""),
        "author": _login(issue_data.get("user")),
        "body": _truncate(str(issue_data.get("body") or ""), 8000),
        "labels": [item.get("name", "") for item in issue_data.get("labels", []) if isinstance(item, dict)],
        "assignees": [_login(item) for item in issue_data.get("assignees", []) if isinstance(item, dict)],
        "milestone": _compact_milestone(issue_data.get("milestone")),
        "created_at": issue_data.get("created_at", ""),
        "updated_at": issue_data.get("updated_at", ""),
        "comments_count": issue_data.get("comments", 0),
        "comments": comments,
    }


def github_api_get(path: str, timeout_seconds: int) -> object:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "agentrunbook/0.1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = path if path.startswith("http") else f"https://api.github.com{path}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ToolError(f"GitHub API returned HTTP {exc.code} for {url}: {_truncate(body)}") from exc
    except urllib.error.URLError as exc:
        raise ToolError(f"GitHub API request failed for {url}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ToolError(f"GitHub API returned invalid JSON for {url}") from exc


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
    return shlex.split(command, posix=True)


def _join_streams(stdout: str, stderr: str) -> str:
    if stdout and stderr:
        return f"{stdout}\n{stderr}"
    return stdout or stderr


def _truncate(value: str, limit: int = 12000) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 24] + "\n... <truncated output>"


def _compact_comment(comment: dict[str, object]) -> dict[str, object]:
    return {
        "author": _login(comment.get("user")),
        "created_at": comment.get("created_at", ""),
        "updated_at": comment.get("updated_at", ""),
        "body": _truncate(str(comment.get("body") or ""), 4000),
    }


def _compact_milestone(value: object) -> str | None:
    if isinstance(value, dict):
        return str(value.get("title") or "")
    return None


def _login(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("login") or "")
    return ""


def _send_json(stream, payload: dict[str, object]) -> None:
    stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
    stream.flush()


def _start_stdout_reader(stream) -> queue.Queue[str]:
    messages: queue.Queue[str] = queue.Queue()

    def read_lines() -> None:
        for line in iter(stream.readline, ""):
            messages.put(line)

    thread = threading.Thread(target=read_lines, daemon=True)
    thread.start()
    return messages


def _read_json_response(
    messages: queue.Queue[str],
    response_id: int,
    deadline: float,
    process: subprocess.Popen[str],
) -> dict[str, object]:
    while True:
        if process.poll() is not None and messages.empty():
            stderr = process.stderr.read().strip() if process.stderr else ""
            detail = f": {stderr}" if stderr else ""
            raise ToolError(f"MCP server exited before response id {response_id}{detail}")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ToolError(f"MCP server timed out waiting for response id {response_id}")
        try:
            line = messages.get(timeout=min(remaining, 0.1))
        except queue.Empty as exc:
            if time.monotonic() >= deadline:
                raise ToolError(f"MCP server timed out waiting for response id {response_id}") from exc
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("id") == response_id:
            return payload


def _format_mcp_result(result: object) -> str:
    if not isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False)
    content = result.get("content")
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(json.dumps(item, ensure_ascii=False))
        if parts:
            return "\n".join(parts)
    return json.dumps(result, ensure_ascii=False, indent=2)


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        _close_process_pipes(process)
        return
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)
    _close_process_pipes(process)


def _close_process_pipes(process: subprocess.Popen[str]) -> None:
    for stream in (process.stdin, process.stdout, process.stderr):
        if stream:
            stream.close()
