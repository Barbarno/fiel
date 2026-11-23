"""Cuanto del original ejecuta de verdad el corpus.

La tesis del proyecto es que un port solo es tan fiel como el corpus que lo
comprueba. Este comando le pone numero a esa frase: cuenta cuantas lineas con
sentencia del original se ejecutan al menos una vez al pasar el corpus, y dice
cuales no se ejecutan nunca. Lo que el corpus no toca es exactamente el sitio
donde el port puede haberse desviado sin que nadie se entere.

Solo funciona sobre originales en Python: el modulo `trace` de la biblioteca
estandar no puede mirar dentro de un binario de Rust. Para esos se dice claro.

    fiel coverage
    fiel coverage --pair cron-fiel
    fiel coverage --min 80 --format markdown
"""

from __future__ import annotations

import ast
import io
import os
import sys
import trace
from dataclasses import dataclass, field
from pathlib import Path

from . import corpus as corpus_mod
from .spec import Endpoint, Project

PYTHON_NAMES = ("python", "python3", "py")


class CoverageError(Exception):
    pass


@dataclass
class PairCoverage:
    pair_id: str
    script: str = ""
    cases: int = 0
    statements: int = 0
    covered: int = 0
    missing: list[int] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)
    excepciones: list[str] = field(default_factory=list)
    motivo: str = ""          # por que no se pudo medir

    @property
    def medido(self) -> bool:
        return not self.motivo and self.statements > 0

    @property
    def porcentaje(self) -> float:
        if not self.statements:
            return 0.0
        return self.covered * 100.0 / self.statements


@dataclass
class CoverageResult:
    pairs: list[PairCoverage] = field(default_factory=list)

    @property
    def statements(self) -> int:
        return sum(p.statements for p in self.pairs)

    @property
    def covered(self) -> int:
        return sum(p.covered for p in self.pairs)

    @property
    def porcentaje(self) -> float:
        if not self.statements:
            return 0.0
        return self.covered * 100.0 / self.statements

    @property
    def errors(self) -> list[str]:
        return [e for p in self.pairs for e in p.errores]


def script_de(endpoint: Endpoint, project: Project) -> Path | None:
    """Ruta del .py si el lado del original es un script de Python."""
    comando = endpoint.resolved()
    if len(comando) < 2:
        return None
    cabeza = Path(comando[0]).name.lower()
    if not cabeza.startswith(PYTHON_NAMES):
        return None
    candidato = Path(comando[1])
    if not candidato.is_absolute():
        candidato = endpoint.working_dir(project.root) / candidato
    return candidato if candidato.is_file() else None


def sentencias(script: Path) -> set[int]:
    """Lineas con una sentencia real: la unidad que mide `trace`."""
    try:
        arbol = ast.parse(script.read_text(encoding="utf-8-sig"), filename=str(script))
    except (OSError, SyntaxError) as exc:
        raise CoverageError(f"no se puede leer {script}: {exc}") from exc
    lineas: set[int] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.stmt):
            lineas.add(nodo.lineno)
    return lineas


class _Estandar:
    """Conserva y restaura stdin/stdout/stderr alrededor de una ejecucion."""

    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        self.previos = (sys.stdin, sys.stdout, sys.stderr, sys.argv)
        sys.stdin = io.TextIOWrapper(io.BytesIO(self.payload), encoding="utf-8", errors="replace")
        sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", errors="replace")
        return sys.stdin, sys.stdout

    def __exit__(self, *_):
        sys.stdin, sys.stdout, sys.stderr, sys.argv = self.previos
        return False


def medir_par(script: Path, casos: list[bytes], cwd: Path | None = None) -> tuple[set[int], list[str]]:
    """Ejecuta cada caso en este proceso, trazado, y devuelve las lineas vistas.

    `cwd` importa: un script que abre un fichero relativo lo hace contra el
    directorio desde el que se lanza, y el corpus se grabo desde otro.
    """
    totales = sentencias(script)
    vistas: set[int] = set()
    errores: list[str] = []

    trazador = trace.Trace(count=True, trace=False, ignoredirs=[sys.prefix, sys.exec_prefix])
    ruta = str(script.resolve())
    anterior = os.getcwd()
    if cwd is not None:
        os.chdir(cwd)
    try:
        for payload in casos:
            with _Estandar(payload) as (_, salida):
                sys.argv = [ruta]
                try:
                    trazador.runfunc(_ejecutar, ruta)
                except SystemExit:
                    pass
                except BaseException as exc:  # el script puede fallar: eso es un dato, no un fallo
                    if not isinstance(exc, (KeyboardInterrupt,)):
                        errores.append(f"{type(exc).__name__}: {exc}")
                finally:
                    try:
                        salida.flush()
                    except ValueError:
                        pass
    finally:
        os.chdir(anterior)
    for (fichero, linea), _cuenta in trazador.results().counts.items():
        if Path(fichero).resolve() == Path(ruta):
            vistas.add(linea)
    return vistas & totales, errores


