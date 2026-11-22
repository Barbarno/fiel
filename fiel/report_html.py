"""Informe HTML en un solo fichero.

Sin plantillas, sin dependencias, sin javascript. Se abre en cualquier navegador
y se puede adjuntar a la memoria tal cual: el CSS va dentro, las imagenes no
existen, y el fichero funciona con el wifi apagado.
"""

from __future__ import annotations

import base64
import html
from datetime import datetime
from pathlib import Path

from . import corpus as corpus_mod
from .check import CheckResult
from .compare import Divergence
from .spec import Project

STYLE = """
:root {
  --bg: #0d1117; --panel: #161b22; --panel2: #1c2128; --border: #30363d;
  --text: #c9d1d9; --muted: #8b949e; --green: #3fb950; --red: #f85149;
  --amber: #d29922; --blue: #58a6ff;
  --mono: ui-monospace, SFMono-Regular, "Cascadia Mono", Consolas, monospace;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 40px 24px; background: var(--bg); color: var(--text);
  font-family: var(--mono); font-size: 14px; line-height: 1.55;
}
main { max-width: 1000px; margin: 0 auto; }
h1 { margin: 0 0 6px; font-size: 26px; font-weight: 600; letter-spacing: -0.4px; }
.sub { color: var(--muted); margin: 0 0 32px; }
.numbers { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 32px; }
.card {
  background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
  padding: 14px 18px; min-width: 132px; flex: 0 1 auto;
}
.card .n { font-size: 26px; font-weight: 600; display: block; line-height: 1.2; }
.card .l { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.6px; }
.green { color: var(--green); } .red { color: var(--red); }
.amber { color: var(--amber); } .blue { color: var(--blue); }
table { width: 100%; border-collapse: collapse; margin-bottom: 34px; }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }
th { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.6px; font-weight: 500; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
td.state { white-space: nowrap; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 8px; }
.dot.ok { background: var(--green); } .dot.bad { background: var(--red); }
.bar { display: block; height: 6px; border-radius: 3px; background: #21262d; overflow: hidden; min-width: 90px; }
.bar span { display: block; height: 100%; background: var(--green); }
.bar.bad span { background: var(--red); }
h2 { font-size: 15px; font-weight: 600; margin: 0 0 12px; color: var(--muted);
     text-transform: uppercase; letter-spacing: 0.8px; }
.diff { background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
        padding: 14px 16px; margin-bottom: 10px; }
.diff.known { border-style: dashed; }
.diff .head { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }
.diff .case { color: var(--amber); }
.diff .kind { color: var(--muted); font-size: 12px; }
.diff .kind b { color: var(--red); font-weight: 500; }
.diff .kind b.old { color: var(--muted); font-weight: 500; }
.diff dl { margin: 0; display: grid; grid-template-columns: 92px 1fr; gap: 5px 12px; }
.diff dt { color: var(--muted); font-size: 12px; padding-top: 1px; }
.diff dd { margin: 0; word-break: break-all; white-space: pre-wrap; }
.diff .was { color: var(--green); } .diff .now { color: var(--red); }
.empty { color: var(--muted); font-style: italic; }
footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--border);
         color: var(--muted); font-size: 12px; }
code { background: #21262d; padding: 1px 5px; border-radius: 4px; }
"""

CONTROL_ALLOWED = {0x09, 0x0A, 0x0D}


def _readable(payload: bytes, limit: int = 160) -> str:
    """Entrada tal como se lee en el corpus, o base64 si no es texto."""
    if not payload:
        return "(vacio)"
    if any(byte < 0x20 and byte not in CONTROL_ALLOWED for byte in payload):
        return base64.b64encode(payload).decode("ascii")[:limit] + " (base64)"
    text = payload.decode("utf-8", "replace")
    text = text.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    return text[:limit] + "..." if len(text) > limit else text


def _inputs_by_pair(project: Project) -> dict[str, dict[str, bytes]]:
    table: dict[str, dict[str, bytes]] = {}
    for pair in project.pairs:
        try:
            cases = corpus_mod.read(project.root / pair.corpus)
        except corpus_mod.CorpusError:
            continue
        table[pair.id] = {case.id: case.input for case in cases}
    return table


