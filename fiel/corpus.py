"""Lectura y escritura del corpus.

Una linea por caso, JSON:

    {"id": "c0001", "input_b64": "...", "status": "ok", "output_b64": "..."}

'status' solo aparece cuando el caso ya esta grabado.
Un fichero solo con id + input_b64 sirve como semilla para `fiel record`.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path

STATUSES = {"ok", "err"}


class CorpusError(Exception):
    pass


@dataclass(frozen=True)
class Case:
    id: str
    input: bytes
    status: str | None
    output: bytes

    @property
    def recorded(self) -> bool:
        return self.status in STATUSES


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64decode(text: str, where: str) -> bytes:
    try:
        return base64.b64decode(text.encode("ascii"), validate=True)
    except Exception as exc:
        raise CorpusError(f"{where}: base64 invalido ({exc})") from exc


def read(path: Path) -> list[Case]:
    if not path.is_file():
        raise CorpusError(f"no encuentro el corpus {path}")
    cases: list[Case] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8-sig") as handle:
        for number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            where = f"{path.name}:{number}"
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CorpusError(f"{where}: JSON invalido ({exc})") from exc
            if not isinstance(raw, dict):
                raise CorpusError(f"{where}: se esperaba un objeto")

            cid = raw.get("id")
            if not isinstance(cid, str) or not cid:
                raise CorpusError(f"{where}: falta 'id'")
            if cid in seen:
                raise CorpusError(f"{where}: id duplicado '{cid}'")
            seen.add(cid)

            if "input_b64" not in raw:
                raise CorpusError(f"{where}: falta 'input_b64'")
            payload = _b64decode(str(raw["input_b64"]), where)

            status = raw.get("status")
            if status is not None and status not in STATUSES:
                raise CorpusError(f"{where}: 'status' debe ser ok o err")
            output = b""
            if "output_b64" in raw:
                output = _b64decode(str(raw["output_b64"]), where)

            cases.append(Case(id=cid, input=payload, status=status, output=output))
    if not cases:
        raise CorpusError(f"{path} no tiene ningun caso")
    return cases


def write(path: Path, cases: list[Case]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for case in sorted(cases, key=lambda c: c.id):
        row = {"id": case.id, "input_b64": _b64encode(case.input)}
        if case.recorded:
            row["status"] = case.status
            row["output_b64"] = _b64encode(case.output)
        lines.append(json.dumps(row, ensure_ascii=False, sort_keys=True))
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(path)
