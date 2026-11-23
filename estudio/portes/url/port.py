import sys
raw = sys.stdin.buffer.read().decode("utf-8", "replace")
line = raw.split("\n")[0].strip()
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

scheme, sep, rest = line.partition("://")
if not sep:
    scheme, rest = "", line
netloc, _, path = rest.partition("/")
path = "/" + path if path else "/"
query = ""
if "?" in path:
    path, _, query = path.partition("?")
print("|".join([scheme, netloc, path, query, ""]))
