import sys
raw = sys.stdin.buffer.read().decode("utf-8", "replace")
line = raw.split("\n")[0].strip()

import csv, io
row = next(csv.reader(io.StringIO(line)))
print("|".join(row))
