"""Diagnostico del entorno antes de una demo, un commit o una entrega.

Comprueba lo que suele fallar en la mesa equivocada: que el interprete sea el
adecuado, que la especificacion cargue, que cada corpus exista, que los dos
lados de cada pareja se puedan ejecutar y que la raiz se pueda escribir.

    fiel doctor
    fiel doctor --smoke

`--smoke` ademas ejecuta el primer caso de cada pareja, que es la unica forma
de saber que los comandos arrancan de verdad.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import corpus as corpus_mod
from .spec import Endpoint, Pair, Project, SpecError, load

OK = "ok"
AVISO = "aviso"
FALLO = "fallo"

MARCAS = {OK: "OK  ", AVISO: "!   ", FALLO: "X   "}


@dataclass(frozen=True)
class Hallazgo:
    nivel: str
    titulo: str
    detalle: str = ""


def _ejecutable(cmd: list[str], cwd: Path) -> tuple[bool, str]:
    """Si el primer token del comando se puede lanzar desde ese directorio."""
    if not cmd:
        return False, "comando vacio"
    primero = cmd[0]
    candidato = Path(primero)
    if candidato.is_absolute() or os.sep in primero or (os.altsep and os.altsep in primero):
        ruta = candidato if candidato.is_absolute() else cwd / candidato
        if ruta.is_file():
            return True, str(ruta)
        return False, f"no existe {ruta}"
    encontrado = shutil.which(primero)
    if encontrado:
        return True, encontrado
    return False, f"'{primero}' no esta en el PATH"


def _smoke(pair: Pair, project: Project) -> Hallazgo:
    try:
        casos = corpus_mod.read(project.root / pair.corpus)
    except corpus_mod.CorpusError as exc:
        return Hallazgo(FALLO, f"{pair.id}: corpus ilegible", str(exc))
    if not casos:
        return Hallazgo(AVISO, f"{pair.id}: corpus vacio", "no hay nada que comprobar")
    caso = casos[0]
    for etiqueta, endpoint in (("original", pair.original), ("port", pair.port)):
        proceso = subprocess.run(
            endpoint.resolved(),
            input=caso.input,
            cwd=endpoint.working_dir(project.root),
            capture_output=True,
            timeout=max(pair.timeout_ms / 1000.0, 1.0),
        )
        if proceso.returncode not in (0, 1):
            # 1 es una salida valida: el programa rechazo la entrada.
            return Hallazgo(
                FALLO,
                f"{pair.id}: {etiqueta} no arranca",
                (proceso.stderr or proceso.stdout).decode("utf-8", "replace").strip()[:120],
            )
    return Hallazgo(OK, f"{pair.id}: los dos lados arrancan", f"caso {caso.id}")


def diagnosticar(project: Project, smoke: bool = False) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []

    if sys.version_info >= (3, 11):
        hallazgos.append(Hallazgo(OK, "interprete", f"Python {sys.version.split()[0]}"))
    else:
        hallazgos.append(
            Hallazgo(FALLO, "interprete", f"Python {sys.version.split()[0]}: hace falta 3.11 o mas")
        )

    if not project.pairs:
        hallazgos.append(Hallazgo(FALLO, "parejas", "la especificacion no define ninguna"))
    else:
        hallazgos.append(Hallazgo(OK, "parejas", f"{len(project.pairs)} definidas"))

    if os.access(project.root, os.W_OK):
        hallazgos.append(Hallazgo(OK, "raiz escribible", str(project.root)))
    else:
        hallazgos.append(Hallazgo(FALLO, "raiz escribible", f"sin permiso en {project.root}"))

    baseline = project.baseline_path()
    if baseline.is_file():
        hallazgos.append(Hallazgo(OK, "baseline", baseline.name))
    else:
        hallazgos.append(Hallazgo(AVISO, "baseline", "no hay: se comprueba todo el corpus"))

    for pair in project.pairs:
        corpus = project.root / pair.corpus
        if corpus.is_file():
            try:
                total = len(corpus_mod.read(corpus))
            except corpus_mod.CorpusError as exc:
                hallazgos.append(Hallazgo(FALLO, f"{pair.id}: corpus roto", str(exc)))
            else:
                hallazgos.append(Hallazgo(OK, f"{pair.id}: corpus", f"{total} casos"))
        else:
            hallazgos.append(Hallazgo(FALLO, f"{pair.id}: corpus", f"no existe {pair.corpus}"))
            continue

        for etiqueta, endpoint in (("original", pair.original), ("port", pair.port)):
            bien, detalle = _ejecutable(endpoint.resolved(), endpoint.working_dir(project.root))
            hallazgos.append(
                Hallazgo(OK if bien else FALLO, f"{pair.id}: comando {etiqueta}", detalle)
            )

        if smoke:
            try:
                hallazgos.append(_smoke(pair, project))
            except subprocess.TimeoutExpired:
                hallazgos.append(Hallazgo(FALLO, f"{pair.id}: tiempo agotado", "el primer caso no termina"))
            except OSError as exc:
                hallazgos.append(Hallazgo(FALLO, f"{pair.id}: no se pudo lanzar", str(exc)))

    return hallazgos


def _filtrar(hallazgos: list[Hallazgo], prefijo: str) -> list[Hallazgo]:
    return [h for h in hallazgos if prefijo in h.titulo or h.titulo.startswith(prefijo)]


def cmd_doctor(args) -> int:
    root = Path(args.root).resolve()
    try:
        project = load(root, Path(args.spec) if args.spec else None)
    except SpecError as exc:
        print(f"fiel doctor: {exc}", file=sys.stderr)
        return 2

    hallazgos = diagnosticar(project, smoke=getattr(args, "smoke", False))
    for pareja in getattr(args, "pair", None) or []:
        hallazgos = [h for h in hallazgos if h.titulo.split(":")[0] in ("interprete", "parejas", "raiz escribible", "baseline") or h.titulo.startswith(f"{pareja}:")]

    for hallazgo in hallazgos:
        marca = MARCAS[hallazgo.nivel]
        linea = f"  {marca} {hallazgo.titulo}"
        if hallazgo.detalle:
            linea += f"  -  {hallazgo.detalle}"
        print(linea)

    fallos = sum(1 for h in hallazgos if h.nivel == FALLO)
    avisos = sum(1 for h in hallazgos if h.nivel == AVISO)
    print("")
    if fallos:
        print(f"{fallos} fallo(s), {avisos} aviso(s). Esto no esta listo.")
        return 1
    if avisos:
        print(f"Todo en orden, con {avisos} aviso(s).")
        return 0
    print("Todo en orden.")
    return 0
