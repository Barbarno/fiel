import sys
raw = sys.stdin.buffer.read().decode("utf-8", "replace")
line = raw.split("\n")[0].strip()
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

parts = line.split(".")
if len(parts) != 4:
    print("error")
else:
    ok = all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
    print(".".join(str(int(p)) for p in parts) if ok else "error")
