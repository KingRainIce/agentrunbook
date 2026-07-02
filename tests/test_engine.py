import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentrunbook.config import parse_runbook
from agentrunbook.engine import Runner


class EngineTests(unittest.TestCase):
    def test_mock_run_writes_artifact_and_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            runbook = parse_runbook(
                {
                    "runbook": {"name": "demo", "workspace": ".runs"},
                    "context": {"goal": "Ship something useful"},
                    "agents": [{"id": "planner", "role": "Planner"}],
                    "steps": [
                        {
                            "id": "plan",
                            "type": "llm",
                            "agent": "planner",
                            "save_as": "plan",
                            "prompt": "Goal: {{ goal }}",
                        },
                        {
                            "id": "write",
                            "type": "write",
                            "path": "plan.md",
                            "content": "{{ plan }}",
                        },
                    ],
                }
            )
            result = Runner(runbook, cwd=cwd).run()
            self.assertEqual(result.status, "ok")
            self.assertTrue(result.trace_path.exists())
            self.assertTrue((result.run_dir / "artifacts" / "plan.md").exists())

    def test_shell_is_dry_run_without_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            runbook = parse_runbook(
                {
                    "runbook": {"name": "shell-demo", "workspace": ".runs"},
                    "tools": {"shell": {"allow": ["python"]}},
                    "steps": [{"id": "version", "type": "shell", "command": "python --version"}],
                }
            )
            result = Runner(runbook, cwd=cwd, allow_shell=False).run()
            self.assertIn("DRY RUN", result.steps[0].output)

    def test_github_issue_triage_writes_raw_issue_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            runbook = parse_runbook(
                {
                    "runbook": {"name": "issue-demo", "workspace": ".runs"},
                    "agents": [{"id": "maintainer", "role": "Maintainer"}],
                    "steps": [
                        {
                            "id": "triage",
                            "type": "github_issue_triage",
                            "agent": "maintainer",
                            "repo": "owner/project",
                            "issue": 7,
                            "save_as": "triage",
                        }
                    ],
                }
            )
            provider = FakeProvider("triage output")
            issue_data = {
                "repo": "owner/project",
                "issue": "7",
                "url": "https://github.com/owner/project/issues/7",
                "title": "Exports fail",
                "state": "open",
                "author": "octocat",
                "body": "The export fails.",
                "labels": ["bug"],
                "comments": [],
            }
            with patch("agentrunbook.engine.fetch_github_issue", return_value=issue_data):
                result = Runner(runbook, provider=provider, cwd=cwd).run()
            self.assertEqual(result.steps[0].output, "triage output")
            self.assertIn("GitHub issue data", provider.messages[-1]["content"])
            raw_artifact = Path(result.steps[0].metadata["raw_artifact"])
            self.assertTrue(raw_artifact.exists())
            self.assertIn('"title": "Exports fail"', raw_artifact.read_text(encoding="utf-8"))

    def test_mcp_tool_runs_stdio_server_when_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            server = cwd / "mcp_echo_server.py"
            server.write_text(MCP_ECHO_SERVER, encoding="utf-8")
            runbook = parse_runbook(
                {
                    "runbook": {"name": "mcp-demo", "workspace": ".runs"},
                    "context": {"name": "World"},
                    "tools": {"shell": {"allow": ["python"]}},
                    "steps": [
                        {
                            "id": "echo",
                            "type": "mcp_tool",
                            "command": f'python "{server}"',
                            "tool": "echo",
                            "arguments": {"text": "Hello {{ name }}"},
                        }
                    ],
                }
            )
            result = Runner(runbook, cwd=cwd, allow_shell=True).run()
            self.assertEqual(result.steps[0].status, "ok")
            self.assertIn("Hello World", result.steps[0].output)


class FakeProvider:
    def __init__(self, output):
        self.output = output
        self.messages = []

    def generate(self, messages, model, temperature=0.2):
        self.messages = messages
        return self.output


MCP_ECHO_SERVER = r'''
import json
import sys


def send(payload):
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    if method == "initialize":
        send({
            "jsonrpc": "2.0",
            "id": message["id"],
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "test-echo", "version": "0.1.0"},
            },
        })
    elif method == "tools/call":
        args = message.get("params", {}).get("arguments", {})
        send({
            "jsonrpc": "2.0",
            "id": message["id"],
            "result": {
                "content": [{"type": "text", "text": args.get("text", "")}],
                "isError": False,
            },
        })
'''


if __name__ == "__main__":
    unittest.main()
