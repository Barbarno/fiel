import sys
raw = sys.stdin.buffer.read().decode("utf-8", "replace")
line = raw.split("\n")[0].strip()
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from urllib.parse import urlsplit
u = urlsplit(line)
print("|".join([u.scheme, u.netloc, u.path, u.query, u.fragment]))
