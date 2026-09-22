import argparse
import json
import os
import re
import sys
from collections.abc import Mapping


class ParseError(ValueError):
    """Некорректная или неподдерживаемая конструкция оболочки."""


def parse_command(line: str, env: Mapping[str, str] | None = None) -> list[str]:

    env = os.environ if env is None else env
    words: list[str] = []
    word = ""
    started = False
    quote = None
    i = 0

    def flush():
        nonlocal word, started
        if started:
            words.append(word)
        word, started = "", False

    while i < len(line):
        ch = line[i]
        if quote == "'":
            if ch == "'":
                quote = None
            else:
                word += ch
            i += 1
            continue
        if ch == "\\":
            if i + 1 == len(line):
                raise ParseError("незавершённое экранирование")
            following = line[i + 1]
            if quote == '"' and following not in '$"\\':
                word += "\\"
                started = True
                i += 1
                continue
            word += following
            started = True
            i += 2
            continue
        if ch == quote:
            quote = None
            i += 1
            continue
        if quote is None and ch in "'\"":
            quote = ch
            started = True
            i += 1
            continue
        if ch == "$":
            if line[i + 1:i + 2] == "(":
                raise ParseError("подстановка команд не поддерживается")
            if line[i + 1:i + 2] == "{":
                end = line.find("}", i + 2)
                if end == -1:
                    raise ParseError("не закрыта переменная ${...}")
                name = line[i + 2:end]
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                    raise ParseError("неверное имя переменной: " + name)
                i = end + 1
            else:
                match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", line[i + 1:])
                if not match:
                    word += "$"
                    started = True
                    i += 1
                    continue
                name = match.group()
                i += len(name) + 1
            value = env.get(name, "")
            if quote == '"':
                word += value
                started = True
            else:
                for part in re.split(r"([ \t\n]+)", value):
                    if part and part[0] in " \t\n":
                        flush()
                    elif part:
                        word += part
                        started = True
            continue
        if quote is None and ch.isspace():
            flush()
        elif quote is None and ch in "|;&<>()`":
            raise ParseError("оператор не поддерживается: " + ch)
        else:
            word += ch
            started = True
        i += 1
    if quote is not None:
        raise ParseError("незакрытая кавычка " + quote)
    flush()
    return words


def run(vfs_name: str) -> int:
    while True:
        try:
            line = input(f"{vfs_name}:/$ ")
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print("\nВвод отменён.")
            continue
        try:
            words = parse_command(line)
        except ParseError as error:
            print(f"Ошибка синтаксиса: {error}", file=sys.stderr)
            continue
        if not words:
            continue
        command, *args = words
        if command in ("ls", "cd"):
            print(f"{command}: аргументы = {json.dumps(args, ensure_ascii=False)}")
        elif command == "exit":
            if args:
                print("Ошибка: exit не принимает аргументы.", file=sys.stderr)
                continue
            print("Выход из эмулятора.")
            return 0
        else:
            print(f"Ошибка: команда не найдена: {command}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vfs", default="demo-vfs", help="имя виртуальной ФС")
    options = parser.parse_args()
    if not options.vfs.strip() or any(ord(ch) < 32 or ord(ch) == 127 for ch in options.vfs):
        parser.error("имя VFS должно быть непустым и без управляющих символов")
    return run(options.vfs)


if __name__ == "__main__":
    raise SystemExit(main())