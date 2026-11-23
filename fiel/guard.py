"""Instala fiel como puerta de git: no se commitea una divergencia nueva.

`fiel check` se lanza cuando alguien se acuerda. Un hook de git se lanza
siempre, en la maquina de cada uno, antes de que el commit exista. Este comando
escribe ese hook y lo quita cuando ya no hace falta.

    fiel guard --install
    fiel guard --status
    fiel guard --remove

El hook no adivina nada: ejecuta exactamente el mismo `fiel check` que se lanza
a mano, con la misma especificacion, y devuelve su codigo de salida. Si hay una
divergencia nueva, el commit no se crea.

Un proyecto puede tener parejas que divergen a proposito (el ejemplo del
repositorio tiene una, para ensenar el fallo). Para eso esta `--pair`: la puerta
se apunta a las parejas que tienen que seguir siendo fieles y deja en paz las
demas.

    fiel guard --install --pair cron-fiel
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MARCA = "# fiel: puerta de fidelidad"


class GuardError(Exception):
    pass


@dataclass(frozen=True)
class Estado:
    raiz: Path
    hooks: Path
    hook: Path
    comando: str
    instalado: bool
    nuestro: bool


def _git(args: list[str], cwd: Path) -> str:
    try:
        salida = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GuardError("git no esta en el PATH") from exc
    if salida.returncode != 0:
        raise GuardError(salida.stderr.strip() or f"git {args[0]} fallo")
    return salida.stdout.strip()


def raiz(cwd: Path) -> Path:
    try:
        return Path(_git(["rev-parse", "--show-toplevel"], cwd)).resolve()
    except GuardError as exc:
        raise GuardError(f"{cwd} no esta dentro de un repositorio git ({exc})") from exc


def dir_hooks(cwd: Path) -> Path:
    ruta = Path(_git(["rev-parse", "--git-path", "hooks"], cwd))
    return (cwd / ruta).resolve() if not ruta.is_absolute() else ruta


def _comando(spec: str, python: str, pairs: tuple[str, ...] = ()) -> str:
    base = f'{python} -m fiel --spec "{spec}" check'
    if not pairs:
        return base
    selectores = " ".join(f'--pair "{p}"' for p in pairs)
    return f"{base} {selectores}"


def _guion(spec: str, python: str, pairs: tuple[str, ...] = ()) -> str:
    return (
        "#!/bin/sh\n"
        f"{MARCA}. Generado por 'fiel guard'. No editar a mano.\n"
        "# Quitar con: fiel guard --remove\n"
        "#\n"
        "# Se ejecuta desde la raiz del repositorio. Sale 1 si el port deja de\n"
        "# hacer lo mismo que el original en algun caso del corpus.\n"
        f"exec {_comando(spec, python, pairs)}\n"
    )


def estado(
    root: Path,
    spec: str = "fiel.toml",
    hook: str = "pre-commit",
    python: str = "python",
    pairs: tuple[str, ...] = (),
) -> Estado:
    repo = raiz(root)
    hooks = dir_hooks(repo)
    destino = hooks / hook
    contenido = destino.read_text(encoding="utf-8", errors="replace") if destino.is_file() else ""
    return Estado(
        raiz=repo,
        hooks=hooks,
        hook=destino,
        comando=_comando(spec, python, pairs),
        instalado=destino.is_file(),
        nuestro=MARCA in contenido,
    )


def instalar(
    root: Path,
    spec: str = "fiel.toml",
    hook: str = "pre-commit",
    python: str = "python",
    force: bool = False,
    pairs: tuple[str, ...] = (),
) -> Estado:
    actual = estado(root, spec, hook, python, pairs)
    if not (actual.raiz / spec).is_file():
        raise GuardError(
            f"no encuentro {spec} en {actual.raiz}: el hook fallaria en cada commit"
        )
    if actual.instalado and not actual.nuestro and not force:
        raise GuardError(
            f"{actual.hook} ya existe y no lo escribio fiel. "
            "Muevelo o repite con --force para sustituirlo."
        )
    actual.hooks.mkdir(parents=True, exist_ok=True)
    actual.hook.write_text(_guion(spec, python, pairs), encoding="utf-8", newline="\n")
    if os.name != "nt":
        # git solo ejecuta el hook si tiene permiso de ejecucion
        actual.hook.chmod(0o755)
    return estado(root, spec, hook, python, pairs)


def quitar(
    root: Path,
    spec: str = "fiel.toml",
    hook: str = "pre-commit",
    python: str = "python",
    pairs: tuple[str, ...] = (),
) -> Estado:
    actual = estado(root, spec, hook, python, pairs)
    if not actual.instalado:
        return actual
    if not actual.nuestro:
        raise GuardError(f"{actual.hook} no lo escribio fiel; no se toca")
    actual.hook.unlink()
    return estado(root, spec, hook, python, pairs)


def _ruta_corta(repo: Path, ruta: Path) -> str:
    try:
        return str(ruta.relative_to(repo))
    except ValueError:
        return str(ruta)


def console(actual: Estado) -> str:
    if not actual.instalado:
        estado_texto = "no instalado"
    elif actual.nuestro:
        estado_texto = "instalado"
    else:
        estado_texto = "ocupado por otro hook"
    lineas = [
        f"  repositorio  {actual.raiz}",
        f"  hook         {_ruta_corta(actual.raiz, actual.hook)}",
        f"  comando      {actual.comando}",
        f"  estado       {estado_texto}",
        f"  git          {shutil.which('git') or 'no encontrado'}",
    ]
    return "\n".join(lineas)


def cmd_guard(args) -> int:
    root = Path(args.root).resolve()
    spec = args.spec or "fiel.toml"
    pairs = tuple(args.pair or ())
    try:
        if args.remove:
            resultado = quitar(root, spec, args.hook, args.python, pairs)
            verbo = "quitado" if not resultado.instalado else "no estaba"
            print(f"fiel guard: {verbo} en {_ruta_corta(resultado.raiz, resultado.hook)}")
            return 0
        if args.install:
            resultado = instalar(root, spec, args.hook, args.python, force=args.force, pairs=pairs)
            print(console(resultado))
            print("")
            print("desde ahora, 'git commit' ejecuta la comprobacion antes de crear el commit.")
            return 0
        print(console(estado(root, spec, args.hook, args.python, pairs)))
        return 0
    except GuardError as exc:
        print(f"fiel guard: {exc}", file=sys.stderr)
        return 2
