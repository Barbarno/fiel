"""Importa corpus de otras herramientas al formato de fiel.

Tolerante a proposito: no conocemos el formato exacto de cada herramienta de
migracion, y el corpus es lo unico que no podemos regenerar sin volver a
ejecutar el original. Adivinar campos es mejor que exigir un esquema.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path

ID_KEYS = ("id", "case_id", "caseId", "name", "key", "index")
INPUT_KEYS = ("input_b64", "input", "stdin", "payload", "args", "arguments", "call")
OUTPUT_KEYS = ("output_b64", "output", "stdout", "result", "value", "returns")
STATUS_KEYS = ("status", "ok", "outcome", "kind")

OK_WORDS = {"ok", "pass", "passed", "success", "true", "1"}
ERR_WORDS = {"err", "error", "fail", "failed", "panic", "crash", "false", "0"}


class ImportError_(Exception):
    pass


@dataclass
class ImportReport:
    total: int = 0
    skipped: int = 0
    reasons: list[str] = field(default_factory=list)


def _first(row: dict, keys: tuple[str, ...]):
    for key in keys:
        if key in row and row[key] is not None:
            return key, row[key]
    return None, None


def _to_bytes(key: str, value) -> bytes:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    if isinstance(value, bool):
        return b"1" if value else b"0"
    if isinstance(value, (int, float)):
        return str(value).encode("utf-8")
    text = str(value)
    if key.endswith("_b64"):
        try:
            return base64.b64decode(text.encode("ascii"), validate=True)
        except Exception as exc:
            raise ImportError_(f"base64 invalido en '{key}': {exc}") from exc
    return text.encode("utf-8")


def _to_status(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "ok" if value else "err"
    word = str(value).strip().lower()
    if word in OK_WORDS:
        return "ok"
    if word in ERR_WORDS:
        return "err"
    return None


def read_foreign(path: Path) -> tuple[list[dict], ImportReport]:
    if not path.is_file():
        raise ImportError_(f"no encuentro {path}")
    rows: list[dict] = []
    report = ImportReport()
    with path.open("r", encoding="utf-8-sig") as handle:
        for number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            report.total += 1
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                report.skipped += 1
                report.reasons.append(f"{path.name}:{number}: JSON invalido ({exc})")
                continue
            if not isinstance(raw, dict):
                report.skipped += 1
                report.reasons.append(f"{path.name}:{number}: no es un objeto")
                continue

            id_key, cid = _first(raw, ID_KEYS)
            in_key, payload = _first(raw, INPUT_KEYS)
            if in_key is None:
                report.skipped += 1
                report.reasons.append(f"{path.name}:{number}: sin campo de entrada")
                continue

            entry = {
                "id": str(cid) if cid is not None else f"case{number:05d}",
                "input": _to_bytes(in_key, payload),
            }

            st_key, st_value = _first(raw, STATUS_KEYS)
            out_key, out_value = _first(raw, OUTPUT_KEYS)
            if out_key is not None:
                entry["output"] = _to_bytes(out_key, out_value)
                entry["status"] = _to_status(st_value) or "ok"
            elif st_key is not None:
                entry["status"] = _to_status(st_value)
            rows.append(entry)
    report.total = len(rows) + report.skipped
    return rows, report


def to_fiel(rows: list[dict]) -> list[dict]:
    """Convierte al formato exacto de fiel (id + base64)."""
    out: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        cid = row["id"]
        if cid in seen:
            suffix = 2
            while f"{cid}-{suffix}" in seen:
                suffix += 1
            cid = f"{cid}-{suffix}"
        seen.add(cid)
        line = {"id": cid, "input_b64": base64.b64encode(row["input"]).decode("ascii")}
        if "output" in row and row.get("status"):
            line["status"] = row["status"]
            line["output_b64"] = base64.b64encode(row["output"]).decode("ascii")
        out.append(line)
    return out


def write_corpus(rows: list[dict], path: Path, append: bool = False) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict] = []
    if append and path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    existing.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    known = {row["id"] for row in existing}
    merged = existing + [row for row in rows if row["id"] not in known]
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in merged) + "\n", encoding="utf-8")
    return len(merged) - len(existing)
