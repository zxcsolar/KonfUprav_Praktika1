import os
import subprocess
import sys
import unittest
import unittest.mock
from pathlib import Path

from console import ParseError, load_config, parse_command

class ParserTests(unittest.TestCase):

#проверка кавычек и переменных окружения
    def test_quotes_and_environment(self):
        env = {"HOME": "/home/test user", "FLAGS": "-a -l"}
        self.assertEqual(parse_command('ls "$HOME" ${FLAGS}', env),
                         ["ls", "/home/test user", "-a", "-l"])
        self.assertEqual(parse_command("cd '$HOME'", env), ["cd", "$HOME"])
        self.assertEqual(parse_command(r'ls \$HOME a\ b ""', env),
                         ["ls", "$HOME", "a b", ""])

#проверка отсутствующих переменных и отсутствия повторной подстановки
    def test_missing_and_no_recursive_expansion(self):
        self.assertEqual(parse_command('ls $MISSING "$MISSING"', {}), ["ls", ""])
        self.assertEqual(parse_command('ls "$X"', {"X": "$HOME;exit"}),
                         ["ls", "$HOME;exit"])

#проверка обработки синтаксических ошибок
    def test_errors(self):
        for line in ['ls "oops', "cd 'oops", "ls \\", "ls ${HOME", "ls ${1}",
                     "ls | cd", "ls $(exit)"]:
            with self.subTest(line=line), self.assertRaises(ParseError):
                parse_command(line)

#проверка работы с реальной переменной окружения
    def test_real_environment(self):
        with unittest.mock.patch.dict(os.environ, {"SHELL_TEST_VALUE": "actual value"}):
            self.assertEqual(parse_command('cd "$SHELL_TEST_VALUE"'), ["cd", "actual value"])

#проверка чтения конфигурационного файла
    def test_load_config(self):
        config_path = Path(__file__).with_name("config.ini")
        config = load_config(str(config_path))

        self.assertEqual(config["vfs"], "config-vfs")
        self.assertEqual(config["startup_script"], "startup.txt")

#проверка приоритета параметров командной строки над конфигурацией
    def test_cli_overrides_config(self):
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("console.py")),
                "--config", "config.ini",
                "--vfs", "cli-vfs"
            ],
            input="exit\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"}
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("VFS: cli-vfs", result.stdout)

#проверка остановки стартового скрипта при ошибке
    def test_startup_stops_on_error(self):
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("console.py")),
                "--startup", "startup_error.txt"
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"}
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("команда не найдена: unknown", result.stderr)
        self.assertNotIn("cd /home", result.stdout)

#проверка обработки ошибки чтения конфигурационного файла
    def test_config_read_error(self):
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("console.py")),
                "--config", "missing.ini"
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"}
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "ошибка чтения конфигурационного файла",
            result.stderr
        )

#проверка работы командной строки и корректного завершения эмулятора
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