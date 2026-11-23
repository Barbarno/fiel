"""Cuanto deja sin comprobar un corpus.

El corpus de `fiel` demuestra que el port coincide en los casos grabados. No dice
nada de los casos que no estan. Ese hueco es el que admiten las herramientas de
migracion ("solo detecta lo que cubre la grabacion") y nadie lo mide.

Aqui se mide sin instrumentar nada, sin dependencias y sin saber en que lenguaje
esta escrito el original:

1. Cada salida se reduce a una *forma*: el estado, el esqueleto del texto y el
   tamano. `5,6,7` y `1,2,3` son la misma forma; `error: foo` es otra.
2. Se generan sondas deterministas a partir de las entradas del corpus.
3. Se ejecuta el original sobre las sondas. Las formas que no aparecen en el
   corpus son **comportamiento no verificado**: el port puede hacer lo que
   quiera ahi y `fiel check` no dira nada.
4. Se ejecuta el port sobre esas sondas. Cada divergencia es un fallo real que
   el corpus no estaba viendo.

El numero que sale es la cobertura de comportamiento del corpus y la lista de
sondas que la suben.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from . import corpus as corpus_mod
from .compare import CompareError, Divergence, compare
from .runner import CRASH, ERR, OK, TIMEOUT, Observation, run
from .spec import Pair, Project

MAX_PROBES = 2000
SHAPE_LIMIT = 64


# ---------------------------------------------------------------- forma


def _shape_text(text: str) -> str:
    """Esqueleto estructural: que clase de caracter, y cuanto mide cada tirada.

    Se agrupa el valor pero no el tamano: `1,2,3` y `5,6,7` son la misma forma,
    mientras que `a,b,c` y `nombre,edad,ciudad` no lo son. Sin esa distincion
    todas las salidas de texto caen en una sola clase y la medida no dice nada.
    """
    out: list[str] = []
    index = 0
    size = len(text)
    while index < size and len(out) < SHAPE_LIMIT:
        char = text[index]
        if char.isdigit():
            kind = "9"
        elif char.isalpha():
            kind = "a"
        elif char in " \t":
            kind = "_"
        elif char.isascii() and char.isprintable():
            out.append(char)
            index += 1
            continue
        else:
            kind = "~"
        run = 1
        while index + run < size and run < 3:
            nxt = text[index + run]
            if kind == "9" and nxt.isdigit():
                run += 1
            elif kind == "a" and nxt.isalpha():
                run += 1
            elif kind == "_" and nxt in " \t":
                run += 1
            elif kind == "~" and not nxt.isascii():
                run += 1
            else:
                break
        out.append(kind * run)
        index += run
    return "".join(out)[:SHAPE_LIMIT]


def _shape_hex(data: bytes) -> str:
    """Para salidas binarias: el tamano y los primeros bytes, no el valor."""
    head = data[:16].hex()
    return f"bin:{len(data).bit_length()}:{head}"


def behavior_class(obs: Observation) -> str:
    """Identifica *que clase de cosa hace* el programa, no el valor exacto."""
    if obs.status in {TIMEOUT, CRASH}:
        return obs.status
    if obs.status == ERR:
        # el texto del error no distingue: la clase es "fallo controlado"
        return f"err:{len(obs.output).bit_length()}"
    try:
        text = obs.output.decode("utf-8")
    except UnicodeDecodeError:
        return f"ok:{_shape_hex(obs.output)}"
    return f"ok:{len(text).bit_length()}:{_shape_text(text)}"


# ---------------------------------------------------------------- sondas

_FIXED = [
    b"",
    b"\n",
    b" ",
    b"\t",
    b"0",
    b"-1",
    b"1",
    b"2147483647",
    b"4294967296",
    b"1e309",
    b"NaN",
    b"null",
    b"true",
    b"\x00",
    b"\x00\x00\x00",
    b"\xef\xbb\xbf",
    b"\xc3\xa9",
    b"\xc3\xb1",
    b"\xc2\xa0",
    b"\xe2\x84\xa6",
    b"\"",
    b"'",
    b"\\",
    b"%s",
    b"{0}",
    b"\r\n",
]

# Trampas semanticas: valores que separan implementaciones que "parecen" iguales.
# No son aleatorios, son las costuras conocidas entre lenguajes y bibliotecas:
# comillas, ceros a la izquierda, escapes, mayusculas que no son minusculas,
# numeros que no caben, y texto que no es UTF-8 valido.
_TRAPS = [
    b"a,\"b,c\",d",
    b"\"a b\"",
    b"'a b'",
    b"a\\ b",
    b"010.0.0.1",
    b"007",
    b"-0",
    b"+1",
    b"0x10",
    b"1_000",
    b"inf",
    b"-inf",
    b"\\x41",
    b"\\u00e9",
    b"a\rb",
    b"\xff\xfe",
    b"\xc3\x9f",
    b"\xc4\xb0",
    b"\xef\xac\x81",
    b"\xe2\x80\x8b",
    b"a\"b",
    b"a'b",
    b"a|b",
    b"a,b",
]

_DELIMS = [b"\n", b",", b"|", b"\x00", b"=", b";", b"\t", b"/"]


def _mutations(seed: bytes) -> list[bytes]:
    """Sondas derivadas de una entrada real. Deterministas y sin azar."""
    out: list[bytes] = []
    size = len(seed)
    if size:
        out.append(seed[:-1])
        out.append(seed[1:])
        out.append(seed[: size // 2])
        out.append(seed * 2)
        out.append(seed.upper())
        out.append(seed.lower())
        for delim in _DELIMS:
            out.append(seed + delim)
            out.append(delim + seed)
            out.append(seed + delim + seed)
        # comillas: separan un parser de verdad de un split a mano
        out.append(b'"' + seed + b'"')
        out.append(b"'" + seed + b"'")
        if b"," in seed:
            first, _, rest = seed.partition(b",")
            out.append(first + b',"' + rest + b'"')
        # corrimiento de un byte: rompe parsers de longitud y de indices
        out.append(bytes((b + 1) & 0xFF for b in seed))
    return out


def probe_inputs(seeds: list[bytes], budget: int = 400) -> list[bytes]:
    """Plan de sondas: fijas, mutaciones de cada semilla, y combinaciones."""
    budget = max(0, min(budget, MAX_PROBES))
    probes: list[bytes] = []
    seen: set[bytes] = set()

    def push(payload: bytes) -> None:
        if payload in seen or len(probes) >= budget:
            return
        seen.add(payload)
        probes.append(payload)

    for payload in _FIXED:
        push(payload)
    for payload in _TRAPS:
        push(payload)
    for seed in seeds:
        for payload in _mutations(seed):
            push(payload)
    # si aun queda presupuesto, cruza las dos primeras semillas
    if len(seeds) >= 2 and len(probes) < budget:
        for delim in _DELIMS:
            push(seeds[0] + delim + seeds[1])
            push(seeds[1] + delim + seeds[0])
    return probes


# ---------------------------------------------------------------- medida


@dataclass
class AdequacyPair:
    pair_id: str
    corpus_cases: int = 0
    corpus_classes: int = 0
    probes: int = 0
    probe_classes: int = 0
    novel_classes: int = 0
    divergences: list[Divergence] = field(default_factory=list)
    examples: list[tuple[bytes, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        if not self.probe_classes:
            return 0.0
        return self.corpus_classes / self.probe_classes

    @property
    def unverified(self) -> int:
        return self.novel_classes


@dataclass
class AdequacyResult:
    pairs: list[AdequacyPair] = field(default_factory=list)

    @property
    def errors(self) -> list[str]:
        return [e for p in self.pairs for e in p.errors]

    @property
    def divergences(self) -> int:
        return sum(len(p.divergences) for p in self.pairs)


def _probe_id(index: int) -> str:
    return f"probe{index:05d}"


def measure_pair(project: Project, pair: Pair, budget: int = 400) -> AdequacyPair:
    report = AdequacyPair(pair_id=pair.id)
    try:
        cases = corpus_mod.read(project.root / pair.corpus)
    except corpus_mod.CorpusError as exc:
        report.errors.append(str(exc))
        return report

    recorded = [c for c in cases if c.recorded]
    report.corpus_cases = len(recorded)
    if not recorded:
        report.errors.append(f"{pair.id}: el corpus no tiene ningun caso grabado")
        return report

    known: set[str] = set()
    for case in recorded:
        known.add(_class_of_status(case.status, case.output))

    report.corpus_classes = len(known)

    seeds = [c.input for c in recorded if c.input][:24]
    probes = probe_inputs(seeds, budget)
    report.probes = len(probes)

    seen: set[str] = set()
    novel_classes: set[str] = set()
    novel: list[tuple[int, bytes, str, Observation]] = []
    for index, payload in enumerate(probes):
        obs = run(pair.original.resolved(), payload, pair.timeout_ms, pair.original.working_dir(project.root))
        cls = behavior_class(obs)
        seen.add(cls)
        if cls in known:
            continue
        novel_classes.add(cls)
        novel.append((index, payload, cls, obs))
    report.probe_classes = len(seen | known)
    report.novel_classes = len(novel_classes)

    # se prueban TODAS las sondas fuera de cobertura, no una por forma: dos
    # entradas con la misma forma pueden desviarse en sitios distintos
    for index, payload, cls, original in novel:
        port = run(pair.port.resolved(), payload, pair.timeout_ms, pair.port.working_dir(project.root))
        fake = corpus_mod.Case(_probe_id(index), payload, "ok", b"")
        try:
            divergence = compare(fake, original, port, pair.normalize, pair.errors)
        except CompareError as exc:
            report.errors.append(f"{pair.id}/{fake.id}: {exc}")
            continue
        if divergence is None:
            continue
        report.divergences.append(divergence)
        if len(report.examples) < 6:
            report.examples.append((payload, cls))

    return report


def _class_of_status(status: str | None, output: bytes) -> str:
    if status is None:
        return "desconocido"
    return behavior_class(Observation(status, output))


def measure(project: Project, pairs: list[str] | None = None, budget: int = 400) -> AdequacyResult:
    selected = [p for p in project.pairs if pairs is None or p.id in pairs]
    if pairs and not selected:
        raise ValueError(f"ninguna pareja coincide con {pairs}")
    result = AdequacyResult()
    for pair in selected:
        result.pairs.append(measure_pair(project, pair, budget))
    return result


# ---------------------------------------------------------------- salida


def console(result: AdequacyResult) -> str:
    lines: list[str] = []
    for pair in result.pairs:
        if pair.errors:
            for error in pair.errors:
                lines.append(f"fiel: {error}")
            continue
        lines.append(
            f"{pair.pair_id}: el corpus vio {pair.corpus_classes} de las "
            f"{pair.probe_classes} formas que alcanzaron las sondas "
            f"({pair.coverage * 100:.1f}%)"
        )
        lines.append(
            f"  {pair.novel_classes} formas sin verificar, "
            f"{len(pair.divergences)} divergencias encontradas fuera del corpus"
        )
        for divergence in pair.divergences[:8]:
            lines.append(f"    {divergence.one_line()}")
        if len(pair.divergences) > 8:
            lines.append(f"    ... y {len(pair.divergences) - 8} mas")
    return "\n".join(lines)


def markdown(result: AdequacyResult) -> str:
    out = ["## Cobertura del corpus", ""]
    out.append("| pareja | casos | formas cubiertas | formas vistas | cobertura | sin verificar | divergencias nuevas |")
    out.append("|---|---|---|---|---|---|---|")
    for pair in result.pairs:
        if pair.errors:
            out.append(f"| {pair.pair_id} | error | | | | | {pair.errors[0]} |")
            continue
        out.append(
            f"| {pair.pair_id} | {pair.corpus_cases} | {pair.corpus_classes} | "
            f"{pair.probe_classes} | {pair.coverage * 100:.1f}% | "
            f"{pair.novel_classes} | {len(pair.divergences)} |"
        )
    return "\n".join(out)


def as_json(result: AdequacyResult) -> dict:
    return {
        "pairs": [
            {
                "id": pair.pair_id,
                "corpus_cases": pair.corpus_cases,
                "corpus_classes": pair.corpus_classes,
                "probe_classes": pair.probe_classes,
                "coverage": round(pair.coverage, 4),
                "unverified": pair.novel_classes,
                "divergences": [
                    {
                        "probe": d.case_id,
                        "kind": d.kind,
                        "original": d.original,
                        "port": d.port,
                    }
                    for d in pair.divergences
                ],
                "errors": pair.errors,
            }
            for pair in result.pairs
        ],
        "ok": not result.errors and not result.divergences,
    }


def seeds_digest(payloads: list[bytes]) -> str:
    """Huella del plan de sondas, para que dos ejecuciones sean comparables."""
    digest = hashlib.sha256()
    for payload in payloads:
        digest.update(payload)
        digest.update(b"\x1f")
    return digest.hexdigest()[:16]


def write_unverified(result: AdequacyResult, target: Path) -> int:
    """Deja las sondas sin verificar en un corpus de semillas, listo para grabar."""
    from . import mutate

    payloads: list[bytes] = []
    for pair in result.pairs:
        payloads.extend(payload for payload, _ in pair.examples)
    if not payloads:
        return 0
    added = mutate.add_inputs(target, payloads)
    return len(added)


__all__ = [
    "AdequacyPair",
    "AdequacyResult",
    "as_json",
    "behavior_class",
    "console",
    "markdown",
    "measure",
    "measure_pair",
    "probe_inputs",
    "seeds_digest",
    "write_unverified",
]
