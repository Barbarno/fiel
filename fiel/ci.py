"""Escribe el workflow de GitHub Actions que ejecuta la comprobacion.

`fiel guard` cubre el portatil; esto cubre el repositorio. El workflow que
genera no es una plantilla generica: lleva la especificacion del proyecto, las
parejas que existen de verdad y el mismo `fiel check` que se lanza a mano, con
`--format github` para que las divergencias salgan como anotaciones en el diff
del pull request.

    fiel ci --install
    fiel ci --install --out .github/workflows/fidelidad.yml
    fiel ci --remove

Si el fichero ya existe y no lo escribio fiel, no se toca salvo con --force.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .spec import Project

MARCA = "# fiel: puerta de fidelidad en CI"
RUTA_POR_DEFECTO = Path(".github") / "workflows" / "fiel.yml"


class CiError(Exception):
    pass


@dataclass(frozen=True)
class Estado:
    ruta: Path
    existe: bool
    nuestro: bool
    parejas: tuple[str, ...] = ()


def _parejas(project: Project, seleccion: tuple[str, ...]) -> tuple[str, ...]:
    disponibles = tuple(p.id for p in project.pairs)
    if not seleccion:
        return disponibles
    for pedida in seleccion:
        if pedida not in disponibles:
            raise CiError(f"no existe la pareja {pedida} en la especificacion")
    return seleccion


def _selectores(parejas: tuple[str, ...], todas: tuple[str, ...]) -> str:
    # si van todas, no hace falta listarlas: el workflow se lee mejor
    if tuple(parejas) == tuple(todas):
        return ""
    return "".join(f" --pair {p}" for p in parejas)


def guion(
    project: Project,
    parejas: tuple[str, ...],
    spec: str = "fiel.toml",
    python: str = "3.12",
    install: str = 'pip install "fiel @ git+https://github.com/Barbarno/fiel"',
) -> str:
    todas = tuple(p.id for p in project.pairs)
    parejas = _parejas(project, tuple(parejas))
    selectores = _selectores(parejas, todas)
    lineas = [
        MARCA + ". Generado por 'fiel ci'. No editar a mano.",
        "# Quitar con: fiel ci --remove",
        "name: fidelidad",
        "",
        "on:",
        "  push:",
        "    branches: [main]",
        "  pull_request:",
        "",
        "jobs:",
        "  fiel:",
        "    name: el port sigue haciendo lo mismo que el original",
        "    runs-on: ubuntu-latest",
        "    steps:",
        "      - uses: actions/checkout@v5",
        "",
        "      - uses: actions/setup-python@v6",
        "        with:",
        f'          python-version: "{python}"',
        "",
        "      - name: Instalar fiel",
        f"        run: {install}",
        "",
        "      - name: Comprobar la fidelidad",
        f"        run: fiel --spec {spec} check{selectores} --format github",
        "",
    ]
    return "\n".join(lineas)


def estado(root: Path, destino: Path) -> Estado:
    ruta = destino if destino.is_absolute() else (root / destino)
    ruta = ruta.resolve()
    contenido = ruta.read_text(encoding="utf-8", errors="replace") if ruta.is_file() else ""
    return Estado(ruta=ruta, existe=ruta.is_file(), nuestro=MARCA in contenido)


def escribir(
    project: Project,
    destino: Path = RUTA_POR_DEFECTO,
    parejas: tuple[str, ...] = (),
    spec: str = "fiel.toml",
    force: bool = False,
    install: str = 'pip install "fiel @ git+https://github.com/Barbarno/fiel"',
) -> Estado:
    elegidas = _parejas(project, parejas)
    actual = estado(project.root, destino)
    if actual.existe and not actual.nuestro and not force:
        raise CiError(
            f"{actual.ruta} ya existe y no lo escribio fiel. "
            "Muevelo o repite con --force para sustituirlo."
        )
    actual.ruta.parent.mkdir(parents=True, exist_ok=True)
    actual.ruta.write_text(
        guion(project, elegidas, spec, install=install), encoding="utf-8", newline="\n"
    )
    return Estado(ruta=actual.ruta, existe=True, nuestro=True, parejas=elegidas)


def quitar(root: Path, destino: Path = RUTA_POR_DEFECTO) -> Estado:
    actual = estado(root, destino)
    if not actual.existe:
        return actual
    if not actual.nuestro:
        raise CiError(f"{actual.ruta} no lo escribio fiel; no se toca")
    actual.ruta.unlink()
    padre = actual.ruta.parent
    # deja el arbol como estaba: si la carpeta quedo vacia, se va
    while padre != root and padre.is_dir() and not any(padre.iterdir()):
        padre.rmdir()
        padre = padre.parent
    return estado(root, destino)


def console(actual: Estado, root: Path) -> str:
    try:
        corta = actual.ruta.relative_to(root)
    except ValueError:
        corta = actual.ruta
    if not actual.existe:
        texto = "no instalado"
    elif actual.nuestro:
        texto = "instalado"
    else:
        texto = "ocupado por otro workflow"
    lineas = [f"  fichero  {corta}", f"  estado   {texto}"]
    if actual.parejas:
        lineas.append(f"  parejas  {', '.join(actual.parejas)}")
    return "\n".join(lineas)
