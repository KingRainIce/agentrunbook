import unittest

from agentrunbook.config import ConfigError, parse_runbook


class ConfigTests(unittest.TestCase):
    def test_parse_minimal_runbook(self):
        runbook = parse_runbook(
            {
                "runbook": {"name": "demo"},
                "agents": [{"id": "writer", "role": "Writer"}],
                "steps": [{"id": "draft", "type": "llm", "agent": "writer", "prompt": "Hello"}],
            }
        )
        self.assertEqual(runbook.name, "demo")
        self.assertEqual(runbook.agents[0].id, "writer")
        self.assertEqual(runbook.steps[0].id, "draft")

    def test_unknown_agent_fails_validation(self):
        with self.assertRaises(ConfigError):
            parse_runbook(
                {
                    "runbook": {"name": "bad"},
                    "steps": [{"id": "draft", "type": "llm", "agent": "missing", "prompt": "Hello"}],
                }
            )


if __name__ == "__main__":
    unittest.main()
