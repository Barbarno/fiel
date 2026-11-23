"""Estudio: mide ports generados por modelos contra el corpus de cada target.

Dos subcomandos:

    python estudio/estudio.py medir
        Mide los ports que ya existen (los de Rust escritos para los ejemplos y
        los que haya en estudio/salidas/<modelo>/<target>.py) y escribe
        estudio/resultados.md y estudio/resultados.csv.

    python estudio/estudio.py generar --modelo groq
        Pide a un modelo (API compatible con OpenAI) que escriba el port de
        cada target y lo guarda en estudio/salidas/<modelo>/<target>.py.
        Necesita la variable de entorno con la clave. Despues se ejecuta
        'medir' y la fila aparece sola en la tabla.

Solo biblioteca estandar. Ninguna clave se guarda en el repositorio: se lee
del entorno y no se escribe en ningun sitio.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fiel import check as check_mod
from fiel import corpus as corpus_mod
from fiel.spec import Endpoint, Pair, Project

ESTUDIO = ROOT / "estudio"
TARGETS = ("url", "toml", "slug")

# Ports escritos a mano para los ejemplos del repositorio. Se miden con el
# mismo instrumento que los generados: no hay varilla distinta para los mios.
MANUALES = {
    "url": ["examples/targets/url/rust-port/target/x86_64-pc-windows-gnu/release/url-rs.exe"],
    "toml": ["examples/targets/toml/rust-port/target/x86_64-pc-windows-gnu/release/toml-rs.exe"],
    "slug": ["examples/targets/slug/rust-port/target/x86_64-pc-windows-gnu/release/slug-rs.exe"],
}


def _original(target: str) -> Endpoint:
    return Endpoint(command=("python", f"examples/targets/{target}/original.py"))


def _pair(target: str, suffix: str, port: Endpoint) -> Pair:
    return Pair(
        id=f"{target}{suffix}",
        original=_original(target),
        port=port,
        corpus=f"examples/targets/{target}/corpus/{'traps' if suffix else target}.jsonl",
        normalize="text",
        errors="ignore",
        timeout_ms=10000,
    )


def fila(nombre: str, port_command: list[str]) -> dict[str, object]:
    data: dict[str, tuple[int, int, int, int]] = {}
    port = Endpoint(command=tuple(port_command))
    for target in TARGETS:
        normal = check_mod.check(Project(root=ROOT, pairs=(_pair(target, "", port),)), jobs=4)
        traps = check_mod.check(Project(root=ROOT, pairs=(_pair(target, "-trampas", port),)), jobs=4)
        data[target] = (normal.total, normal.total - normal.failed, traps.total, traps.failed)
    return _resumen(nombre, data)


def _generados() -> list[tuple[str, list[str]]]:
    rows: list[tuple[str, list[str]]] = []
    base = ESTUDIO / "salidas"
    if not base.is_dir():
        return rows
    for model_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        ports = [model_dir / f"{t}.py" for t in TARGETS]
        if not all(p.is_file() for p in ports):
            continue
        rows.append((model_dir.name, ["python", str(ports[0])]))
    return rows


def _measure_generated(model_dir: Path) -> dict[str, object] | None:
    data: dict[str, tuple[int, int, int, int]] = {}
    for target in TARGETS:
        port = Endpoint(command=("python", str(model_dir / f"{target}.py")))
        normal = check_mod.check(Project(root=ROOT, pairs=(_pair(target, "", port),)), jobs=4)
        traps = check_mod.check(
            Project(root=ROOT, pairs=(_pair(target, "-trampas", port),)), jobs=4
        )
        data[target] = (normal.total, normal.total - normal.failed, traps.total, traps.failed)
    casos = sum(v[0] for v in data.values())
    fieles = sum(v[1] for v in data.values())
    trampas = sum(v[2] for v in data.values())
    fallos = sum(v[3] for v in data.values())
    if casos == 0:
        return None
    return {
        "modelo": model_dir.name,
        "casos": casos,
        "fieles": fieles,
        "trampas": trampas,
        "divergencias": fallos,
        "porcentaje": round(100.0 * (fieles + (trampas - fallos)) / (casos + trampas), 1),
        "detalle": data,
    }


def _fila_real() -> dict[str, object] | None:
    """Dos bibliotecas reales del mismo estandar, medidas con el mismo motor."""
    semver_rs = (
        ROOT
        / "examples"
        / "real-semver"
        / "rust-port"
        / "target"
        / "x86_64-pc-windows-gnu"
        / "release"
        / "semver-rs.exe"
    )
    if not semver_rs.is_file():
        return None
    original = Endpoint(command=("python", "examples/real-semver/original.py"))
    port = Endpoint(command=(str(semver_rs),))
    normal = check_mod.check(
        Project(
            root=ROOT,
            pairs=(
                Pair(
                    id="semver-real",
                    original=original,
                    port=port,
                    corpus="examples/real-semver/corpus/semver.jsonl",
                    normalize="text",
                    errors="ignore",
                    timeout_ms=10000,
                ),
            ),
        ),
        jobs=4,
    )
    traps = check_mod.check(
        Project(
            root=ROOT,
            pairs=(
                Pair(
                    id="semver-real-trampas",
                    original=original,
                    port=port,
                    corpus="examples/real-semver/corpus/traps.jsonl",
                    normalize="text",
                    errors="ignore",
                    timeout_ms=10000,
                ),
            ),
        ),
        jobs=4,
    )
    return {
        "modelo": "bibliotecas reales (python-semver vs semver-rs)",
        "casos": normal.total,
        "fieles": normal.total - normal.failed,
        "trampas": traps.total,
        "divergencias": traps.failed,
        "porcentaje": round(
            100.0
            * ((normal.total - normal.failed) + (traps.total - traps.failed))
            / (normal.total + traps.total),
            1,
        ),
        "detalle": {"semver": (normal.total, normal.total - normal.failed, traps.total, traps.failed)},
    }


def _fila_portes() -> dict[str, object] | None:
    """Seis funciones de la biblioteca estandar reescritas a mano.

    No son ports de un modelo ni de Rust: son el caso mas comun de todos, el
    de alguien que reescribe `csv`, `shlex` o `ipaddress` "a mano" porque le
    parece sencillo. Cada una pasa su corpus normal y falla en las trampas.
    """
    base = ROOT / "estudio" / "portes"
    parejas = ("csv", "shlex", "url", "wrap", "ip", "casefold")
    if not all((base / p / "corpus" / f"{p}.jsonl").is_file() for p in parejas):
        return None
    detalle: dict[str, tuple[int, int, int, int]] = {}
    for nombre in parejas:
        original = Endpoint(command=("python", "original.py"), cwd=str(base / nombre))
        port = Endpoint(command=("python", "port.py"), cwd=str(base / nombre))
        normal = check_mod.check(
            Project(
                root=ROOT,
                pairs=(
                    Pair(
                        id=nombre,
                        original=original,
                        port=port,
                        corpus=f"estudio/portes/{nombre}/corpus/{nombre}.jsonl",
                        normalize="text",
                        errors="ignore",
                        timeout_ms=10000,
                    ),
                ),
            ),
            jobs=4,
        )
        trampas = check_mod.check(
            Project(
                root=ROOT,
                pairs=(
                    Pair(
                        id=f"{nombre}-trampas",
                        original=original,
                        port=port,
                        corpus=f"estudio/portes/{nombre}/corpus/{nombre}-trampas.jsonl",
                        normalize="text",
                        errors="ignore",
                        timeout_ms=10000,
                    ),
                ),
            ),
            jobs=4,
        )
        detalle[nombre] = (
            normal.total,
            normal.total - normal.failed,
            trampas.total,
            trampas.failed,
        )
    return _resumen("reescritura a mano (stdlib, sin dependencias)", detalle)


def cmd_medir(args: argparse.Namespace) -> int:
    filas: list[dict[str, object]] = []

    # Fila manual: tres binarios distintos, una medicion por target.
    inicio = time.perf_counter()
    detalle: dict[str, tuple[int, int, int, int]] = {}
    for target, command in MANUALES.items():
        port = Endpoint(command=tuple(command))
        normal = check_mod.check(Project(root=ROOT, pairs=(_pair(target, "", port),)), jobs=4)
        traps = check_mod.check(Project(root=ROOT, pairs=(_pair(target, "-trampas", port),)), jobs=4)
        detalle[target] = (normal.total, normal.total - normal.failed, traps.total, traps.failed)
    fila = _resumen("port de IA (Rust, una pasada)", detalle)
    fila["segundos"] = round(time.perf_counter() - inicio, 2)
    filas.append(fila)

    inicio = time.perf_counter()
    real = _fila_real()
    if real:
        real["segundos"] = round(time.perf_counter() - inicio, 2)
        filas.append(real)

    inicio = time.perf_counter()
    portes = _fila_portes()
    if portes:
        portes["segundos"] = round(time.perf_counter() - inicio, 2)
        filas.append(portes)

    base = ESTUDIO / "salidas"
    if base.is_dir():
        for model_dir in sorted(p for p in base.iterdir() if p.is_dir()):
            if model_dir.name.startswith("_"):
                continue
            row = _measure_generated(model_dir)
            if row:
                filas.append(row)

    if not args.quiet:
        print(_markdown(filas))
    _write(filas, args)
    return 0


def _resumen(nombre: str, detalle: dict[str, tuple[int, int, int, int]]) -> dict[str, object]:
    casos = sum(v[0] for v in detalle.values())
    fieles = sum(v[1] for v in detalle.values())
    trampas = sum(v[2] for v in detalle.values())
    fallos = sum(v[3] for v in detalle.values())
    return {
        "modelo": nombre,
        "casos": casos,
        "fieles": fieles,
        "trampas": trampas,
        "divergencias": fallos,
        "porcentaje": round(100.0 * (fieles + (trampas - fallos)) / (casos + trampas), 1),
        "detalle": detalle,
    }


def _markdown(filas: list[dict[str, object]]) -> str:
    lines = [
        "| modelo | casos normales | fieles | trampas | divergencias en trampas | % fiel | tiempo |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in filas:
        segundos = row.get("segundos")
        tiempo = f"{segundos} s" if segundos is not None else "-"
        lines.append(
            f"| {row['modelo']} | {row['casos']} | {row['fieles']} | {row['trampas']} | "
            f"{row['divergencias']} | {row['porcentaje']}% | {tiempo} |"
        )
    lines.append("")
    lines.append("Detalle por target:")
    lines.append("")
    lines.append("| modelo | target | casos | fieles | trampas | divergencias |")
    lines.append("|---|---|---|---|---|---|")
    for row in filas:
        for target, (casos, fieles, trampas, fallos) in row["detalle"].items():
            lines.append(
                f"| {row['modelo']} | {target} | {casos} | {fieles} | {trampas} | {fallos} |"
            )
    return "\n".join(lines)


def _write(filas: list[dict[str, object]], args: argparse.Namespace) -> None:
    md = ESTUDIO / "resultados.md"
    header = (
        "# Resultados\n\n"
        "Generado por `python estudio/estudio.py medir`. No se edita a mano.\n\n"
        "La primera fila son los ports de Rust del repositorio: los escribió un\n"
        "asistente de IA en una pasada, a partir de la especificación de cada\n"
        "función. La segunda compara dos bibliotecas reales del mismo estándar. La\n"
        "tercera son seis funciones de la biblioteca estándar reescritas a mano.\n"
        "Las filas de modelos aparecen al ejecutar `generar` con una clave.\n\n"
    )
    md.write_text(header + _markdown(filas) + "\n", encoding="utf-8")

    csv_path = ESTUDIO / "resultados.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["modelo", "target", "casos", "fieles", "trampas", "divergencias", "segundos"])
        for row in filas:
            for target, (casos, fieles, trampas, fallos) in row["detalle"].items():
                writer.writerow(
                    [row["modelo"], target, casos, fieles, trampas, fallos, row.get("segundos", "")]
                )
    if not args.quiet:
        print(f"\nEscrito {md.relative_to(ROOT)} y {csv_path.relative_to(ROOT)}")


def _prompt(target: str) -> str:
    spec = (ESTUDIO / "prompts" / f"{target}.md").read_text(encoding="utf-8")
    return (
        "Escribe un programa en Python 3.11, solo biblioteca estandar, que "
        "lea la entrada por stdin y escriba la salida por stdout.\n"
        "Responde unicamente con el codigo, en un bloque ```python.\n\n"
        + spec
    )


def _extract_code(text: str) -> str | None:
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    if match:
        return match.group(1).strip() + "\n"
    if text.strip().startswith(("import ", "from ", "def ", '"""')):
        return text.strip() + "\n"
    return None


