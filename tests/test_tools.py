import unittest

from agentrunbook.tools import split_command


class ToolTests(unittest.TestCase):
    def test_split_command_removes_quotes_from_paths(self):
        command = '"C:\\Program Files\\Python312\\python.exe" "C:\\tmp\\server.py"'
        self.assertEqual(
            split_command(command),
            ["C:\\Program Files\\Python312\\python.exe", "C:\\tmp\\server.py"],
        )


if __name__ == "__main__":
    unittest.main()
