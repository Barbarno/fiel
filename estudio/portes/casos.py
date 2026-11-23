"""Las entradas del banco de reescrituras a mano, y su reparto en dos corpus.

Cada pareja tiene dos listas:

  - las entradas corrientes, las que cualquiera escribiria en un test;
  - las entradas raras, donde una reescritura rapida deja de coincidir.

El reparto no se hace a mano mirando el resultado: las listas son fijas y el
script `probe.py` solo dice cuales divergen. Asi el corpus de trampas se puede
reconstruir desde cero y el resultado es el mismo.

    python estudio/portes/casos.py     # escribe normal.txt y trampas.txt
    python estudio/portes/probe.py     # dice cuales divergen
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Entradas corrientes: las que aparecen en cualquier manual o test rapido.
NORMAL: dict[str, list[str]] = {
    "csv": ["a,b,c", "1,2,3", "uno,dos,tres", "x,y,z", "a,b,c,d,e", "1,2,3,4"],
    "shlex": ["a b c", "uno dos tres", "ls -la /tmp", "a b c d e", "hola mundo", "x y"],
    "url": [
        "http://example.com/path",
        "https://example.com/a/b",
        "http://host/a",
        "https://host/",
        "http://host/a?b=c",
        "https://host:8443/a",
    ],
    "wrap": [
        "uno dos tres cuatro cinco seis",
        "a b c d e f g h i j",
        "uno dos",
        "palabra palabra palabra",
        "x",
        "uno dos tres",
    ],
    "ip": ["1.2.3.4", "0.0.0.0", "255.255.255.255", "192.168.0.1", "10.0.0.1", "8.8.8.8"],
    "casefold": ["HOLA", "Mundo", "abc", "ÑANDÚ", "Texto Normal", "ÀÉÎÕÜ"],
}

# Entradas raras. No son aleatorias: cada una ataca una decision que la
# reescritura tomo sin darse cuenta (comillas, escapes, esquema, guiones,
# IPv6, mayusculas Unicode).
TRAMPAS: dict[str, list[str]] = {
    "csv": [
        '"a,b",c',
        '"a""b",c',
        '"",x',
        'a,"b,c",d',
        '"unterminated',
        '"x",',
        "a,,c",
        "a,b,",
    ],
    "shlex": [
        '"a b" c',
        "'a b' c",
        "a\\ b c",
        'a "b',
        '"a""b"',
        "'a'\"b\"",
        "a 'b c' d",
        "a#b",
    ],
    "url": [
        "https://example.com:8443/a?b=c#d",
        "http://user:pass@host:8080/p?q#f",
        "http://host",
        "//host/path",
        "?q=1",
        "#frag",
        "HTTP://Host/Path",
        "mailto:a@b.com",
        "http://host/a#b#c",
        "example.com",
        "http://",
    ],
    "wrap": [
        "supercalifragilisticoespialidoso",
        "uno supercalifragilisticoespialidoso dos",
        "a-b-c-d-e-f-g-h-i-j-k-l",
        "uno  dos   tres",
        "palabra-de-diez",
        "uno\tdos",
    ],
    "ip": ["::1", "2001:db8::1", "1.2.3.04", "01.2.3.4", "::ffff:1.2.3.4"],
    "casefold": ["Straße", "İstanbul", "ﬁchero", "ΣΟΦΟΣ", "ẞ", "ﬀ", "ﬃ", "ǅungla"],
}

# Entradas que no caben en un fichero de una linea por caso.
FUERA = {"", '"a\nb",c'}


def escribir() -> None:
    for nombre in NORMAL:
        carpeta = ROOT / nombre
        for etiqueta, listas in (("normal", NORMAL), ("trampas", TRAMPAS)):
            casos = [c for c in listas[nombre] if c not in FUERA]
            destino = carpeta / f"{etiqueta}.txt"
            destino.write_text("\n".join(casos) + "\n", encoding="utf-8")
            print(f"{destino.relative_to(ROOT.parent.parent)}: {len(casos)} casos")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    escribir()
