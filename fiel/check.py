"""Ejecucion de la comprobacion completa.

Parallel, con timeout por caso, con baseline para no bloquear la adopcion de
una herramienta que llega a un proyecto que ya tenia divergencias.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from . import corpus as corpus_mod
from .compare import CompareError, Divergence, compare, recorded_matches
from .runner import run
from .spec import Pair, Project


@dataclass
class PairResult:
    pair_id: str
    total: int = 0
    passed: int = 0
    divergences: list[Divergence] = field(default_factory=list)
    drifted: list[str] = field(default_factory=list)   # el original ya no coincide con el corpus
    errors: list[str] = field(default_factory=list)

    @property
    def failed(self) -> int:
        return len(self.divergences)


@dataclass
class CheckResult:
    pairs: list[PairResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(p.total for p in self.pairs)

    @property
    def failed(self) -> int:
        return sum(p.failed for p in self.pairs)

    @property
    def drifted(self) -> int:
        return sum(len(p.drifted) for p in self.pairs)

    @property
    def errors(self) -> list[str]:
        return [e for p in self.pairs for e in p.errors]

    @property
    def ok(self) -> bool:
        return self.failed == 0 and not self.errors


def load_baseline(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    cases = raw.get("cases")
    if not isinstance(cases, dict):
        return {}
    return {str(k): str(v) for k, v in cases.items()}


def write_baseline(path: Path, cases: dict[str, str]) -> None:
    payload = {"version": 1, "cases": dict(sorted(cases.items()))}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _run_pair(
    project: Project,
    pair: Pair,
    jobs: int,
    verify_original: bool,
    case_filter: set[str] | None,
) -> PairResult:
    result = PairResult(pair_id=pair.id)
    corpus_path = project.root / pair.corpus
    try:
        cases = corpus_mod.read(corpus_path)
    except corpus_mod.CorpusError as exc:
        result.errors.append(str(exc))
        return result

    if case_filter:
        cases = [c for c in cases if c.id in case_filter]

    def work(case: corpus_mod.Case):
        original = run(
            pair.original.resolved(),
            case.input,
            pair.timeout_ms,
            pair.original.working_dir(project.root),
        )
        port = run(
            pair.port.resolved(),
            case.input,
            pair.timeout_ms,
            pair.port.working_dir(project.root),
        )
        return case, original, port

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        futures = [pool.submit(work, case) for case in cases]

    result.total = len(futures)
    for future in futures:
        try:
            case, original, port = future.result()
        except Exception as exc:  # un caso roto no debe tumbar la suite
            result.errors.append(f"{pair.id}: error interno ({exc})")
            continue

        if verify_original and not recorded_matches(case, original, pair.normalize):
            result.drifted.append(case.id)

        try:
            divergence = compare(case, original, port, pair.normalize, pair.errors)
        except CompareError as exc:
            result.errors.append(f"{pair.id}/{case.id}: {exc}")
            continue

        if divergence is None:
            result.passed += 1
        else:
            result.divergences.append(divergence)

    result.divergences.sort(key=lambda d: d.case_id)
    return result


def check(
    project: Project,
    pairs: list[str] | None = None,
    jobs: int = 4,
    verify_original: bool = True,
    case_filter: set[str] | None = None,
) -> CheckResult:
    selected = [p for p in project.pairs if pairs is None or p.id in pairs]
    if pairs and not selected:
        raise ValueError(f"ninguna pareja coincide con {pairs}")
    out = CheckResult()
    for pair in selected:
        out.pairs.append(_run_pair(project, pair, jobs, verify_original, case_filter))
    return out


def split_by_baseline(result: CheckResult, baseline: dict[str, str]) -> tuple[list[Divergence], list[Divergence]]:
    """Separa divergencias conocidas (estan en el baseline, misma firma) de nuevas."""
    known: list[Divergence] = []
    fresh: list[Divergence] = []
    for pair in result.pairs:
        for divergence in pair.divergences:
            key = f"{pair.pair_id}:{divergence.case_id}"
            if baseline.get(key) == divergence.signature:
                known.append(divergence)
            else:
                fresh.append(divergence)
    return known, fresh


def record(project: Project, pair: Pair, jobs: int = 4) -> tuple[int, int]:
    """Vuelve a grabar las salidas del original. Devuelve (grabados, cambiados)."""
    path = project.root / pair.corpus
    cases = corpus_mod.read(path)
    previous = {c.id: (c.status, c.output) for c in cases if c.recorded}

    def work(case: corpus_mod.Case):
        return case, run(
            pair.original.resolved(),
            case.input,
            pair.timeout_ms,
            pair.original.working_dir(project.root),
        )

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        futures = [pool.submit(work, case) for case in cases]

    updated: list[corpus_mod.Case] = []
    changed = 0
    for future in futures:
        case, obs = future.result()
        old = previous.get(case.id)
        if old is not None and old != (obs.status, obs.output):
            changed += 1
        updated.append(corpus_mod.Case(case.id, case.input, obs.status, obs.output))

    corpus_mod.write(path, updated)
    return len(updated), changed
