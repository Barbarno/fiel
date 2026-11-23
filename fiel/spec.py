"""Carga y validacion de fiel.toml."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None

PY_NAMES = {"python", "python3", "py"}


class SpecError(Exception):
    pass


@dataclass(frozen=True)
class Endpoint:
    command: tuple[str, ...]
    cwd: str | None = None

    def resolved(self) -> list[str]:
        """Sustituye 'python' por el interprete actual para que funcione igual
        en Windows y en Linux."""
        cmd = list(self.command)
        if cmd and cmd[0].lower() in PY_NAMES:
            cmd[0] = sys.executable
        return cmd

    def working_dir(self, root: Path) -> Path:
        """Directorio desde el que se ejecuta este lado de la pareja."""
        if not self.cwd:
            return root
        candidate = Path(self.cwd)
        return candidate if candidate.is_absolute() else root / candidate


@dataclass(frozen=True)
class Pair:
    id: str
    original: Endpoint
    port: Endpoint
    corpus: str
    timeout_ms: int = 5000
    normalize: str = "text"
    errors: str = "compare"

    @property
    def corpus_path(self) -> str:
        return self.corpus


@dataclass(frozen=True)
class Project:
    root: Path
    pairs: tuple[Pair, ...]
    baseline: str = "fiel.baseline.json"

    def baseline_path(self) -> Path:
        return self.root / self.baseline


def _endpoint(raw: dict, where: str) -> Endpoint:
    if not isinstance(raw, dict):
        raise SpecError(f"{where}: debe ser una tabla")
    command = raw.get("command")
    if not isinstance(command, list) or not command:
        raise SpecError(f"{where}: falta 'command' o no es una lista")
    if not all(isinstance(c, str) for c in command):
        raise SpecError(f"{where}: 'command' debe ser una lista de cadenas")
    cwd = raw.get("cwd")
    if cwd is not None and not isinstance(cwd, str):
        raise SpecError(f"{where}: 'cwd' debe ser una cadena")
    return Endpoint(tuple(command), cwd)


def load(root: Path, name: str = "fiel.toml") -> Project:
    if tomllib is None:
        raise SpecError("hace falta Python 3.11 o superior para leer TOML")
    path = root / name
    if not path.is_file():
        raise SpecError(f"no encuentro {path}")
    with path.open("r", encoding="utf-8-sig") as handle:
        data = tomllib.loads(handle.read())

    raw_pairs = data.get("pair")
    if not isinstance(raw_pairs, list) or not raw_pairs:
        raise SpecError("fiel.toml necesita al menos una [[pair]]")

    pairs: list[Pair] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_pairs):
        where = f"pair[{index}]"
        pid = raw.get("id")
        if not isinstance(pid, str) or not pid:
            raise SpecError(f"{where}: falta 'id'")
        if pid in seen:
            raise SpecError(f"{where}: id duplicado '{pid}'")
        seen.add(pid)

        corpus = raw.get("corpus")
        if not isinstance(corpus, str) or not corpus:
            raise SpecError(f"{where}: falta 'corpus'")

        normalize = raw.get("normalize", "text")
        if normalize not in {"text", "json", "bytes"}:
            raise SpecError(f"{where}: 'normalize' debe ser text, json o bytes")

        errors = raw.get("errors", "compare")
        if errors not in {"compare", "ignore"}:
            raise SpecError(f"{where}: 'errors' debe ser compare o ignore")

        timeout_ms = raw.get("timeout_ms", 5000)
        if not isinstance(timeout_ms, int) or timeout_ms <= 0:
            raise SpecError(f"{where}: 'timeout_ms' debe ser un entero positivo")

        pairs.append(
            Pair(
                id=pid,
                original=_endpoint(raw.get("original"), f"{where}.original"),
                port=_endpoint(raw.get("port"), f"{where}.port"),
                corpus=corpus,
                timeout_ms=timeout_ms,
                normalize=normalize,
                errors=errors,
            )
        )

    baseline = data.get("project", {}).get("baseline", "fiel.baseline.json")
    if not isinstance(baseline, str):
        raise SpecError("project.baseline debe ser una cadena")

    return Project(root=root, pairs=tuple(pairs), baseline=baseline)


TEMPLATE = """\
# fiel.toml - una pareja por cada unidad que quieras mantener fiel.
# El corpus guarda lo que hace el original. El port tiene que hacer lo mismo.

[project]
baseline = "fiel.baseline.json"

[[pair]]
id = "ejemplo"
original = { command = ["python", "original.py"] }
port = { command = ["python", "port.py"] }
corpus = "corpus/ejemplo.jsonl"
timeout_ms = 5000
# text | json | bytes
normalize = "text"
# compare | ignore  (si el mensaje de error del port no tiene por que coincidir)
errors = "compare"
"""
