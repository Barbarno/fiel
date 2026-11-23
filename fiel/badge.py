"""Una chapa SVG con el resultado de la comprobacion, para el README.

GitHub no deja ejecutar codigo en un README, pero si deja enseñar una imagen.
`fiel badge` escribe ese SVG: cuantos casos del corpus siguen siendo fieles y
cuantos no. Sin dependencias, sin servicios externos, sin JavaScript: el
fichero se genera con texto y se commitea.

    fiel badge --out fiel.svg
    fiel badge --out fiel.svg --pair cron-fiel

Los colores solo dicen una cosa: verde si todo es fiel, ambar si queda poco,
rojo si el port se ha desviado de verdad. El texto va siempre, para que la
chapa siga teniendo sentido en blanco y negro y para quien use lector de
pantalla.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .check import CheckResult

VERDE = "#2f6f4e"
AMBAR = "#8a6a1f"
ROJO = "#8c2f24"
GRIS = "#4a473c"


@dataclass(frozen=True)
class Chapa:
    etiqueta: str
    valor: str
    color: str
    fieles: int
    total: int


def resumen(result: CheckResult) -> Chapa:
    total = result.total
    fieles = sum(p.passed for p in result.pairs)
    if total == 0:
        return Chapa("fiel", "sin casos", GRIS, 0, 0)
    if fieles == total and not result.errors:
        return Chapa("fiel", f"{fieles}/{total}", VERDE, fieles, total)
    proporcion = fieles / total
    if proporcion >= 0.9:
        return Chapa("fiel", f"{fieles}/{total}", AMBAR, fieles, total)
    return Chapa("fiel", f"{fieles}/{total}", ROJO, fieles, total)


def _ancho(texto: str) -> float:
    # 6,2 px por caracter a 11 px: suficiente para que el texto no se salga
    return len(texto) * 6.2 + 10


def svg(chapa: Chapa) -> str:
    izq = _ancho(chapa.etiqueta)
    der = _ancho(chapa.valor)
    total = izq + der
    titulo = f"{chapa.etiqueta}: {chapa.valor} casos fieles"
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="20" '
        'role="img" aria-label="{titulo}">'
        "<title>{titulo}</title>"
        '<linearGradient id="s" x2="0" y2="100%">'
        '<stop offset="0" stop-color="#fff" stop-opacity=".18"/>'
        '<stop offset="1" stop-opacity=".18"/>'
        "</linearGradient>"
        '<clipPath id="r"><rect width="{w:.0f}" height="20" rx="3" fill="#fff"/></clipPath>'
        '<g clip-path="url(#r)">'
        '<rect width="{izq:.0f}" height="20" fill="#4a473c"/>'
        '<rect x="{izq:.0f}" width="{der:.0f}" height="20" fill="{color}"/>'
        '<rect width="{w:.0f}" height="20" fill="url(#s)"/>'
        "</g>"
        '<g fill="#fff" text-anchor="middle" '
        'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">'
        '<text x="{tx1:.0f}" y="14">{etiqueta}</text>'
        '<text x="{tx2:.0f}" y="14" font-weight="bold">{valor}</text>'
        "</g>"
        "</svg>"
    ).format(
        w=total,
        izq=izq,
        der=der,
        color=chapa.color,
        titulo=titulo.replace("&", "&amp;").replace("<", "&lt;"),
        etiqueta=chapa.etiqueta,
        valor=chapa.valor,
        tx1=izq / 2,
        tx2=izq + der / 2,
    )


def escribir(ruta: Path, result: CheckResult) -> Chapa:
    chapa = resumen(result)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(svg(chapa) + "\n", encoding="utf-8", newline="\n")
    return chapa
