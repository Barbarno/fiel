"""Interfaz de linea de comandos de fiel."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from . import adapters
from . import check as check_mod
from . import corpus as corpus_mod
from . import mutate
from .bisect import BisectError, run_bisect
from .bot import BotError, resolve_token, upsert_comment
from .demo import run_demo
from .report import console, github_annotations, markdown
from .report_html import write as write_html
from .spec import SpecError, TEMPLATE, load

EXIT_OK = 0
EXIT_DIVERGENCE = 1
EXIT_ERROR = 2


def _root(args: argparse.Namespace) -> Path:
    return Path(args.root).resolve()


def cmd_init(args: argparse.Namespace) -> int:
    root = _root(args)
    root.mkdir(parents=True, exist_ok=True)
    spec_path = root / "fiel.toml"
    if spec_path.exists() and not args.force:
        print(f"ya existe {spec_path} (usa --force para sobrescribirlo)", file=sys.stderr)
        return EXIT_ERROR
    spec_path.write_text(TEMPLATE, encoding="utf-8")
    (root / "corpus").mkdir(exist_ok=True)
    print(f"escrito {spec_path}")
    print("siguiente: llena 'corpus/' con entradas y ejecuta 'fiel record'")
    return EXIT_OK


def cmd_record(args: argparse.Namespace) -> int:
    project = load(_root(args), args.spec)
    selected = [p for p in project.pairs if args.pair is None or p.id in args.pair]
    if not selected:
        print("ninguna pareja coincide", file=sys.stderr)
        return EXIT_ERROR
    for pair in selected:
        total, changed = check_mod.record(project, pair, jobs=args.jobs)
        note = f", {changed} salidas cambiaron" if changed else ""
        print(f"{pair.id}: {total} casos grabados{note}")
    return EXIT_OK


def cmd_check(args: argparse.Namespace) -> int:
    try:
        project = load(_root(args), args.spec)
    except SpecError as exc:
        print(f"fiel: {exc}", file=sys.stderr)
        return EXIT_ERROR

    try:
        result = check_mod.check(
            project,
            pairs=args.pair,
            jobs=args.jobs,
            verify_original=not args.no_verify_original,
            case_filter=set(args.case) if args.case else None,
        )
    except (ValueError, corpus_mod.CorpusError) as exc:
        print(f"fiel: {exc}", file=sys.stderr)
        return EXIT_ERROR

    baseline = {} if args.no_baseline else check_mod.load_baseline(project.baseline_path())
    known, fresh = check_mod.split_by_baseline(result, baseline)

    if args.format == "markdown":
        print(markdown(result, known, fresh, strict=args.strict))
    elif args.format == "github":
        text = github_annotations(result, fresh if not args.strict else [d for p in result.pairs for d in p.divergences])
        if text:
            print(text)
        if not args.quiet:
            print(console(result, known, fresh, strict=args.strict), file=sys.stderr)
    elif args.format == "json":
        print(json.dumps(_as_json(result, known, fresh, args.strict), indent=2, ensure_ascii=False))
    elif not args.quiet:
        print(console(result, known, fresh, strict=args.strict))

    if result.errors:
        return EXIT_ERROR
    failing = result.failed if args.strict else len(fresh)
    return EXIT_DIVERGENCE if failing else EXIT_OK


def _as_json(result, known, fresh, strict: bool) -> dict:
    return {
        "ok": result.ok and not fresh,
        "total": result.total,
        "failed": result.failed,
        "known": len(known),
        "fresh": len(fresh),
        "drifted": result.drifted,
        "pairs": [
            {
                "id": pair.pair_id,
                "passed": pair.passed,
                "total": pair.total,
                "divergences": [
                    {
                        "case": d.case_id,
                        "kind": d.kind,
                        "original": d.original,
                        "port": d.port,
                        "known": d in known,
                    }
                    for d in pair.divergences
                ],
                "errors": pair.errors,
            }
            for pair in result.pairs
        ],
    }


def cmd_baseline(args: argparse.Namespace) -> int:
    project = load(_root(args), args.spec)
    result = check_mod.check(project, pairs=args.pair, jobs=args.jobs)
    if result.errors:
        for error in result.errors:
            print(f"fiel: {error}", file=sys.stderr)
        return EXIT_ERROR

    cases: dict[str, str] = {}
    if args.prune:
        previous = check_mod.load_baseline(project.baseline_path())
        current = {f"{p.pair_id}:{d.case_id}": d.signature for p in result.pairs for d in p.divergences}
        for key in previous:
            if key in current:
                cases[key] = previous[key]
    for pair in result.pairs:
        for divergence in pair.divergences:
            cases[f"{pair.pair_id}:{divergence.case_id}"] = divergence.signature

    check_mod.write_baseline(project.baseline_path(), cases)
    print(f"{len(cases)} divergencias aceptadas en {project.baseline}")
    return EXIT_OK


def cmd_bisect(args: argparse.Namespace) -> int:
    root = _root(args)
    try:
        steps = run_bisect(root, args.since, args.until, args.pair, args.timeout)
    except BisectError as exc:
        print(f"fiel: {exc}", file=sys.stderr)
        return EXIT_ERROR

    for step in steps:
        mark = "ok  " if step.ok else "FALLA"
        print(f"{mark} {step.commit[:8]}  {step.subject}")
    bad = [s for s in steps if not s.ok]
    if not bad:
        print("")
        print(f"sin divergencias en {len(steps)} commits")
        return EXIT_OK
    first = bad[0]
    print("")
    print(f"primera rotura: {first.commit}")
    print(f"  {first.subject}")
    print(f"  {first.detail}")
    return EXIT_DIVERGENCE


def cmd_add(args: argparse.Namespace) -> int:
    project = load(_root(args), args.spec)
    selected = [p for p in project.pairs if args.pair is None or p.id in args.pair]
    if len(selected) != 1:
        print("fiel add necesita exactamente una pareja (--pair)", file=sys.stderr)
        return EXIT_ERROR
    pair = selected[0]
    path = _root(args) / pair.corpus

    payloads: list[bytes] = []
    if args.file:
        source = Path(args.file)
        if not source.is_file():
            print(f"fiel: no encuentro {source}", file=sys.stderr)
            return EXIT_ERROR
        payloads.extend(mutate.read_input_file(source))
    for raw in args.input or []:
        payloads.append(raw.encode("utf-8"))
    if not payloads:
        print("fiel: nada que anadir (usa --input o --file)", file=sys.stderr)
        return EXIT_ERROR

    added = mutate.add_inputs(path, payloads)
    print(f"{pair.id}: {len(added)} casos anadidos ({added[0]}..{added[-1]})")
    total, changed = check_mod.record(project, pair, jobs=args.jobs)
    print(f"{pair.id}: {total} casos grabados")
    del changed
    return EXIT_OK


def cmd_import(args: argparse.Namespace) -> int:
    source = Path(args.file)
    try:
        rows, report = adapters.read_foreign(source)
    except adapters.ImportError_ as exc:
        print(f"fiel: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if not rows:
        print("fiel: el fichero no tenia casos utilizables", file=sys.stderr)
        for reason in report.reasons[:5]:
            print(f"  {reason}", file=sys.stderr)
        return EXIT_ERROR

    converted = adapters.to_fiel(rows)
    target = Path(args.output)
    if not target.is_absolute():
        target = _root(args) / target
    added = adapters.write_corpus(converted, target, append=args.append)

    recorded = sum(1 for row in converted if row.get("status"))
    print(f"{len(converted)} casos leidos, {added} anadidos a {target}")
    print(f"{recorded} traian salida grabada, {len(converted) - recorded} necesitan 'fiel record'")
    if report.skipped:
        print(f"{report.skipped} lineas descartadas:")
        for reason in report.reasons[:5]:
            print(f"  {reason}")
    return EXIT_OK


def cmd_comment(args: argparse.Namespace) -> int:
    try:
        token = resolve_token(args.token)
        text = _build_markdown(args)
        outcome = upsert_comment(args.repo, args.pr, text, token, dry_run=args.dry_run)
    except (BotError, SpecError) as exc:
        print(f"fiel: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if args.dry_run:
        print(text)
        print("")
    print(outcome)
    return EXIT_OK


def _build_markdown(args: argparse.Namespace) -> str:
    project = load(_root(args), args.spec)
    result = check_mod.check(project, pairs=args.pair, jobs=args.jobs)
    baseline = check_mod.load_baseline(project.baseline_path())
    known, fresh = check_mod.split_by_baseline(result, baseline)
    return markdown(result, known, fresh, strict=args.strict)


def cmd_demo(args: argparse.Namespace) -> int:
    return run_demo(getattr(args, "pause", False))


def cmd_report(args: argparse.Namespace) -> int:
    project = load(_root(args), args.spec)
    try:
        result = check_mod.check(project, pairs=args.pair, jobs=args.jobs)
    except (ValueError, corpus_mod.CorpusError) as exc:
        print(f"fiel: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if result.errors:
        for error in result.errors:
            print(f"fiel: {error}", file=sys.stderr)
        return EXIT_ERROR

    baseline = {} if args.no_baseline else check_mod.load_baseline(project.baseline_path())
    known, fresh = check_mod.split_by_baseline(result, baseline)

    target = Path(args.out)
    if not target.is_absolute():
        target = _root(args) / target
    write_html(project, result, known, fresh, target, title=args.title)

    print(f"informe escrito en {target}")
    print(f"{result.total} casos, {result.failed} divergencias ({len(fresh)} nuevas)")

    if args.open:
        import webbrowser

        webbrowser.open(target.resolve().as_uri())
    return EXIT_DIVERGENCE if fresh else EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fiel", description="mantiene un port fiel a su original")
    parser.add_argument("--version", action="version", version=f"fiel {__version__}")
    parser.add_argument("--root", default=".", help="raiz del proyecto (por defecto: .)")
    parser.add_argument("--spec", default="fiel.toml", help="fichero de especificacion (por defecto: fiel.toml)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="crea fiel.toml")
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--pair", action="append", help="solo esta pareja (repetible)")
        p.add_argument("--jobs", type=int, default=4, help="casos en paralelo")

    p_record = sub.add_parser("record", help="graba lo que hace el original")
    add_common(p_record)
    p_record.set_defaults(func=cmd_record)

    p_check = sub.add_parser("check", help="comprueba el port contra el corpus")
    add_common(p_check)
    p_check.add_argument("--case", action="append", help="solo este caso (repetible)")
    p_check.add_argument("--strict", action="store_true", help="ignora el baseline")
    p_check.add_argument("--no-baseline", action="store_true")
    p_check.add_argument("--no-verify-original", action="store_true", help="no avisar de corpus anticuado")
    p_check.add_argument("--format", choices=["console", "markdown", "github", "json"], default="console")
    p_check.add_argument("--quiet", action="store_true")
    p_check.set_defaults(func=cmd_check)

    p_base = sub.add_parser("baseline", help="acepta las divergencias actuales")
    add_common(p_base)
    p_base.add_argument("--prune", action="store_true", help="arrastra solo las que siguen existiendo")
    p_base.set_defaults(func=cmd_baseline)

    p_bisect = sub.add_parser("bisect", help="encuentra el commit que rompio la fidelidad")
    p_bisect.add_argument("--since", required=True, help="commit o ref de partida")
    p_bisect.add_argument("--until", default="HEAD")
    p_bisect.add_argument("--pair", action="append")
    p_bisect.add_argument("--timeout", type=int, default=300, help="segundos por commit")
    p_bisect.set_defaults(func=cmd_bisect)

    p_add = sub.add_parser("add", help="anade casos nuevos al corpus")
    p_add.add_argument("--pair", action="append", required=True)
    p_add.add_argument("--input", action="append", help="una entrada nueva (repetible)")
    p_add.add_argument("--file", help="fichero con una entrada por linea")
    p_add.add_argument("--jobs", type=int, default=4)
    p_add.set_defaults(func=cmd_add)

    p_import = sub.add_parser("import", help="trae un corpus de otra herramienta")
    p_import.add_argument("--file", required=True, help="JSONL de origen")
    p_import.add_argument("--output", required=True, help="corpus de destino")
    p_import.add_argument("--append", action="store_true", help="conservar el corpus destino")
    p_import.set_defaults(func=cmd_import)

    p_comment = sub.add_parser("comment", help="publica el informe en un pull request")
    p_comment.add_argument("--repo", required=True, help="propietario/repositorio")
    p_comment.add_argument("--pr", type=int, required=True)
    p_comment.add_argument("--token", help="token de GitHub (por defecto GH_TOKEN)")
    p_comment.add_argument("--dry-run", action="store_true")
    add_common(p_comment)
    p_comment.add_argument("--strict", action="store_true")
    p_comment.set_defaults(func=cmd_comment)

    p_demo = sub.add_parser("demo", help="la historia completa, en un comando")
    p_demo.add_argument("--pause", action="store_true", help="espera Enter entre actos (para presentar en directo)")
    p_demo.set_defaults(func=cmd_demo)

    p_report = sub.add_parser("report", help="escribe un informe HTML con los resultados")
    p_report.add_argument("--out", default="informe.html", help="fichero de salida (por defecto: informe.html)")
    p_report.add_argument("--title", default="fiel", help="titulo del informe")
    p_report.add_argument("--open", action="store_true", help="abrir el informe al terminar")
    p_report.add_argument("--no-baseline", action="store_true")
    add_common(p_report)
    p_report.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except SpecError as exc:
        print(f"fiel: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except corpus_mod.CorpusError as exc:
        print(f"fiel: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except KeyboardInterrupt:
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
