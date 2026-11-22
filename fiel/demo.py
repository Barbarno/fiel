"""fiel demo - la historia completa, en un comando.

Sin red, sin Git, sin dependencias. Copia los ejemplos a un directorio temporal
y los toca para ensenar que pasa. Si el binario de Rust del ejemplo esta
compilado, incluye el caso real; si no, sigue con el ejemplo en Python.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from . import check as check_mod
from . import mutate
from .check import CheckResult
from .report import console
from .spec import load

EXAMPLE = Path(__file__).resolve().parent.parent / "examples"
TRAPS = [b"1_0", b"5 - 9", b"99999999999999999999"]


def _header(text: str) -> None:
    print("")
    print("=" * 64)
    print(text)
    print("=" * 64)


def _tick(pause: bool) -> None:
    if pause and sys.stdin.isatty():
        try:
            input("  [Enter para seguir] ")
        except EOFError:
            pass


def _pairs(result: CheckResult) -> None:
    for pair in result.pairs:
        print(f"  {pair.pair_id}: {pair.passed}/{pair.total} fieles")
        for divergence in pair.divergences:
            print(f"    - {divergence.one_line()}")


def _copy(source: Path, name: str) -> Path:
    target = Path(tempfile.mkdtemp(prefix=f"fiel-demo-{name}-"))
    shutil.copytree(source, target, dirs_exist_ok=True)
    (target / "fiel.baseline.json").unlink(missing_ok=True)
    return target


def demo_python(pause: bool) -> None:
    work = _copy(EXAMPLE / "demo", "py")
    project = load(work)
    try:
        _header("1. Dos ports del mismo original")
        print("  cron-fiel  -> port fiel")
        print("  cron-roto  -> port con una regresion de una linea (rango exclusivo)")
        result = check_mod.check(project)
        _pairs(result)

        _tick(pause)
        _header("2. El baseline permite adoptar la herramienta en un proyecto roto")
        check_mod.write_baseline(
            project.baseline_path(),
            {f"{p.pair_id}:{d.case_id}": d.signature for p in result.pairs for d in p.divergences},
        )
        again = check_mod.check(project)
        known, fresh = check_mod.split_by_baseline(again, check_mod.load_baseline(project.baseline_path()))
        print(f"  conocidas: {len(known)}   nuevas: {len(fresh)}")
        print("  la puerta se abre para lo ya aceptado")

        _tick(pause)
        _header("3. Un cambio nuevo rompe la puerta")
        source = (work / "port_regresion.py").read_text(encoding="utf-8")
        (work / "port_regresion.py").write_text(
            source.replace(
                "return list(range(start, end))",
                "return list(range(start, end)) + [99]",
            ),
            encoding="utf-8",
        )
        third = check_mod.check(project)
        known, fresh = check_mod.split_by_baseline(third, check_mod.load_baseline(project.baseline_path()))
        print(f"  conocidas: {len(known)}   nuevas: {len(fresh)}")
        for divergence in fresh:
            print(f"    - {divergence.one_line()}")
        print("  solo lo nuevo pasa por la puerta")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def demo_rust(pause: bool) -> bool:
    source = EXAMPLE / "rust-demo"
    binary = next(source.glob("rust-port/target/*/release/cron-rs*"), None)
    if binary is None:
        return False

    work = _copy(source, "rs")
    project = load(work)
    try:
        _tick(pause)
        _header("4. Un port de verdad, compilado en Rust")
        result = check_mod.check(project)
        _pairs(result)
        if result.failed:
            print("  el port real no coincide en todos los casos base")

        _tick(pause)
        _header("5. Casos trampa: lo que Python acepta y Rust no")
        pair = project.pairs[0]
        mutate.add_inputs(work / pair.corpus, TRAPS)
        check_mod.record(project, pair)
        after = check_mod.check(project)
        _pairs(after)
        print("")
        print("  Python: int('1_0') = 10     Rust: \"1_0\".parse::<i32>() = Err")
        print("  Python: int('5 - 9')        Rust: \" 9\".parse() = Err")
        print("  Python: enteros sin limite  Rust: i32 = 2 147 483 647")
        print("  tres fallos reales que ningun test escrito a mano detecta")
        return True
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_demo(pause: bool = False) -> int:
    if not (EXAMPLE / "demo").is_dir():
        print(f"no encuentro los ejemplos en {EXAMPLE}")
        return 2
    demo_python(pause)
    rust_ok = demo_rust(pause)
    _tick(pause)
    _header("resumen")
    if rust_ok:
        print("  corpus grabado, port en Rust comprobado, 3 divergencias reales encontradas")
    else:
        print("  el binario de Rust no esta compilado; el ejemplo en Python basta para la demo")
        print("  para incluirlo: cd examples/rust-demo/rust-port && cargo build --release")
    print("")
    return 0
