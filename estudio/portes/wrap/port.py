import sys
raw = sys.stdin.buffer.read().decode("utf-8", "replace")
line = raw.split("\n")[0].strip()
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

lines, cur = [], ""
for word in line.split():
    if not cur:
        cur = word
    elif len(cur) + 1 + len(word) <= 10:
        cur += " " + word
    else:
        lines.append(cur)
        cur = word
if cur:
    lines.append(cur)
print("\n".join(lines))
