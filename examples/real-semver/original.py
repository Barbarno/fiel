"""Original del ejemplo real: `semver` de Python contra `semver` de Rust.

No es una funcion escrita para este proyecto. Son dos bibliotecas reales,
mantenidas por otras personas, que implementan el mismo estandar
(https://semver.org) en dos lenguajes distintos.

Ese es el caso que fiel existe para medir: dos implementaciones que dicen lo
mismo en la documentacion y no siempre hacen lo mismo en los bordes.

Entrada (stdin):
  - una version:            `1.2.3-alpha.1+build.5`
  - dos versiones separadas por un espacio: `1.0.0-alpha 1.0.0-beta`

Salida:
  - una version:  `mayor|menor|parche|pre|build|canonica`, con `-` en los vacios
  - dos versiones: `-1`, `0` o `1` segun el orden que define el estandar

Requiere:  pip install semver
"""

from __future__ import annotations

import sys

import semver


def parse(text: str) -> str:
    version = semver.Version.parse(text)
    pre = version.prerelease if version.prerelease else "-"
    build = version.build if version.build else "-"
    return f"{version.major}|{version.minor}|{version.patch}|{pre}|{build}|{version}"


def render(raw: str) -> str:
    parts = raw.split()
    if len(parts) == 1:
        return parse(parts[0])
    if len(parts) == 2:
        return str(semver.compare(parts[0], parts[1]))
    raise ValueError("entrada invalida")


def main() -> int:
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    try:
        print(render(raw.strip()))
    except (ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