def _ejecutar(ruta: str) -> None:
    import runpy

    runpy.run_path(ruta, run_name="__main__")


def medir(project: Project, pairs: list[str] | None = None) -> CoverageResult:
    seleccion = [p for p in project.pairs if not pairs or p.id in set(pairs)]
    if not seleccion:
        raise ValueError(f"ninguna pareja coincide con {pairs}")

    resultado = CoverageResult()
    for pair in seleccion:
        cobertura = PairCoverage(pair_id=pair.id)
        script = script_de(pair.original, project)
        if script is None:
            cobertura.motivo = "el original no es un script de Python"
            resultado.pairs.append(cobertura)
            continue

        try:
            casos = corpus_mod.read(project.root / pair.corpus)
        except corpus_mod.CorpusError as exc:
            cobertura.errores.append(str(exc))
            resultado.pairs.append(cobertura)
            continue

        cobertura.script = str(script.relative_to(project.root)) if script.is_relative_to(project.root) else str(script)
        cobertura.cases = len(casos)
        try:
            vistas, errores = medir_par(
                script,
                [caso.input for caso in casos],
                cwd=pair.original.working_dir(project.root),
            )
        except CoverageError as exc:
            cobertura.errores.append(str(exc))
            resultado.pairs.append(cobertura)
            continue

        totales = sentencias(script)
        cobertura.statements = len(totales)
        cobertura.covered = len(vistas)
        cobertura.missing = sorted(totales - vistas)
        cobertura.excepciones = errores[:3]
        resultado.pairs.append(cobertura)

    return resultado


def _rangos(lineas: list[int], tope: int = 12) -> str:
    """14-16, 23, 41 - compacto, para que quepa en una linea."""
    if not lineas:
        return "ninguna"
    trozos: list[str] = []
    inicio = anterior = lineas[0]
    for linea in lineas[1:]:
        if linea == anterior + 1:
            anterior = linea
            continue
        trozos.append(str(inicio) if inicio == anterior else f"{inicio}-{anterior}")
        inicio = anterior = linea
    trozos.append(str(inicio) if inicio == anterior else f"{inicio}-{anterior}")
    if len(trozos) > tope:
        return ", ".join(trozos[:tope]) + f"... (+{len(trozos) - tope})"
    return ", ".join(trozos)


def console(result: CoverageResult) -> str:
    lineas: list[str] = []
    for par in result.pairs:
        lineas.append(par.pair_id)
        if par.motivo:
            lineas.append(f"  {par.motivo}")
            continue
        if par.errores and not par.statements:
            lineas.append(f"  error  {par.errores[0]}")
            continue
        lineas.append(f"  original    {par.script}")
        lineas.append(f"  casos       {par.cases}")
        lineas.append(f"  sentencias  {par.statements}")
        lineas.append(f"  cubiertas   {par.covered}  ({par.porcentaje:.1f}%)")
        lineas.append(f"  sin tocar   {_rangos(par.missing)}")
        if par.excepciones:
            # que el original rechace una entrada trampa es lo esperado, no un fallo
            lineas.append(f"  rechazos    {len(par.excepciones)} (p.ej. {par.excepciones[0][:60]})")
        if par.errores:
            lineas.append(f"  errores     {par.errores[0]}")
    medidos = [p for p in result.pairs if p.medido]
    if len(medidos) > 1:
        lineas.append("")
        lineas.append(
            f"total  {result.covered}/{result.statements} sentencias ({result.porcentaje:.1f}%)"
        )
    return "\n".join(lineas)


def markdown(result: CoverageResult) -> str:
    filas = [
        "| pareja | casos | sentencias | cubiertas | % | sin tocar |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for par in result.pairs:
        if par.motivo:
            filas.append(f"| `{par.pair_id}` | - | - | - | - | {par.motivo} |")
            continue
        filas.append(
            f"| `{par.pair_id}` | {par.cases} | {par.statements} | {par.covered} "
            f"| {par.porcentaje:.1f}% | {_rangos(par.missing)} |"
        )
    if len([p for p in result.pairs if p.medido]) > 1:
        filas.append(
            f"| **total** | | **{result.statements}** | **{result.covered}** | "
            f"**{result.porcentaje:.1f}%** | |"
        )
    return "\n".join(filas)


def as_json(result: CoverageResult) -> list[dict]:
    return [
        {
            "pair": par.pair_id,
            "script": par.script,
            "cases": par.cases,
            "statements": par.statements,
            "covered": par.covered,
            "percent": round(par.porcentaje, 2),
            "missing": par.missing,
            "reason": par.motivo or None,
        }
        for par in result.pairs
    ]
