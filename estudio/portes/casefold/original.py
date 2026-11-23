import sys
raw = sys.stdin.buffer.read().decode("utf-8", "replace")
line = raw.split("\n")[0].strip()

import unicodedata
print(unicodedata.normalize("NFC", line.casefold()))
