"""Anade casos nuevos a un corpus existente.

Es lo que convierte el corpus en algo vivo: cada vez que aparece un fallo en
produccion, se anade su entrada. El guardian se hace mas fuerte con el tiempo.
"""

from __future__ import annotations

from pathlib import Path

from . import corpus as corpus_mod
from .spec import Pair


def next_id(cases: list[corpus_mod.Case], prefix: str = "u") -> str:
    used = {c.id for c in cases}
    index = 1
    while f"{prefix}{index:04d}" in used:
        index += 1
    return f"{prefix}{index:04d}"


def add_inputs(path: Path, payloads: list[bytes], prefix: str = "u") -> list[str]:
    cases = corpus_mod.read(path) if path.is_file() else []
    added: list[str] = []
    for payload in payloads:
        cid = next_id(cases, prefix)
        cases.append(corpus_mod.Case(cid, payload, None, b""))
        added.append(cid)
    corpus_mod.write(path, cases)
    return added


def read_input_file(path: Path) -> list[bytes]:
    """Un caso por linea. Las lineas vacias se saltan."""
    payloads: list[bytes] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            payloads.append(line.encode("utf-8"))
    return payloads


def corpus_for(pair: Pair, root: Path) -> Path:
    return root / pair.corpus
