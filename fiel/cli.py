"""Interfaz de linea de comandos de fiel."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from . import adapters
from . import adequacy as adequacy_mod
from . import badge as badge_mod
from . import check as check_mod
from . import ci as ci_mod
from . import corpus as corpus_mod
from . import coverage as coverage_mod
from . import gate as gate_mod
from . import mutate
from . import probe as probe_mod
from . import shrink as shrink_mod
from .bisect import BisectError, run_bisect
from .bot import BotError, resolve_token, upsert_comment
from .demo import run_demo
from .doctor import cmd_doctor
from .guard import cmd_guard
from .report import console, github_annotations, junit, markdown
from .report_html import write as write_html
from .spec import SpecError, TEMPLATE, load
from .watch import cmd_watch

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
    elif args.format == "junit":
        print(junit(result, known, fresh, strict=args.strict))
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


def cmd_badge(args: argparse.Namespace) -> int:
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
            verify_original=not getattr(args, "no_verify_original", False),
            case_filter=None,
        )
    except (ValueError, corpus_mod.CorpusError) as exc:
        print(f"fiel: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if result.errors:
        for error in result.errors:
            print(f"fiel: {error}", file=sys.stderr)
        return EXIT_ERROR
    destino = Path(args.out)
    chapa = badge_mod.escribir(destino, result)
    print(f"chapa escrita en {destino.resolve()}")
    print(f"  {chapa.etiqueta} {chapa.valor}  ({chapa.fieles} de {chapa.total} casos)")
    return EXIT_OK if chapa.fieles == chapa.total else EXIT_DIVERGENCE


def cmd_ci(args: argparse.Namespace) -> int:
    root = _root(args)
    destino = Path(args.out)
    try:
        if args.remove:
            resultado = ci_mod.quitar(root, destino)
            verbo = "quitado" if not resultado.existe else "no estaba"
            print(f"fiel ci: {verbo} en {resultado.ruta}")
            return EXIT_OK
        if not args.install:
            print(ci_mod.console(ci_mod.estado(root, destino), root))
            return EXIT_OK
        project = load(root, args.spec)
        resultado = ci_mod.escribir(
            project,
            destino=destino,
            parejas=tuple(args.pair or ()),
            spec=args.spec or "fiel.toml",
            force=args.force,
            install=args.pip,
        )
        print(ci_mod.console(resultado, project.root))
        print("")
        print("desde ahora, cada push a main y cada pull request ejecuta la comprobacion.")
        return EXIT_OK
    except (SpecError, ci_mod.CiError) as exc:
        print(f"fiel ci: {exc}", file=sys.stderr)
        return EXIT_ERROR


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


def cmd_adequacy(args: argparse.Namespace) -> int:
    project = load(_root(args), args.spec)
    try:
        result = adequacy_mod.measure(project, pairs=args.pair, budget=args.budget)
    except (ValueError, corpus_mod.CorpusError) as exc:
        print(f"fiel: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.format == "json":
        print(json.dumps(adequacy_mod.as_json(result), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(adequacy_mod.markdown(result))
    else:
        print(adequacy_mod.console(result))

    if result.errors:
        return EXIT_ERROR
    if args.write_unverified:
        target = _root(args) / args.write_unverified
        added = adequacy_mod.write_unverified(result, target)
        print(f"{added} sondas anadidas a {target}")
        print("siguiente: 'fiel record' para grabarlas")
    if args.fail_on_unverified and result.divergences:
        return EXIT_DIVERGENCE
    return EXIT_OK


def cmd_gate(args: argparse.Namespace) -> int:
    project = load(_root(args), args.spec)
    try:
        result = gate_mod.check(project, pairs=args.pair, sample=args.sample)
    except ValueError as exc:
        print(f"fiel: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.format == "json":
        print(json.dumps(gate_mod.as_json(result), indent=2, ensure_ascii=False))
    else:
        print(gate_mod.console(result))

    if result.errors:
        return EXIT_ERROR
    return EXIT_DIVERGENCE if result.dependent else EXIT_OK


def cmd_coverage(args: argparse.Namespace) -> int:
    project = load(_root(args), args.spec)
    try:
        result = coverage_mod.medir(project, pairs=args.pair)
    except ValueError as exc:
        print(f"fiel: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.format == "json":
        print(json.dumps(coverage_mod.as_json(result), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(coverage_mod.markdown(result))
    else:
        print(coverage_mod.console(result))

    if result.errors:
        return EXIT_ERROR
    if args.min and result.porcentaje < args.min:
        print(
            f"fiel: el corpus solo ejecuta el {result.porcentaje:.1f}% del original "
            f"(minimo pedido: {args.min:g}%)",
            file=sys.stderr,
        )
        return EXIT_DIVERGENCE
    return EXIT_OK


def cmd_shrink(args: argparse.Namespace) -> int:
    project = load(_root(args), args.spec)
    try:
        resultados = shrink_mod.shrink_casos(
            project,
            pairs=args.pair,
            casos=args.case,
            presupuesto=args.budget,
            cualquier=args.any,
            todos=args.all,
        )
    except (ValueError, shrink_mod.ShrinkError, corpus_mod.CorpusError) as exc:
        print(f"fiel: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if not resultados:
        print("nada que reducir: no hay divergencias en lo seleccionado")
        return EXIT_OK

    if args.format == "json":
        print(json.dumps(shrink_mod.as_json(resultados), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(shrink_mod.markdown(resultados))
    else:
        por_id = {pair.id: pair for pair in project.pairs}
        for resultado in resultados:
            print(shrink_mod.console(resultado, por_id[resultado.pair_id]))
            print("")

    if args.write:
        por_id = {pair.id: pair for pair in project.pairs}
        for resultado in resultados:
            pair = por_id[resultado.pair_id]
            try:
                nuevo = shrink_mod.escribir_caso(project, pair, resultado)
            except (shrink_mod.ShrinkError, corpus_mod.CorpusError) as exc:
                print(f"fiel: {exc}", file=sys.stderr)
                return EXIT_ERROR
            print(f"{nuevo} anadido a {pair.corpus} (siguiente: 'fiel check')")

    return EXIT_OK


def cmd_probe(args: argparse.Namespace) -> int:
    project = load(_root(args), args.spec)
    if not args.pair:
        print("fiel: indica la pareja con --pair", file=sys.stderr)
        return EXIT_ERROR
    if len(args.pair) > 1:
        print("fiel: probe trabaja sobre una sola pareja", file=sys.stderr)
        return EXIT_ERROR

    entradas: list[bytes] = []
    if args.stdin:
        entradas.append(sys.stdin.buffer.read())
    for texto in args.input or []:
        try:
            entradas.append(probe_mod.leer_entrada(texto))
        except probe_mod.ProbeError as exc:
            print(f"fiel: {exc}", file=sys.stderr)
            return EXIT_ERROR
    if not entradas:
        print("fiel: indica --input o --stdin", file=sys.stderr)
        return EXIT_ERROR

    try:
        pair = probe_mod.obtener(project, args.pair[0])
        resultados = [probe_mod.una(pair, project, entrada) for entrada in entradas]
    except probe_mod.ProbeError as exc:
        print(f"fiel: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.format == "json":
        print(json.dumps([probe_mod.as_json(r) for r in resultados], indent=2, ensure_ascii=False))
    else:
        for resultado in resultados:
            print(probe_mod.console(resultado, diff=args.diff))
            print("")

    return EXIT_OK if all(r.fiel for r in resultados) else EXIT_DIVERGENCE


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
    p_check.add_argument(
        "--format",
        choices=["console", "markdown", "github", "json", "junit"],
        default="console",
    )
    p_check.add_argument("--quiet", action="store_true")
    p_check.set_defaults(func=cmd_check)

    p_badge = sub.add_parser("badge", help="escribe una chapa SVG con el resultado, para el README")
    add_common(p_badge)
    p_badge.add_argument("--out", default="fiel.svg", help="fichero SVG de salida")
    p_badge.set_defaults(func=cmd_badge)

    p_ci = sub.add_parser("ci", help="escribe el workflow de GitHub Actions de la comprobacion")
    p_ci.add_argument("--install", action="store_true", help="escribe el workflow")
    p_ci.add_argument("--remove", action="store_true", help="quita el workflow que escribio fiel")
    p_ci.add_argument("--out", default=str(ci_mod.RUTA_POR_DEFECTO), help="ruta del workflow")
    p_ci.add_argument(
        "--pair",
        action="append",
        metavar="ID",
        help="vigila solo esta pareja (repetible); por defecto, todas",
    )
    p_ci.add_argument("--force", action="store_true", help="sustituye un workflow que no escribio fiel")
    p_ci.add_argument(
        "--pip",
        default='pip install "fiel @ git+https://github.com/Barbarno/fiel"',
        help="orden con la que el workflow instala fiel",
    )
    p_ci.set_defaults(func=cmd_ci)

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

    p_adeq = sub.add_parser("adequacy", help="mide cuanto deja sin comprobar el corpus")
    add_common(p_adeq)
    p_adeq.add_argument("--budget", type=int, default=400, help="sondas por pareja (por defecto: 400)")
    p_adeq.add_argument("--format", choices=["console", "markdown", "json"], default="console")
    p_adeq.add_argument("--write-unverified", help="anade las sondas sin verificar a este corpus de semillas")
    p_adeq.add_argument("--fail-on-unverified", action="store_true", help="exit 1 si hay divergencias fuera del corpus")
    p_adeq.set_defaults(func=cmd_adequacy)

    p_gate = sub.add_parser("gate", help="comprueba que el port no llama al original")
    add_common(p_gate)
    p_gate.add_argument("--sample", type=int, default=20, help="casos a comprobar (por defecto: 20)")
    p_gate.add_argument("--format", choices=["console", "json"], default="console")
    p_gate.set_defaults(func=cmd_gate)

    p_doctor = sub.add_parser("doctor", help="revisa que el entorno este listo para comprobar")
    add_common(p_doctor)
    p_doctor.add_argument("--smoke", action="store_true", help="ademas ejecuta el primer caso de cada pareja")
    p_doctor.set_defaults(func=cmd_doctor)

    p_watch = sub.add_parser("watch", help="repite la comprobacion cuando cambia un fichero")
    add_common(p_watch)
    p_watch.add_argument("--interval", type=float, default=1.0, help="segundos entre revisiones (por defecto: 1)")
    p_watch.add_argument("--path", action="append", help="fichero o carpeta adicional que vigilar (repetible)")
    p_watch.add_argument("--vueltas", type=int, default=None, help=argparse.SUPPRESS)
    p_watch.add_argument("--quiet", action="store_true", help="no imprime el resultado de cada vuelta")
    p_watch.set_defaults(func=cmd_watch)

    p_cov = sub.add_parser("coverage", help="mide cuantas lineas del original ejecuta el corpus")
    add_common(p_cov)
    p_cov.add_argument("--min", type=float, default=0.0, help="exit 1 si el corpus no llega a este porcentaje")
    p_cov.add_argument("--format", choices=["console", "markdown", "json"], default="console")
    p_cov.set_defaults(func=cmd_coverage)

    p_shr = sub.add_parser("shrink", help="reduce un caso que diverge al minimo que sigue divergiendo")
    add_common(p_shr)
    p_shr.add_argument("--case", action="append", help="caso a reducir (repetible)")
    p_shr.add_argument("--all", action="store_true", help="reduce todas las divergencias de la pareja")
    p_shr.add_argument("--budget", type=int, default=shrink_mod.PRESUPUESTO, help="ejecuciones por caso")
    p_shr.add_argument("--any", action="store_true", help="vale cualquier divergencia, no solo la misma")
    p_shr.add_argument("--write", action="store_true", help="anade la entrada minima al corpus")
    p_shr.add_argument("--format", choices=["console", "markdown", "json"], default="console")
    p_shr.set_defaults(func=cmd_shrink)

    p_prb = sub.add_parser("probe", help="prueba una entrada suelta contra una pareja")
    add_common(p_prb)
    p_prb.add_argument("--input", action="append", help="entrada a probar; @fichero para leerla de disco (repetible)")
    p_prb.add_argument("--stdin", action="store_true", help="lee la entrada de la entrada estandar")
    p_prb.add_argument("--diff", action="store_true", help="muestra las dos salidas como diff unificado")
    p_prb.add_argument("--format", choices=["console", "json"], default="console")
    p_prb.set_defaults(func=cmd_probe)

    p_grd = sub.add_parser("guard", help="instala fiel como hook de git (pre-commit)")
    p_grd.add_argument("--install", action="store_true", help="escribe el hook")
    p_grd.add_argument("--remove", action="store_true", help="quita el hook que escribio fiel")
    p_grd.add_argument(
        "--pair",
        action="append",
        metavar="ID",
        help="solo vigila esta pareja (repetible); por defecto, todas",
    )
    p_grd.add_argument("--hook", default="pre-commit", help="hook a usar (por defecto: pre-commit)")
    p_grd.add_argument("--python", default="python", help="interprete que ejecutara el hook")
    p_grd.add_argument("--force", action="store_true", help="sustituye un hook que no escribio fiel")
    p_grd.set_defaults(func=cmd_guard)

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
