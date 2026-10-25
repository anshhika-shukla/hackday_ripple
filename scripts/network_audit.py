"""Record every network connection the RIPPLE process opens during one `ripple check`.

Uses Python's audit hooks (socket.connect events), so it needs no extra tools.
Usage: .venv/bin/python scripts/network_audit.py --repo targets/canteen --run --no-cache
Prints each address contacted and whether all of them were on this machine.
"""

import sys

contacted: list[str] = []


def hook(event: str, args: tuple) -> None:
    if event == "socket.connect":
        address = args[1]
        contacted.append(str(address))


sys.addaudithook(hook)

from ripple.cli import main  # noqa: E402

code = main(["check", *sys.argv[1:]])
local = all(a.startswith(("('127.", "('::1'", "('localhost'")) or a.startswith("/") for a in contacted)
print("\nNetwork connections opened by RIPPLE:")
for a in sorted(set(contacted)):
    print(f"  {a}  x{contacted.count(a)}")
print(f"All on this machine (localhost): {'yes' if local else 'NO'}; {len(contacted)} connection(s)")
sys.exit(code)