def cmd_generar(args: argparse.Namespace) -> int:
    config = tomllib.loads((ESTUDIO / "modelos.toml").read_text(encoding="utf-8"))
    models = {m["id"]: m for m in config.get("modelo", [])}
    if args.modelo not in models:
        print(f"modelo desconocido: {args.modelo} (hay: {', '.join(models)})", file=sys.stderr)
        return 2
    model = models[args.modelo]
    key = os.environ.get(model["api_key_env"], "")
    if not key:
        print(
            f"falta la variable {model['api_key_env']}. "
            "Consigue una clave gratuita y exportala; no se guarda en el repo.",
            file=sys.stderr,
        )
        return 2

    target_dir = ESTUDIO / "salidas" / args.modelo
    target_dir.mkdir(parents=True, exist_ok=True)
    for target in TARGETS:
        if (target_dir / f"{target}.py").is_file() and not args.force:
            print(f"{target}: ya existe, se conserva (usa --force para repetir)")
            continue
        code = _call(model, key, _prompt(target))
        if code is None:
            print(f"{target}: el modelo no devolvio codigo utilizable", file=sys.stderr)
            continue
        (target_dir / f"{target}.py").write_text(code, encoding="utf-8")
        print(f"{target}: guardado en {target_dir / (target + '.py')}")
    return 0


