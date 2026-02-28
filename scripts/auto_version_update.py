#!/usr/bin/env python3
"""
Автоматическое обновление версии после merge PR.

Этот скрипт:
1. Читает текущую версию из VERSION файла
2. Инкрементирует patch версию (например, 0.0.2 -> 0.0.3)
3. Записывает новую версию в VERSION
4. Создает коммит и пушит изменения

Использование:
    python scripts/auto_version_update.py [--major|--minor|--patch]

По умолчанию инкрементирует patch версию.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def get_current_version(version_file: Path) -> tuple[int, int, int]:
    """Читает текущую версию из файла."""
    if not version_file.exists():
        return 0, 0, 1

    content = version_file.read_text().strip()
    parts = content.split(".")

    if len(parts) != 3:
        print(f"Invalid version format: {content}, expected X.Y.Z")
        sys.exit(1)

    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        print(f"Invalid version format: {content}, expected X.Y.Z")
        sys.exit(1)


def increment_version(
    major: int, minor: int, patch: int, increment_type: str
) -> tuple[int, int, int]:
    """Инкрементирует версию в зависимости от типа."""
    if increment_type == "major":
        return major + 1, 0, 0
    elif increment_type == "minor":
        return major, minor + 1, 0
    else:  # patch
        return major, minor, patch + 1


def run_git_command(args: list[str]) -> None:
    """Выполняет git команду."""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Git command failed: git {' '.join(args)}")
        print(f"Error: {result.stderr}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Обновление версии агента")
    parser.add_argument(
        "--major",
        action="store_true",
        help="Инкрементировать major версию (X.0.0)",
    )
    parser.add_argument(
        "--minor",
        action="store_true",
        help="Инкрементировать minor версию (0.Y.0)",
    )
    parser.add_argument(
        "--patch",
        action="store_true",
        default=True,
        help="Инкрементировать patch версию (0.0.Z) [по умолчанию]",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Не создавать коммит и не пушить изменения",
    )

    args = parser.parse_args()

    # Определяем тип инкремента
    if args.major:
        increment_type = "major"
    elif args.minor:
        increment_type = "minor"
    else:
        increment_type = "patch"

    # Находим VERSION файл
    version_file = Path(__file__).parent.parent / "VERSION"

    # Читаем текущую версию
    major, minor, patch = get_current_version(version_file)
    old_version = f"{major}.{minor}.{patch}"

    # Инкрементируем версию
    major, minor, patch = increment_version(major, minor, patch, increment_type)
    new_version = f"{major}.{minor}.{patch}"

    # Записываем новую версию
    version_file.write_text(new_version + "\n")
    print(f"Version updated: {old_version} -> {new_version}")

    if args.no_commit:
        return

    # Создаем коммит
    run_git_command(["add", "VERSION"])
    run_git_command(["commit", "-m", f"chore: bump version to {new_version}"])

    # Пушим изменения
    run_git_command(["push"])
    print(f"Version {new_version} committed and pushed")


if __name__ == "__main__":
    main()
