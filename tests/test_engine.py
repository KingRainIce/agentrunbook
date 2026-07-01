import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
