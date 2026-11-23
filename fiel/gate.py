"""El port no debe necesitar el original para funcionar.

Un port que pasa los 40 casos del corpus puede estar haciendo trampa: en vez de
reimplementar la funcion, llama al original por debajo. En Python es trivial
(`subprocess.run(["python", "original.py"])`), y en una migracion real es el
fallo que mas caro sale, porque el dia que se borre el original el port muere.

La comprobacion es la definicion literal de independencia y no necesita nada
instalado: se esconde el original, se vuelve a ejecutar el port, y si los casos
que antes pasaban ahora fallan, el port lo estaba llamando.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from . import corpus as corpus_mod
from .compare import CompareError, compare
from .runner import Observation, run
from .spec import Pair, Project

HIDDEN_SUFFIX = ".fiel-hidden"


@dataclass
class GatePair:
    pair_id: str
    sampled: int = 0
    passing_before: int = 0
    passing_hidden: int = 0
    broken_by_hiding: list[str] = field(default_factory=list)
    hidden_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def independent(self) -> bool:
        return not self.broken_by_hiding and not self.errors


@dataclass
class GateResult:
    pairs: list[GatePair] = field(default_factory=list)

    @property
    def errors(self) -> list[str]:
        return [e for p in self.pairs for e in p.errors]

    @property
    def dependent(self) -> int:
        return sum(len(p.broken_by_hiding) for p in self.pairs)

    @property
    def ok(self) -> bool:
        return not self.errors and not self.dependent


def _candidate_files(pair: Pair, root: Path) -> list[Path]:
    """Ficheros del original que se pueden esconder sin romper el port.

    Solo los que aparecen en su linea de comandos y existen dentro del proyecto.
    Nada de adivinar: si el original carga un modulo que no esta en el comando,
    esta comprobacion no lo vera, y eso se dice en las notas.
    """
    port_tokens = {token.replace("\\", "/") for token in pair.port.command}
    found: list[Path] = []
    for token in pair.original.command:
        if token.startswith("-") or "/" not in token and "." not in token:
            continue
        if token.replace("\\", "/") in port_tokens:
            continue
        raw = Path(token.replace("\\", "/"))
        candidate = raw if raw.is_absolute() else (root / raw)
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_file() and root.resolve() in resolved.parents:
            found.append(resolved)
    return found


def _hide(paths: list[Path]) -> list[tuple[Path, Path]]:
    moved: list[tuple[Path, Path]] = []
    for path in paths:
        target = path.with_name(path.name + HIDDEN_SUFFIX)
        if target.exists():
            target.unlink()
        os.replace(path, target)
        moved.append((path, target))
    return moved


def _restore(moved: list[tuple[Path, Path]]) -> None:
    for original, hidden in moved:
        if hidden.exists():
            os.replace(hidden, original)


def check_pair(project: Project, pair: Pair, sample: int = 20) -> GatePair:
    report = GatePair(pair_id=pair.id)
    try:
        cases = [c for c in corpus_mod.read(project.root / pair.corpus) if c.recorded]
    except corpus_mod.CorpusError as exc:
        report.errors.append(str(exc))
        return report

    if not cases:
        report.errors.append(f"{pair.id}: no hay casos grabados que comprobar")
        return report

    # muestra determinista: los primeros N por id, no al azar
    cases = sorted(cases, key=lambda c: c.id)[: max(1, sample)]
    report.sampled = len(cases)

    def passes(case: corpus_mod.Case) -> bool:
        # se compara contra lo grabado, no contra el original: el original es
        # justo lo que estamos escondiendo
        port = run(pair.port.resolved(), case.input, pair.timeout_ms, pair.port.working_dir(project.root))
        recorded = Observation(case.status or "ok", case.output)
        try:
            return compare(case, recorded, port, pair.normalize, pair.errors) is None
        except CompareError:
            return False

    before = {case.id: passes(case) for case in cases}
    report.passing_before = sum(1 for ok in before.values() if ok)

    files = _candidate_files(pair, project.root)
    report.hidden_files = [str(path.relative_to(project.root)) for path in files]
    if not files:
        # no hay fichero que esconder: el original es un binario o un comando del sistema
        return report

    moved = _hide(files)
    try:
        for case in cases:
            if not before[case.id]:
                continue
            if not passes(case):
                report.broken_by_hiding.append(case.id)
        report.passing_hidden = report.passing_before - len(report.broken_by_hiding)
    finally:
        _restore(moved)

    return report


def check(project: Project, pairs: list[str] | None = None, sample: int = 20) -> GateResult:
    selected = [p for p in project.pairs if pairs is None or p.id in pairs]
    if pairs and not selected:
        raise ValueError(f"ninguna pareja coincide con {pairs}")
    result = GateResult()
    for pair in selected:
        result.pairs.append(check_pair(project, pair, sample))
    return result


def console(result: GateResult) -> str:
    lines: list[str] = []
    for pair in result.pairs:
        if pair.errors:
            for error in pair.errors:
                lines.append(f"fiel: {error}")
            continue
        if not pair.hidden_files:
            lines.append(f"{pair.pair_id}: sin fichero que esconder, no se puede comprobar")
            continue
        if pair.broken_by_hiding:
            lines.append(
                f"{pair.pair_id}: DEPENDIENTE - {len(pair.broken_by_hiding)} de "
                f"{pair.passing_before} casos se rompen al esconder el original"
            )
            lines.append(f"  escondido: {', '.join(pair.hidden_files)}")
            lines.append(f"  casos: {', '.join(pair.broken_by_hiding[:8])}")
        else:
            lines.append(
                f"{pair.pair_id}: independiente - {pair.passing_before} casos siguen "
                f"pasando sin el original"
            )
    return "\n".join(lines)


def as_json(result: GateResult) -> dict:
    return {
        "ok": result.ok,
        "pairs": [
            {
                "id": pair.pair_id,
                "independent": pair.independent,
                "sampled": pair.sampled,
                "passing_before": pair.passing_before,
                "passing_hidden": pair.passing_hidden,
                "broken_by_hiding": pair.broken_by_hiding,
                "hidden_files": pair.hidden_files,
                "errors": pair.errors,
            }
            for pair in result.pairs
        ],
    }


__all__ = [
    "GatePair",
    "GateResult",
    "as_json",
    "check",
    "check_pair",
    "console",
]
