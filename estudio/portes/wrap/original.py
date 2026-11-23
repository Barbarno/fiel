import sys
raw = sys.stdin.buffer.read().decode("utf-8", "replace")
line = raw.split("\n")[0].strip()

import textwrap
print("\n".join(textwrap.wrap(line, 10)))
