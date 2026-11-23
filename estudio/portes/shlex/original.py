import sys
raw = sys.stdin.buffer.read().decode("utf-8", "replace")
line = raw.split("\n")[0].strip()

import shlex
print("|".join(shlex.split(line)))
