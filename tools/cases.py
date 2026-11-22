"""Genera los ficheros de casos de los tres targets nuevos.

Un caso por linea. `fiel add --file` los convierte en corpus y graba la salida
del original. Se guarda el generador y no solo el .txt para que el corpus sea
reproducible y revisable.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "examples" / "targets"

URL_NORMAL = [
    "https://example.com:8443/a/b",
    "http://example.com:8080/users/42?tab=posts",
    "https://api.example.org/v1/items?limit=10&page=2",
    "ftp://files.example.net:2121/pub/readme.txt",
    "https://user@example.com:9000/panel",
    "https://user:secret@example.com:9443/login?next=%2Fhome",
    "http://localhost:3000/",
    "http://127.0.0.1:8000/health",
    "https://sub.domain.example.co.uk:8443/path/with/dashes",
    "https://example.com:8443/a?q=1#top",
    "https://example.com:8443/#frag",
    "http://example.com:8081/",
    "https://example.com:8444/?x=1",
    "https://example.com:8445/?x=1#y",
    "ftp://mirror.example.com:2121/dir/",
    "https://cdn.example.com:9443/img/logo.png",
    "http://example.com:8000/a/b/c/d/e",
    "https://example.com:8443/search?q=rust+lang",
    "https://example.com:8443/a//b",
    "https://example.com:8443/a/./b/../c",
    "https://user.name@example.com:8443/x",
    "https://user:pa%40ss@example.com:8443/x",
    "http://example.com:8082/a?x=#y",
    "https://example.com:8443/a?#f",
    "https://example.com:8443/a?",
    "https://example.com:8443/a#",
    "https://a.b.c.d:8443/x",
    "https://example.com:65535/x",
    "http://example.com:1/x",
    "https://example.com:8443/%7Euser/file",
    "https://example.com:8443/a?b=c=d",
    "https://example.com:8443/a#b#c",
    "https://example.com:8443/a?b?c",
    "http://example.com:8080/",
    "https://example.com:8443/x?utm_source=a&utm_medium=b",
    "https://example.com:8443/espacio%20con%20porcentaje",
    "ftp://user@host.example:21/file",
    "https://example.com:4430/x",
    "http://example.com:8000/x#a?b",
    "https://example.com:8443/a/b?x=1#f/g",
]

URL_TRAPS = [
    "http://example.com:80/a",
    "HTTP://example.com/x",
    "http://example.com",
    "http://[::1]:8080/x",
    "http://example.com:/x",
    "https://example.com:443/x",
    "http://example.com:65536/x",
    "http://example.com/ok",
    "http://[::1]/x",
]

TOML_NORMAL = [
    "puerto = 8080",
    'nombre = "servidor"',
    "activo = true",
    "debug = false",
    "ids = [1, 2, 3]",
    "vacio = []",
    "max = 100",
    "min = -20",
    "plus = +5",
    "grande = 1_000_000",
    'ruta = "/var/log/app.log"',
    'titulo = "hola mundo"',
    'comentario = "a # b"   # esto no es comentario',
    r'linea = "a\nb"',
    r'tab = "a\tb"',
    r'comillas = "dice \"hola\""',
    r'barra = "c:\\tmp"',
    "version = 1",
    "negativo = -1",
    "cero = 0",
    "cero_mas = +0",
    'server.host = "localhost"',
    "server.port = 8080",
    "a-b_c.1 = 2",
    'MAYUS = "X"',
    "lista = [10, 20, 30, 40]",
    "unico = [7]",
    "negativos = [-1, -2, -3]",
    "suma = 2_500_000",
    'url = "https://example.com:8443/x"',
    'espacios = "  con espacios  "',
    'igual = "a=b"',
    'dos_puntos = "a:b"',
    'corchete = "[no es array]"',
    'llave = "{}"',
    'hash = "##"',
    'vacia = ""',
    "bool_key = false",
    "mixto_num = [1, -2, +3]",
    "ultimo = 999",
]

TOML_TRAPS = [
    "big = 99999999999999999999",
    "roto = 1__0",
    r'unicode = "\u00e9"',
    'lista = ["a", "b"]',
    "siete = 007",
    "normal = 5",
    "final = 1_",
    "minus = -0",
]

SLUG_NORMAL = [
    "Hola Mundo",
    "Rust: rapido y seguro!",
    "   espacios   alrededor   ",
    "a",
    "A",
    "hola-mundo",
    "hola_mundo",
    "hola.mundo",
    "Hola, mundo... otra vez",
    "123 456",
    "version 2.0",
    "C++ y Rust",
    "50% mas",
    "a/b/c",
    "--hola--",
    "hola!!!mundo",
    "uno    dos     tres",
    "uno-dos-tres",
    "a  b",
    "ejemplo de titulo para blog",
    "como hacer una web en 2026",
    "guia de rust para principiantes",
    "100 trucos de python",
    "hola mundo 2",
    "test",
    "mi primer proyecto",
    "proyecto intermodular daw",
    "fiel mantiene la equivalencia",
    "los 3 cerditos",
    "a1b2c3",
    "x",
    "abc123",
    "con guiones - y espacios",
    "muchos    espacios",
    "fin.",
    ".inicio",
    "medio",
    "a-b-c",
    "2026",
    "zapato azul",
]

SLUG_TRAPS = [
    "Café con Leche",
    "Ñandú",
    "acción",
    "über",
    "año 2026",
    "HOLA",
    "😀 emoji",
    "   ",
]


def write(name: str, normal: list[str], traps: list[str]) -> None:
    folder = ROOT / name / "cases"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "normal.txt").write_text("\n".join(normal) + "\n", encoding="utf-8")
    (folder / "traps.txt").write_text("\n".join(traps) + "\n", encoding="utf-8")
    print(f"{name}: {len(normal)} normales, {len(traps)} trampas")


if __name__ == "__main__":
    write("url", URL_NORMAL, URL_TRAPS)
    write("toml", TOML_NORMAL, TOML_TRAPS)
    write("slug", SLUG_NORMAL, SLUG_TRAPS)
