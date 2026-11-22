"""Port con una regresion: el rango es exclusivo por la derecha.

Este es el fallo tipico de una migracion: en un lenguaje `range(a,b)` excluye
el final, en otro lo incluye. Compila, pasa los tests que nadie escribio, y
cambia el resultado en silencio.
"""

import sys


def parse(expr: str) -> list[int]:
    expr = expr.strip()
    if not expr:
        raise ValueError("expresion vacia")
    if expr.startswith("*/"):
        step = int(expr[2:])
        if step <= 0:
            raise ValueError("el paso debe ser positivo")
        return list(range(0, 60, step))
    if "-" in expr:
        left, right = expr.split("-", 1)
        start, end = int(left), int(right)
        if start > end:
            raise ValueError("rango invertido")
        return list(range(start, end))  # <-- se come el ultimo valor
    return [int(expr)]


def main() -> int:
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    try:
        values = parse(raw)
    except (ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(",".join(str(v) for v in values))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
