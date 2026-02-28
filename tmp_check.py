import pathlib

p = pathlib.Path("agent/interfaces/cli.py")
for i, line in enumerate(p.read_text().splitlines(), 1):
    if line.startswith("+"):
        print("Plus line", i, repr(line))
    if any(ord(c) > 127 for c in line):
        print("Non-ascii line", i, repr(line))
