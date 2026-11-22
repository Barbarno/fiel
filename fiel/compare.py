"""Normalizacion y comparacion.

Sin normalizar, el 90% de los hallazgos son ruido: el mismo valor escrito de
otra forma en dos lenguajes. Aqui se decide que cuenta como diferencia.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .corpus import Case
from .runner import CRASH, ERR, OK, TIMEOUT, Observation


class CompareError(Exception):
    pass


@dataclass(frozen=True)
class Divergence:
    case_id: str
    kind: str          # status | output | error-text
    original: str
    port: str
    signature: str

    def one_line(self) -> str:
        return f"[{self.kind}] caso {self.case_id}: original={self.original!r} port={self.port!r}"


def _as_text(data: bytes) -> str:
    text = data.decode("utf-8", "replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _as_json(data: bytes) -> str:
    text = data.decode("utf-8", "replace").strip()
    if not text:
        return ""
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CompareError(f"salida que no es JSON valido: {exc}") from exc
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def normalize(data: bytes, kind: str) -> str:
    if kind == "bytes":
        return data.hex()
    if kind == "text":
        return _as_text(data)
    if kind == "json":
        return _as_json(data)
    raise CompareError(f"tipo de normalizacion desconocido: {kind}")


def _signature(*parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def compare(
    case: Case,
    original: Observation,
    port: Observation,
    kind: str,
    errors: str,
) -> Divergence | None:
    """Devuelve None si el port es fiel en este caso."""
    if case.status is None:
        raise CompareError(f"el caso {case.id} no tiene salida grabada")

    # 1. el estado tiene que coincidir, salvo timeout/crash que son categorias propias
    if original.status != port.status:
        return Divergence(
            case_id=case.id,
            kind="status",
            original=original.status,
            port=port.status if not port.detail else f"{port.status} ({port.detail})",
            signature=_signature("status", original.status, port.status),
        )

    # 2. si el original fallo de forma controlada y el mensaje no importa, paramos aqui
    if original.status == ERR and errors == "ignore":
        return None

    # 3. timeouts y crashes no tienen salida comparable
    if original.status in {TIMEOUT, CRASH}:
        return None

    left = normalize(original.output, kind)
    right = normalize(port.output, kind)
    if left == right:
        return None

    label = "error-text" if original.status == ERR else "output"
    return Divergence(
        case_id=case.id,
        kind=label,
        original=_clip(left),
        port=_clip(right),
        signature=_signature(left, right),
    )


def _clip(text: str, limit: int = 160) -> str:
    flat = text.replace("\n", "\\n")
    if len(flat) <= limit:
        return flat
    return flat[:limit] + "..."


def first_difference(a: str, b: str, context: int = 40) -> tuple[str, int]:
    """Posicion del primer byte distinto, con contexto, para el informe."""
    limit = min(len(a), len(b))
    for index in range(limit):
        if a[index] != b[index]:
            start = max(0, index - context)
            return (f"...{a[start:index]}[AQUI]", index)
    return (f"...{a[limit:limit + context]}", limit)


def recorded_matches(case: Case, obs: Observation, kind: str) -> bool:
    """Comprueba que el original sigue haciendo lo que dice el corpus."""
    if case.status != obs.status:
        return False
    if case.status in {TIMEOUT, CRASH}:
        return True
    try:
        return normalize(case.output, kind) == normalize(obs.output, kind)
    except CompareError:
        return False


__all__ = [
    "CompareError",
    "Divergence",
    "compare",
    "first_difference",
    "normalize",
    "recorded_matches",
    "OK",
]