def _call(model: dict, key: str, prompt: str) -> str | None:
    body = json.dumps(
        {
            "model": model["nombre"],
            "temperature": model.get("temperatura", 0.2),
            "messages": [
                {"role": "system", "content": "Eres un programador. Respondes solo con codigo."},
                {"role": "user", "content": prompt},
            ],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        model["base_url"].rstrip("/") + "/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read()[:200].decode('utf-8', 'replace')}", file=sys.stderr)
        return None
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"sin conexion con el modelo: {exc}", file=sys.stderr)
        return None
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        print(f"respuesta inesperada: {str(payload)[:200]}", file=sys.stderr)
        return None
    return _extract_code(content)


def cmd_estado(args: argparse.Namespace) -> int:
    del args
    config = tomllib.loads((ESTUDIO / "modelos.toml").read_text(encoding="utf-8"))
    print("Modelos configurados:")
    for model in config.get("modelo", []):
        key = os.environ.get(model["api_key_env"], "")
        mark = "clave lista" if key else f"falta {model['api_key_env']}"
        ports = ESTUDIO / "salidas" / model["id"]
        hecho = ports.is_dir() and all((ports / f"{t}.py").is_file() for t in TARGETS)
        print(f"  {model['id']:<12} {model['nombre']:<40} {mark:<28} ports: {'si' if hecho else 'no'}")
    print("")
    if (ESTUDIO / "resultados.md").is_file():
        print("Tabla actual: estudio/resultados.md")
    else:
        print("Tabla: todavia no hay. Ejecuta 'medir'.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="estudio")
    sub = parser.add_subparsers(dest="command", required=True)

    p_estado = sub.add_parser("estado", help="que modelos hay listos y que falta")
    p_estado.set_defaults(func=cmd_estado)

    p_medir = sub.add_parser("medir", help="mide los ports y escribe la tabla")
    p_medir.add_argument("--quiet", action="store_true")
    p_medir.set_defaults(func=cmd_medir)

    p_gen = sub.add_parser("generar", help="pide un port a un modelo")
    p_gen.add_argument("--modelo", required=True)
    p_gen.add_argument("--force", action="store_true")
    p_gen.set_defaults(func=cmd_generar)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
