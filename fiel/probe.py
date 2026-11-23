"""Prueba una entrada suelta contra una pareja, sin grabarla en el corpus.

Es la respuesta a la pregunta que llega en mitad de una reunion: "y esta
entrada concreta, la traga igual?". No hace falta corpus, ni fichero, ni
grabar nada: se lanzan los dos lados con esos bytes y se comparan.

    fiel probe --pair url --input "http://host/a#b"
    fiel probe --pair url --input @entrada.txt
    echo -n "a,b" | fiel probe --pair csv --stdin

Sale 0 si el port es fiel en esa entrada y 1 si no, para poder encadenarlo.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path

from .compare import CompareError, Divergence, compare, first_difference, normalize
from .corpus import Case
from .runner import Observation, run
from .spec import Project

MARCA_ENTRADA = "@"


class ProbeError(Exception):
    pass


@dataclass(frozen=True)
class ProbeResult:
    pair_id: str
    payload: bytes
    original: Observation
    port: Observation
    divergencia: Divergence | None
    posicion: int = 0
    texto_original: str = ""
    texto_port: str = ""

    @property
    def fiel(self) -> bool:
        return self.divergencia is None


def leer_entrada(texto: str) -> bytes:
    """Un @ delante lee de un fichero; si no, es la entrada tal cual."""
    if texto.startswith(MARCA_ENTRADA):
        ruta = Path(texto[len(MARCA_ENTRADA):]).expanduser()
        if not ruta.is_file():
            raise ProbeError(f"no existe el fichero {ruta}")
        return ruta.read_bytes()
    if texto.startswith("\\x"):
        return bytes.fromhex(texto[2:])
    return texto.encode("utf-8")


def una(pair, project: Project, payload: bytes) -> ProbeResult:
    original = run(pair.original.resolved(), payload, pair.timeout_ms, pair.original.working_dir(project.root))
    port = run(pair.port.resolved(), payload, pair.timeout_ms, pair.port.working_dir(project.root))

    caso = Case(id=f"probe:{pair.id}", input=payload, status="ok", output=b"")
    try:
        divergencia = compare(caso, original, port, pair.normalize, pair.errors)
    except CompareError as exc:
        raise ProbeError(str(exc)) from exc

    posicion = 0
    izquierda = derecha = ""
    if divergencia is not None and divergencia.kind in {"output", "error-text"}:
        try:
            izquierda = normalize(original.output, pair.normalize)
            derecha = normalize(port.output, pair.normalize)
        except CompareError:
            pass
        else:
            _, posicion = first_difference(izquierda, derecha)

    return ProbeResult(
        pair_id=pair.id,
        payload=payload,
        original=original,
        port=port,
        divergencia=divergencia,
        posicion=posicion,
        texto_original=izquierda,
        texto_port=derecha,
    )


def obtener(project: Project, pair_id: str):
    for pair in project.pairs:
        if pair.id == pair_id:
            return pair
    disponibles = ", ".join(p.id for p in project.pairs)
    raise ProbeError(f"no existe la pareja '{pair_id}'. Hay: {disponibles}")


def _texto(datos: bytes, limite: int = 120) -> str:
    if not datos:
        return "(vacio)"
    visible = datos.decode("utf-8", "replace").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    if len(visible) > limite:
        visible = visible[:limite] + "..."
    return visible


def console(resultado: ProbeResult, diff: bool = False) -> str:
    lineas = [f"entrada   {_texto(resultado.payload)}"]
    if resultado.fiel:
        lineas.append(f"original  {resultado.original.status}: {_texto(resultado.original.output)}")
        lineas.append("port      igual: esta entrada sale fiel")
        lineas.append("veredicto FIEL")
        return "\n".join(lineas)

    divergencia = resultado.divergencia
    assert divergencia is not None
    lineas.append(f"original  {resultado.original.status}: {_texto(resultado.original.output)}")
    lineas.append(f"port      {resultado.port.status}: {_texto(resultado.port.output)}")
    lineas.append(f"tipo      {divergencia.kind}")
    if resultado.posicion:
        lineas.append(f"desde     el caracter {resultado.posicion}")
    if diff and resultado.texto_original != resultado.texto_port:
        lineas.append("")
        lineas.extend(unified(resultado))
    lineas.append("veredicto NO FIEL")
    return "\n".join(lineas)


def unified(resultado: ProbeResult, context: int = 2) -> list[str]:
    """Las dos salidas como diff unificado: - lo que hacia el original, + lo que hace el port."""
    izquierda = resultado.texto_original.split("\n")
    derecha = resultado.texto_port.split("\n")
    return list(
        difflib.unified_diff(
            izquierda,
            derecha,
            fromfile="original",
            tofile="port",
            n=context,
            lineterm="",
        )
    )


def as_json(resultado: ProbeResult) -> dict:
    return {
        "pair": resultado.pair_id,
        "faithful": resultado.fiel,
        "kind": resultado.divergencia.kind if resultado.divergencia else None,
        "original_status": resultado.original.status,
        "port_status": resultado.port.status,
        "original_output_hex": resultado.original.output[:4096].hex(),
        "port_output_hex": resultado.port.output[:4096].hex(),
        "position": resultado.posicion,
    }