def render(
    project: Project,
    result: CheckResult,
    known: list[Divergence] | None = None,
    fresh: list[Divergence] | None = None,
    title: str = "fiel",
) -> str:
    known = known or []
    del fresh  # el render muestra las dos clases, no solo las nuevas
    accepted = {(d.case_id, d.signature) for d in known}
    inputs = _inputs_by_pair(project)

    total_cases = sum(p.total for p in result.pairs)
    total_div = sum(p.failed for p in result.pairs)
    faithful = total_cases - total_div
    total_known = sum(1 for p in result.pairs for d in p.divergences if (d.case_id, d.signature) in accepted)
    total_new = total_div - total_known

    rows: list[str] = []
    for pair in result.pairs:
        ok = pair.passed
        total = pair.total
        pct = 100.0 if total == 0 else ok * 100.0 / total
        state = "ok" if not pair.divergences else "bad"
        label = "fiel" if not pair.divergences else f"{pair.failed} divergencias"
        color = "green" if not pair.divergences else "red"
        rows.append(
            "<tr>"
            f"<td><span class='dot {state}'></span><code>{html.escape(pair.pair_id)}</code></td>"
            f"<td class='num'>{ok}</td>"
            f"<td class='num'>{total}</td>"
            f"<td><span class='bar {'' if not pair.divergences else 'bad'}'>"
            f"<span style='width:{pct:.1f}%'></span></span></td>"
            f"<td class='num {color} state'>{label}</td>"
            "</tr>"
        )

    blocks: list[str] = []
    for pair in result.pairs:
        for divergence in pair.divergences:
            payload = inputs.get(pair.pair_id, {}).get(divergence.case_id, b"")
            is_known = (divergence.case_id, divergence.signature) in accepted
            tag = (
                "<b class='old'>aceptada en baseline</b>"
                if is_known
                else f"<b>{html.escape(divergence.kind)}</b>"
            )
            blocks.append(
                f"<div class='diff{' known' if is_known else ''}'>"
                "<div class='head'>"
                f"<span class='case'>{html.escape(pair.pair_id)} / {html.escape(divergence.case_id)}</span>"
                f"<span class='kind'>{tag}</span>"
                "</div>"
                "<dl>"
                f"<dt>entrada</dt><dd>{html.escape(_readable(payload))}</dd>"
                f"<dt>original</dt><dd class='was'>{html.escape(divergence.original)}</dd>"
                f"<dt>port</dt><dd class='now'>{html.escape(divergence.port)}</dd>"
                "</dl>"
                "</div>"
            )

    if total_div == 0:
        verdict = "<span class='green'>todas las parejas fieles</span>"
    elif total_new:
        verdict = f"<span class='red'>{total_new} divergencias nuevas</span>"
    else:
        verdict = f"<span class='amber'>{total_known} divergencias, todas aceptadas en el baseline</span>"

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    empty = '<p class="empty">Ninguna. El port hace lo mismo que el original en todos los casos grabados.</p>'

    return f"""<!doctype html>
<html lang="es">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} - informe</title>
<style>{STYLE}</style>
<main>
  <h1>{html.escape(title)}</h1>
  <p class="sub">Equivalencia entre un original y su port, comprobada caso por caso.</p>

  <div class="numbers">
    <div class="card"><span class="n">{total_cases}</span><span class="l">casos</span></div>
    <div class="card"><span class="n green">{faithful}</span><span class="l">fieles</span></div>
    <div class="card"><span class="n {'red' if total_new else 'green'}">{total_new}</span><span class="l">nuevas</span></div>
    <div class="card"><span class="n amber">{total_known}</span><span class="l">en baseline</span></div>
    <div class="card"><span class="n">{len(result.pairs)}</span><span class="l">parejas</span></div>
  </div>

  <h2>Parejas</h2>
  <table>
    <thead><tr><th>pareja</th><th class="num">fieles</th><th class="num">casos</th><th></th><th class="num">estado</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>

  <h2>Divergencias ({len(blocks)})</h2>
  {''.join(blocks) if blocks else empty}

  <footer>
    {verdict} &middot; generado el {generated} &middot; <code>fiel check</code>
  </footer>
</main>
</html>
"""


def write(project: Project, result: CheckResult, known: list[Divergence], fresh: list[Divergence], path: Path,
          title: str = "fiel") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(project, result, known, fresh, title=title), encoding="utf-8")
    return path
