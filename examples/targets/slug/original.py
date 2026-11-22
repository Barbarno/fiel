"""Original del target 'slug': convierte un titulo en una URL limpia.

Ejemplo:  "Café con Leche -- 2ª parte"  ->  "cafe-con-leche-2a-parte"

Reglas:
  - minusculas
  - se quitan los acentos (normalizacion NFD + quitar marcas)
  - todo lo que no sea letra o numero se convierte en un guion
  - los guiones repetidos se colapsan y se recortan de los extremos

Es una funcion de una linea en apariencia y el sitio exacto donde una
reescritura se rompe: Rust no trae plegado de acentos en la biblioteca
estandar, y Python si (unicodedata).
"""

from __future__ import annotations

import sys
import unicodedata


def slug(text: str) -> str:
    text = text.strip()
    if not text:
        raise ValueError("texto vacio")
    decomposed = unicodedata.normalize("NFD", text)
    plain = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    lowered = plain.lower()
    out: list[str] = []
    for ch in lowered:
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    result = "".join(out).strip("-")
    if not result:
        raise ValueError("sin caracteres utilizables")
    return result


def main() -> int:
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    try:
        print(slug(raw))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
