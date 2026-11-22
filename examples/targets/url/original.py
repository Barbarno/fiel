"""Original del target 'url': parser de URLs sin dependencias.

Lee una URL por stdin y escribe sus componentes separados por '|':

    esquema|usuario|host|puerto|ruta|query|fragmento

Los campos que no existen se escriben '-'. El puerto por defecto del esquema
(80 en http, 443 en https) se normaliza a '-', igual que hace un navegador.

Es el tipo de funcion que se reescribe en otro lenguaje sin pensar: parece
trivial hasta que aparece un IPv6, un puerto vacio o un esquema en mayusculas.
"""

from __future__ import annotations

import sys

SCHEME_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789+.-")


def parse(url: str) -> str:
    if "://" not in url:
        raise ValueError("sin esquema")
    scheme, rest = url.split("://", 1)
    if not scheme:
        raise ValueError("esquema vacio")
    low = scheme.lower()
    if not low[0].isalpha() or any(ch not in SCHEME_CHARS for ch in low):
        raise ValueError("esquema invalido")

    fragment = None
    if "#" in rest:
        rest, fragment = rest.split("#", 1)
    query = None
    if "?" in rest:
        rest, query = rest.split("?", 1)

    if "/" in rest:
        authority, tail = rest.split("/", 1)
        path = "/" + tail
    else:
        authority, path = rest, "/"

    userinfo = None
    if "@" in authority:
        userinfo, authority = authority.rsplit("@", 1)

    if authority.startswith("["):
        end = authority.find("]")
        if end < 0:
            raise ValueError("ipv6 sin cerrar")
        host = authority[: end + 1]
        after = authority[end + 1 :]
        if after.startswith(":"):
            port = after[1:]
        elif after:
            raise ValueError("host invalido")
        else:
            port = ""
    elif ":" in authority:
        host, port = authority.rsplit(":", 1)
    else:
        host, port = authority, ""

    if not host:
        raise ValueError("host vacio")

    if port == "":
        rendered_port = "-"
    else:
        if not port.isdigit():
            raise ValueError("puerto invalido")
        number = int(port)
        if number > 65535:
            raise ValueError("puerto fuera de rango")
        default = (low == "http" and number == 80) or (low == "https" and number == 443)
        rendered_port = "-" if default else str(number)

    return "|".join(
        [
            low,
            userinfo if userinfo is not None else "-",
            host,
            rendered_port,
            path,
            query if query is not None else "-",
            fragment if fragment is not None else "-",
        ]
    )


def main() -> int:
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    try:
        print(parse(raw.strip()))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
