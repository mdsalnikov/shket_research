import pathlib
import sys

p = pathlib.Path("agent/interfaces/cli.py")
for i, line in enumerate(p.read_text().splitlines(), 1):
    sys.stdout.write(f"{i:3}: {line}\n")
