import unittest

from agentrunbook.templating import TemplateError, render_template


class TemplateTests(unittest.TestCase):
    def test_renders_nested_values(self):
        context = {"ticket": "Export failed", "steps": {"triage": {"output": "P1"}}}
        rendered = render_template("{{ ticket }} => {{ steps.triage.output }}", context)
        self.assertEqual(rendered, "Export failed => P1")

    def test_missing_value_is_explicit(self):
        with self.assertRaises(TemplateError):
            render_template("{{ missing.value }}", {})


if __name__ == "__main__":
    unittest.main()
