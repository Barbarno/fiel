"""Guardián continuo: reejecuta la comprobacion cuando algo cambia.

`fiel check` se lanza a mano. `fiel watch` se queda mirando los ficheros que
importan (los corpus y los programas de cada pareja) y repite la comprobacion
en cuanto uno cambia de tamano o de fecha. Sin dependencias: un bucle y
`os.stat`.

    fiel watch
    fiel watch --interval 0.5 --pair cron
    fiel watch --path src/parser.py --path tests/
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from . import check as check_mod
from .report import console
from .spec import Project

# Limite de ficheros por directorio vigilado: un `src/` grande no debe convertir
# el bucle en un recorrido de miles de rutas en cada vuelta.
MAX_FICHEROS = 2000


def _firma_de_fichero(path: Path) -> tuple[str, float, int] | None:
    try:
        info = path.stat()
    except OSError:
        return None
    return (str(path), info.st_mtime, info.st_size)


def _ficheros_de(directorio: Path) -> Iterable[Path]:
    contador = 0
    for raiz, carpetas, ficheros in os.walk(directorio):
        carpetas[:] = [c for c in carpetas if c not in {".git", "target", "__pycache__", "node_modules"}]
        for nombre in ficheros:
            contador += 1
            if contador > MAX_FICHEROS:
                return
            yield Path(raiz) / nombre


def rutas_vigiladas(project: Project, extra: Iterable[str] = ()) -> list[Path]:
    """Todo lo que puede cambiar el resultado de una comprobacion."""
    rutas: list[Path] = []
    vistos: set[Path] = set()

    def anadir(candidata: Path) -> None:
        resuelta = candidata.resolve()
        if resuelta not in vistos:
            vistos.add(resuelta)
            rutas.append(resuelta)

    for pair in project.pairs:
        anadir(project.root / pair.corpus)
        for endpoint in (pair.original, pair.port):
            primero = endpoint.command[0] if endpoint.command else ""
            if not primero:
                continue
            candidato = Path(primero)
            if candidato.is_absolute() or os.sep in primero:
                base = endpoint.working_dir(project.root)
                anadir(candidato if candidato.is_absolute() else base / candidato)

    for ruta in extra:
        candidata = (project.root / ruta).resolve()
        if candidata.is_dir():
            for fichero in _ficheros_de(candidata):
                anadir(fichero)
        else:
            anadir(candidata)

    return rutas


def firma(rutas: Iterable[Path]) -> tuple[tuple[str, float, int], ...]:
    """Foto barata del estado de los ficheros vigilados."""
    datos = []
    for ruta in rutas:
        if ruta.is_dir():
            for fichero in _ficheros_de(ruta):
                dato = _firma_de_fichero(fichero)
                if dato:
                    datos.append(dato)
            continue
        dato = _firma_de_fichero(ruta)
        if dato:
            datos.append(dato)
    return tuple(sorted(datos))


@dataclass
class Resultado:
    codigo: int
    total: int
    fallos: int


def una_vuelta(project: Project, pairs: list[str] | None, jobs: int, quiet: bool) -> Resultado:
    seleccion = project.pairs
    if pairs:
        seleccion = tuple(p for p in project.pairs if p.id in set(pairs))
        if not seleccion:
            print(f"fiel watch: ninguna pareja coincide con {sorted(set(pairs))}", file=sys.stderr)
            return Resultado(2, 0, 0)
    resultado = check_mod.check(Project(root=project.root, pairs=seleccion, baseline=project.baseline), jobs=jobs)
    if not quiet:
        baseline = check_mod.load_baseline(project.baseline_path())
        known, fresh = check_mod.split_by_baseline(resultado, baseline)
        print(console(resultado, known, fresh, strict=False))
        sys.stdout.flush()
    total = sum(p.total for p in resultado.pairs)
    fallos = sum(p.failed for p in resultado.pairs)
    return Resultado(1 if fallos else 0, total, fallos)


def run_watch(
    project: Project,
    pairs: list[str] | None = None,
    jobs: int = 4,
    interval: float = 1.0,
    extra: Iterable[str] = (),
    vueltas: int | None = None,
    quiet: bool = False,
    dormir: Callable[[float], None] = time.sleep,
    reloj: Callable[[], float] = time.monotonic,
    salida: Callable[[str], None] = print,
) -> int:
    """Bucle principal. `vueltas` existe para poder probarlo sin esperar."""
    rutas = rutas_vigiladas(project, extra)
    if not rutas:
        salida("fiel watch: no hay nada que vigilar")
        return 2

    salida(f"fiel watch: {len(rutas)} ficheros, cada {interval:g}s. Ctrl+C para salir.")
    anterior = firma(rutas)
    ultimo = una_vuelta(project, pairs, jobs, quiet)
    inicio = reloj()
    contador = 1

    while vueltas is None or contador < vueltas:
        dormir(interval)
        actual = firma(rutas)
        if actual == anterior:
            continue
        anterior = actual
        hace = reloj() - inicio
        salida("")
        salida(f"--- cambio detectado a los {hace:.1f}s ---")
        ultimo = una_vuelta(project, pairs, jobs, quiet)
        contador += 1

    return ultimo.codigo


def cmd_watch(args) -> int:
    from .spec import SpecError, load

    root = Path(args.root).resolve()
    try:
        project = load(root, Path(args.spec) if args.spec else None)
    except SpecError as exc:
        print(f"fiel watch: {exc}", file=sys.stderr)
        return 2
    try:
        return run_watch(
            project,
            pairs=args.pair,
            jobs=args.jobs,
            interval=args.interval,
            extra=args.path or (),
            vueltas=getattr(args, "vueltas", None),
            quiet=getattr(args, "quiet", False),
        )
    except KeyboardInterrupt:
        print("\nfiel watch: parado")
        return 0
