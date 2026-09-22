import os
import subprocess
import sys
import unittest
import unittest.mock
from pathlib import Path

from console import ParseError, parse_command


class ParserTests(unittest.TestCase):
    def test_quotes_and_environment(self):
        env = {"HOME": "/home/test user", "FLAGS": "-a -l"}
        self.assertEqual(parse_command('ls "$HOME" ${FLAGS}', env),
                         ["ls", "/home/test user", "-a", "-l"])
        self.assertEqual(parse_command("cd '$HOME'", env), ["cd", "$HOME"])
        self.assertEqual(parse_command(r'ls \$HOME a\ b ""', env),
                         ["ls", "$HOME", "a b", ""])

    def test_missing_and_no_recursive_expansion(self):
        self.assertEqual(parse_command('ls $MISSING "$MISSING"', {}), ["ls", ""])
        self.assertEqual(parse_command('ls "$X"', {"X": "$HOME;exit"}),
                         ["ls", "$HOME;exit"])

    def test_errors(self):
        for line in ['ls "oops', "cd 'oops", "ls \\", "ls ${HOME", "ls ${1}",
                     "ls | cd", "ls $(exit)"]:
            with self.subTest(line=line), self.assertRaises(ParseError):
                parse_command(line)

    def test_real_environment(self):
        with unittest.mock.patch.dict(os.environ, {"SHELL_TEST_VALUE": "actual value"}):
            self.assertEqual(parse_command('cd "$SHELL_TEST_VALUE"'), ["cd", "actual value"])

    def test_cli_recovers_and_exits(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("console.py")), "--vfs", "test-vfs"],
            input='\nls -l\nunknown\nls "oops\nexit extra\ncd /tmp\nexit\nls NEVER\n',
            capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.assertEqual(result.returncode, 0)
        self.assertIn("test-vfs:/$", result.stdout)
        self.assertIn('cd: аргументы = ["/tmp"]', result.stdout)
        self.assertNotIn("NEVER", result.stdout)
        self.assertIn("команда не найдена", result.stderr)
        self.assertIn("Ошибка синтаксиса", result.stderr)
        self.assertIn("exit не принимает", result.stderr)


if __name__ == "__main__":
    unittest.main()