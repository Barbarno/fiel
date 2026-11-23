"""Informe HTML en un solo fichero.

Sin plantillas, sin dependencias, sin javascript. Se abre en cualquier navegador
y se puede adjuntar a la memoria tal cual: el CSS va dentro, las imagenes no
existen, y el fichero funciona con el wifi apagado.

El aspecto sigue la escuela de los informes impresos: papel calido, tinta casi
negra, serif para el texto y monoespaciada solo para los datos. El color se
reserva para lo que hay que mirar (verde fiel, rojo divergencia); el resto es
jerarquia tipografica.
"""

from __future__ import annotations

import base64
import html
from datetime import datetime
from pathlib import Path

from . import __version__, corpus as corpus_mod
from .check import CheckResult
from .compare import Divergence
from .spec import Project

STYLE = """
:root {
  --paper: #fbfaf6;
  --ink: #16150f;
  --ink-soft: #4a473c;
  --muted: #7d7768;
  --rule: #ddd8cb;
  --rule-soft: #ece8dd;
  --green: #1f6f43;
  --red: #9d2b25;
  --amber: #8a6416;
  --blue: #1f4f7a;
  --serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, "Times New Roman", serif;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, SFMono-Regular, "Cascadia Mono", Consolas, "Liberation Mono", monospace;
}

@media (prefers-color-scheme: dark) {
  :root {
    --paper: #14140f;
    --ink: #eee9dd;
    --ink-soft: #c3bdae;
    --muted: #8f897a;
    --rule: #33322a;
    --rule-soft: #232219;
    --green: #7cc79b;
    --red: #e88a82;
    --amber: #d9b25f;
    --blue: #8fb8dd;
  }
}

* { box-sizing: border-box; }

html { -webkit-text-size-adjust: 100%; }

body {
  margin: 0;
  padding: 64px 28px 96px;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--serif);
  font-size: 17px;
  line-height: 1.6;
  font-kerning: normal;
  font-variant-ligatures: common-ligatures;
  text-rendering: optimizeLegibility;
}

main { max-width: 1040px; margin: 0 auto; }

/* ---------------------------------------------------------------- cabecera */

.kicker {
  font-family: var(--sans);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--muted);
  margin: 0 0 18px;
}

h1 {
  margin: 0 0 10px;
  font-size: clamp(30px, 4.2vw, 46px);
  font-weight: 400;
  line-height: 1.12;
  letter-spacing: -0.015em;
}

.sub {
  margin: 0;
  font-size: 19px;
  line-height: 1.5;
  color: var(--ink-soft);
  max-width: 62ch;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 26px;
  margin: 26px 0 0;
  padding: 14px 0 0;
  border-top: 1px solid var(--rule);
  font-family: var(--sans);
  font-size: 12.5px;
  color: var(--muted);
}

.meta b { color: var(--ink-soft); font-weight: 600; }

/* ------------------------------------------------------------------ cifras */

.numbers {
  display: flex;
  flex-wrap: wrap;
  margin: 44px 0 52px;
  border-top: 2px solid var(--ink);
  border-bottom: 1px solid var(--rule);
}

.card {
  flex: 1 1 150px;
  padding: 18px 22px 20px;
  border-right: 1px solid var(--rule-soft);
}

.card:first-child { padding-left: 0; }
.card:last-child { border-right: 0; }

.card .n {
  display: block;
  font-family: var(--serif);
  font-size: 40px;
  line-height: 1.05;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums lining-nums;
}

.card .l {
  display: block;
  margin-top: 8px;
  font-family: var(--sans);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
}

.green { color: var(--green); }
.red { color: var(--red); }
.amber { color: var(--amber); }
.blue { color: var(--blue); }

/* ------------------------------------------------------------------ tablas */

h2 {
  font-family: var(--sans);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted);
  margin: 0 0 14px;
}

section { margin-bottom: 56px; }

table { width: 100%; border-collapse: collapse; }

thead th {
  font-family: var(--sans);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
  text-align: left;
  padding: 0 12px 9px;
  border-bottom: 1px solid var(--rule);
  white-space: nowrap;
}

thead th:first-child { padding-left: 0; }
thead th.num { text-align: right; }

tbody td {
  padding: 11px 12px;
  border-bottom: 1px solid var(--rule-soft);
  vertical-align: middle;
  font-size: 15px;
}

tbody td:first-child { padding-left: 0; }
tbody tr:hover td { background: var(--rule-soft); }

td.num {
  text-align: right;
  font-family: var(--mono);
  font-size: 13.5px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

td.state { white-space: nowrap; text-align: right; }

code {
  font-family: var(--mono);
  font-size: 0.88em;
  background: var(--rule-soft);
  padding: 1px 5px;
  border-radius: 3px;
  color: var(--ink-soft);
}

td code { background: none; padding: 0; color: var(--ink); }

.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 10px;
  vertical-align: 1px;
}

.dot.ok { background: var(--green); }
.dot.bad { background: var(--red); }

.bar {
  display: block;
  height: 4px;
  min-width: 84px;
  background: var(--rule-soft);
  overflow: hidden;
}

.bar span { display: block; height: 100%; background: var(--green); }
.bar.bad span { background: var(--red); }

/* ------------------------------------------------------------ divergencias */

.grupo { margin: 0 0 44px; }

.grupo h3 {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin: 0 0 18px;
  padding: 0 0 7px;
  border-bottom: 1px solid var(--rule);
  font-family: var(--sans);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.grupo h3 code {
  background: none;
  padding: 0;
  font-size: 13px;
  letter-spacing: 0;
  color: var(--ink);
}

.grupo h3 .cuenta {
  font-family: var(--sans);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
}

.diff {
  border-left: 2px solid var(--red);
  padding: 2px 0 2px 18px;
  margin: 0 0 26px;
}

.diff.known { border-left-color: var(--amber); }

.diff .head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 4px 14px;
  margin-bottom: 8px;
}

.diff .case {
  font-family: var(--mono);
  font-size: 13px;
  color: var(--ink);
}

.diff .kind {
  font-family: var(--sans);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
}

.diff .kind b { color: var(--red); font-weight: 600; }
.diff .kind b.old { color: var(--amber); font-weight: 600; }

.diff dl {
  margin: 0;
  display: grid;
  grid-template-columns: 82px minmax(0, 1fr);
  gap: 3px 14px;
  align-items: baseline;
}

.diff dt {
  font-family: var(--sans);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
}

.diff dd {
  margin: 0;
  font-family: var(--mono);
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.diff .was { color: var(--green); }
.diff .now { color: var(--red); }

.empty {
  margin: 0;
  font-style: italic;
  color: var(--muted);
}

/* ------------------------------------------------------------------ pie */

footer {
  margin-top: 64px;
  padding-top: 16px;
  border-top: 2px solid var(--ink);
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  justify-content: space-between;
  font-family: var(--sans);
  font-size: 12px;
  color: var(--muted);
}

footer code { background: none; padding: 0; }

/* ------------------------------------------------------------------ varios */

a { color: inherit; }

@media (max-width: 640px) {
  body { padding: 40px 20px 64px; font-size: 16px; }
  .numbers { margin: 32px 0 40px; }
  .card { flex: 1 1 50%; border-right: 0; padding: 14px 0; }
  .card .n { font-size: 32px; }
  .diff dl { grid-template-columns: 1fr; gap: 1px 0; }
  .diff dt { margin-top: 8px; }
}

@media print {
  :root {
    --paper: #fff;
    --ink: #000;
    --ink-soft: #222;
    --muted: #555;
    --rule: #bbb;
    --rule-soft: #e2e2e2;
    --green: #14512f;
    --red: #7d1f1a;
    --amber: #6b4d10;
  }
  body { padding: 0; font-size: 11pt; }
  .numbers { margin: 24pt 0 28pt; }
  section { margin-bottom: 28pt; }
  .diff { break-inside: avoid; }
  tbody tr { break-inside: avoid; }
  thead { display: table-header-group; }
  footer { margin-top: 28pt; }
}
"""

