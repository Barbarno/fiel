"""Salidas: consola, markdown para el PR y anotaciones de GitHub."""

from __future__ import annotations

from .check import CheckResult
from .compare import Divergence

MARKER = "<!-- fiel-report -->"
MAX_SHOWN = 20


def console(result: CheckResult, known: list[Divergence], fresh: list[Divergence], strict: bool) -> str:
    lines: list[str] = []
    for pair in result.pairs:
        status = "OK" if not pair.divergences else f"{pair.failed} divergencias"
        lines.append(f"{pair.pair_id}: {pair.passed}/{pair.total} fieles  [{status}]")
        if pair.drifted:
            lines.append(f"  aviso: {len(pair.drifted)} casos ya no coinciden con el corpus grabado")
            for cid in pair.drifted[:5]:
                lines.append(f"    - {cid}")
        for error in pair.errors:
            lines.append(f"  error: {error}")

    shown = fresh if not strict else [d for p in result.pairs for d in p.divergences]
    if shown:
        lines.append("")
        lines.append(f"Divergencias ({len(shown)}), primeras {min(len(shown), MAX_SHOWN)}:")
        for divergence in shown[:MAX_SHOWN]:
            lines.append(f"  {divergence.one_line()}")
        if len(shown) > MAX_SHOWN:
            lines.append(f"  ... y {len(shown) - MAX_SHOWN} mas")
    if known and not strict:
        lines.append("")
        lines.append(f"{len(known)} divergencias conocidas, aceptadas en el baseline.")
    return "\n".join(lines)


def markdown(result: CheckResult, known: list[Divergence], fresh: list[Divergence], strict: bool) -> str:
    total = result.total
    failed = len(fresh) if not strict else result.failed
    head = "fiel: puerta cerrada" if failed else "fiel: sin divergencias nuevas"

    out: list[str] = [MARKER, f"### {head}", ""]
    out.append("| pareja | fieles | total | divergencias |")
    out.append("|---|---|---|---|")
    for pair in result.pairs:
        out.append(f"| `{pair.pair_id}` | {pair.passed} | {pair.total} | {pair.failed} |")
    out.append("")

    shown = fresh if not strict else [d for p in result.pairs for d in p.divergences]
    if shown:
        out.append("<details open><summary>Divergencias nuevas</summary>")
        out.append("")
        for divergence in shown[:MAX_SHOWN]:
            out.append(f"- **{divergence.case_id}** `{divergence.kind}`")
            out.append(f"  - original: `{divergence.original}`")
            out.append(f"  - port: `{divergence.port}`")
        if len(shown) > MAX_SHOWN:
            out.append(f"- ... y {len(shown) - MAX_SHOWN} mas")
        out.append("")
        out.append("</details>")
        out.append("")

    if known and not strict:
        out.append(f"_{len(known)} divergencias conocidas, aceptadas en el baseline._")
        out.append("")

    if result.drifted:
        out.append(
            f"> Aviso: {result.drifted} casos ya no coinciden con el corpus. "
            "El original cambio y el corpus no: ejecuta `fiel record`."
        )
        out.append("")

    out.append(f"<sub>{total} casos comprobados por fiel</sub>")
    return "\n".join(out)


def github_annotations(result: CheckResult, fresh: list[Divergence]) -> str:
    lines: list[str] = []
    for divergence in fresh:
        message = f"divergencia {divergence.kind}: original={divergence.original} port={divergence.port}"
        message = message.replace("\n", " ").replace("%", "%25").replace("\r", "")
        lines.append(f"::error title=fiel {divergence.case_id}::{message}")
    for pair in result.pairs:
        for error in pair.errors:
            safe = error.replace("\n", " ")
            lines.append(f"::error title=fiel {pair.pair_id}::{safe}")
    return "\n".join(lines)
