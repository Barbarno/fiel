"""Original del target 'toml': parser de una linea `clave = valor`.

Soporta lo que aparece en un fichero de configuracion normal:

    puerto = 8080
    nombre = "servidor"
    activo = true
    etiquetas = [1, 2, 3]

Salida: `clave|tipo|valor` con el entero ya normalizado (`+5` -> `5`) y las
cadenas con sus escapes visibles (`\\n`, `\\t`) para que quepan en una linea.

El TOML de verdad es mas grande. Esto es el subconjunto que usan los ficheros
de configuracion de un proyecto, y es justo donde una reescritura se rompe:
enteros grandes, guiones bajos, escapes unicode, arrays de cadenas.
"""

from __future__ import annotations

import re
import sys

INT_RE = re.compile(r"^[+-]?(?:0|[1-9](?:_?[0-9])*)$")
KEY_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
HEX = set("0123456789abcdefABCDEF")


def strip_comment(line: str) -> str:
    out: list[str] = []
    inside = False
    escaped = False
    for ch in line:
        if inside:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                inside = False
        elif ch == '"':
            inside = True
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out)


def parse_string(text: str, start: int) -> tuple[str, int]:
    out: list[str] = []
    i = start + 1
    while i < len(text):
        ch = text[i]
        if ch == '"':
            return "".join(out), i + 1
        if ch == "\\":
            i += 1
            if i >= len(text):
                raise ValueError("escape incompleto")
            code = text[i]
            if code == "n":
                out.append("\n")
            elif code == "t":
                out.append("\t")
            elif code == '"':
                out.append('"')
            elif code == "\\":
                out.append("\\")
            elif code == "u":
                digits = text[i + 1 : i + 5]
                if len(digits) != 4 or any(d not in HEX for d in digits):
                    raise ValueError("escape unicode invalido")
                out.append(chr(int(digits, 16)))
                i += 4
            else:
                raise ValueError("escape desconocido")
            i += 1
            continue
        out.append(ch)
        i += 1
    raise ValueError("cadena sin cerrar")


def display(text: str) -> str:
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t")


def parse_array(text: str, start: int) -> tuple[list[tuple[str, str]], int]:
    items: list[tuple[str, str]] = []
    i = start + 1
    while True:
        while i < len(text) and text[i] in " \t":
            i += 1
        if i >= len(text):
            raise ValueError("array sin cerrar")
        if text[i] == "]":
            return items, i + 1
        if text[i] == '"':
            value, i = parse_string(text, i)
            items.append(("str", display(value)))
        else:
            j = i
            while j < len(text) and text[j] not in ",]":
                j += 1
            token = text[i:j].strip()
            if not INT_RE.match(token):
                raise ValueError("elemento de array invalido")
            items.append(("int", str(int(token.replace("_", "")))))
            i = j
        while i < len(text) and text[i] in " \t":
            i += 1
        if i >= len(text):
            raise ValueError("array sin cerrar")
        if text[i] == ",":
            i += 1
            continue
        if text[i] == "]":
            return items, i + 1
        raise ValueError("separador invalido")


def parse(line: str) -> str:
    clean = strip_comment(line).strip()
    if not clean:
        raise ValueError("linea vacia")
    if "=" not in clean:
        raise ValueError("falta el signo igual")
    key, value = clean.split("=", 1)
    key = key.strip()
    if not KEY_RE.match(key):
        raise ValueError("clave invalida")
    value = value.strip()
    if not value:
        raise ValueError("valor vacio")

    if value.startswith('"'):
        text, end = parse_string(value, 0)
        if value[end:].strip():
            raise ValueError("texto de sobra")
        return f"{key}|string|{display(text)}"

    if value in {"true", "false"}:
        return f"{key}|bool|{value}"

    if value.startswith("["):
        items, end = parse_array(value, 0)
        if value[end:].strip():
            raise ValueError("texto de sobra")
        if not items:
            return f"{key}|array|"
        kinds = {kind for kind, _ in items}
        if len(kinds) != 1:
            raise ValueError("array mixto")
        return f"{key}|array|{','.join(item for _, item in items)}"

    if INT_RE.match(value):
        return f"{key}|int|{int(value.replace('_', ''))}"

    raise ValueError("valor no soportado")


def main() -> int:
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    try:
        print(parse(raw))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