CONTROL_ALLOWED = {0x09, 0x0A, 0x0D}
MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def _fecha(moment: datetime) -> str:
    """Fecha larga en espanol, sin depender del locale del sistema."""
    return f"{moment.day} de {MESES[moment.month - 1]} de {moment.year}, {moment:%H:%M}"


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
        if not pair.divergences:
            continue
        piezas: list[str] = []
        for divergence in pair.divergences:
            payload = inputs.get(pair.pair_id, {}).get(divergence.case_id, b"")
            is_known = (divergence.case_id, divergence.signature) in accepted
            tag = (
                "<b class='old'>aceptada en baseline</b>"
                if is_known
                else f"<b>{html.escape(divergence.kind)}</b>"
            )
            piezas.append(
                f"<div class='diff{' known' if is_known else ''}'>"
                "<div class='head'>"
                f"<span class='case'>{html.escape(divergence.case_id)}</span>"
                f"<span class='kind'>{tag}</span>"
                "</div>"
                "<dl>"
                f"<dt>entrada</dt><dd>{html.escape(_readable(payload))}</dd>"
                f"<dt>original</dt><dd class='was'>{html.escape(divergence.original)}</dd>"
                f"<dt>port</dt><dd class='now'>{html.escape(divergence.port)}</dd>"
                "</dl>"
                "</div>"
            )
        # agrupadas por pareja: 66 bloques seguidos no se leen, en grupos si
        blocks.append(
            "<div class='grupo'>"
            f"<h3><code>{html.escape(pair.pair_id)}</code>"
            f"<span class='cuenta'>{len(pair.divergences)}</span></h3>"
            f"{''.join(piezas)}"
            "</div>"
        )

    if total_div == 0:
        verdict = "<span class='green'>todas las parejas fieles</span>"
    elif total_new:
        verdict = f"<span class='red'>{total_new} divergencias nuevas</span>"
    else:
        verdict = f"<span class='amber'>{total_known} divergencias, todas aceptadas en el baseline</span>"

    moment = datetime.now()
    generated = _fecha(moment)
    empty = '<p class="empty">Ninguna. El port hace lo mismo que el original en todos los casos grabados.</p>'

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{html.escape(title)} - informe</title>
<style>{STYLE}</style>
</head>
<body>
<main>
  <header>
    <p class="kicker">Informe de equivalencia</p>
    <h1>{html.escape(title)}</h1>
    <p class="sub">El mismo programa, dos implementaciones, las mismas entradas.
    Cada caso que no coincide aparece abajo con su entrada exacta.</p>
    <p class="meta">
      <span><b>{len(result.pairs)}</b> parejas</span>
      <span><b>{total_cases}</b> casos grabados</span>
      <span><b>{generated}</b></span>
      <span><code>fiel&nbsp;{__version__}</code></span>
    </p>
  </header>

  <div class="numbers">
    <div class="card"><span class="n">{total_cases}</span><span class="l">casos</span></div>
    <div class="card"><span class="n green">{faithful}</span><span class="l">fieles</span></div>
    <div class="card"><span class="n {'red' if total_new else 'green'}">{total_new}</span><span class="l">nuevas</span></div>
    <div class="card"><span class="n amber">{total_known}</span><span class="l">en baseline</span></div>
    <div class="card"><span class="n">{len(result.pairs)}</span><span class="l">parejas</span></div>
  </div>

  <section>
    <h2>Parejas</h2>
    <table>
      <thead><tr><th>pareja</th><th class="num">fieles</th><th class="num">casos</th><th></th><th class="num">estado</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </section>

  <section>
    <h2>Divergencias ({len(blocks)})</h2>
    {''.join(blocks) if blocks else empty}
  </section>

  <footer>
    <span>{verdict}</span>
    <span>generado el {generated} con <code>fiel check</code></span>
  </footer>
</main>
</body>
</html>
"""


def write(project: Project, result: CheckResult, known: list[Divergence], fresh: list[Divergence], path: Path,
          title: str = "fiel") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(project, result, known, fresh, title=title), encoding="utf-8")
    return path
