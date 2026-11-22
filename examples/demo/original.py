"""Original de ejemplo: parser de expresiones minimo.

En un proyecto real este seria el modulo Python (o C, o Go) que alguien esta
migrando a Rust. Aqui es Python para que el demo funcione sin toolchain.

Protocolo (el mismo para los dos lados de la pareja):
  stdin  -> una expresion, texto plano
  stdout -> valores separados por comas
  exit 0 -> ok, exit 1 -> error controlado
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
        return list(range(start, end + 1))
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
