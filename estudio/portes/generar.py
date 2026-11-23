"""Genera el banco de portes: seis reimplementaciones ingenuas de funciones reales.

Cada pareja es un caso que se da en la vida real: alguien reescribe una funcion de
la biblioteca estandar "a mano" porque no quiere depender de ella. El corpus se
graba con entradas normales, como haria cualquiera. La pregunta es si ese corpus
demuestra algo.

    python estudio/portes/generar.py
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Las entradas llegan por bytes: se decodifica tolerando basura, como haria un
# programa de verdad. Si no, cualquier sonda no-UTF8 tumba el proceso y todas las
# formas de comportamiento colapsan en "crash".
READ = 'raw = sys.stdin.buffer.read().decode("utf-8", "replace")\nline = raw.split("\\n")[0].strip()\n'

PAIRS = {
    "csv": {
        "original": READ + """
import csv, io
row = next(csv.reader(io.StringIO(line)))
print("|".join(row))
""",
        "port": READ + """
print("|".join(line.split(",")))
""",
        "seeds": ["a,b,c", "1,2,3", "name,age,city", "x,y", "foo,bar,baz", "a,b,c,d"],
    },
    "shlex": {
        "original": READ + """
import shlex
print("|".join(shlex.split(line)))
""",
        "port": READ + """
print("|".join(line.split()))
""",
        "seeds": ["ls -la", "git commit -m x", "echo hola", "python script.py --v", "cd /tmp", "cat f.txt"],
    },
    "url": {
        "original": READ + """
from urllib.parse import urlsplit
u = urlsplit(line)
print("|".join([u.scheme, u.netloc, u.path, u.query, u.fragment]))
""",
        "port": READ + """
scheme, sep, rest = line.partition("://")
if not sep:
    scheme, rest = "", line
netloc, _, path = rest.partition("/")
path = "/" + path if path else "/"
query = ""
if "?" in path:
    path, _, query = path.partition("?")
print("|".join([scheme, netloc, path, query, ""]))
""",
        "seeds": [
            "http://example.com/a",
            "https://x.org:8080/p?q=1",
            "ftp://h/f",
            "http://a/b/c",
            "https://d.e/",
            "http://f.g/h?i=j",
        ],
    },
    "wrap": {
        "original": READ + """
import textwrap
print("\\n".join(textwrap.wrap(line, 10)))
""",
        "port": READ + """
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
print("\\n".join(lines))
""",
        "seeds": [
            "hola mundo",
            "esto es una prueba",
            "linea corta",
            "uno dos tres cuatro",
            "abc def ghi",
            "palabra palabra",
        ],
    },
    "ip": {
        "original": READ + """
import ipaddress
try:
    print(str(ipaddress.ip_address(line)))
except ValueError:
    print("error")
""",
        "port": READ + """
parts = line.split(".")
if len(parts) != 4:
    print("error")
else:
    ok = all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
    print(".".join(str(int(p)) for p in parts) if ok else "error")
""",
        "seeds": ["192.168.1.1", "10.0.0.1", "8.8.8.8", "172.16.0.1", "1.1.1.1", "192.0.2.1"],
    },
    "casefold": {
        "original": READ + """
import unicodedata
print(unicodedata.normalize("NFC", line.casefold()))
""",
        "port": READ + """
print(line.lower())
""",
        "seeds": ["HOLA", "Mundo", "abc", "Test", "ARBOL", "casa"],
    },
}


def corpus_line(cid: str, payload: bytes) -> str:
    return json.dumps(
        {"id": cid, "input_b64": base64.b64encode(payload).decode()},
        ensure_ascii=False,
    )


def main() -> int:
    spec = ['[project]', 'baseline = "fiel.baseline.json"', ""]
    for name, data in PAIRS.items():
        target = ROOT / name
        target.mkdir(parents=True, exist_ok=True)
        (target / "original.py").write_text("import sys\n" + data["original"].lstrip(), encoding="utf-8")
        (target / "port.py").write_text("import sys\n" + data["port"].lstrip(), encoding="utf-8")
        (target / "corpus").mkdir(exist_ok=True)
        lines = [corpus_line(f"{name}{i:03d}", seed.encode()) for i, seed in enumerate(data["seeds"], 1)]
        (target / "corpus" / f"{name}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

        spec.extend(
            [
                "[[pair]]",
                f'id = "{name}"',
                'original = { command = ["python", "original.py"], cwd = "' + name + '" }',
                'port = { command = ["python", "port.py"], cwd = "' + name + '" }',
                f'corpus = "{name}/corpus/{name}.jsonl"',
                "timeout_ms = 5000",
                'normalize = "text"',
                "",
            ]
        )

    (ROOT / "fiel.toml").write_text("\n".join(spec), encoding="utf-8")
    print(f"{len(PAIRS)} parejas escritas en {ROOT}")
    print("siguiente: python -m fiel --root estudio/portes record")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
