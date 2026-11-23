"""Busca las entradas donde cada reescritura a mano deja de coincidir.

Los seis ports de este banco pasan su corpus normal: seis entradas corrientes
cada uno. Eso es exactamente lo que hace cualquiera antes de dar una
reescritura por buena. Este script ejecuta las dos versiones sobre las entradas
raras de `casos.py` y muestra solo las que divergen.

    python estudio/portes/probe.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from casos import NORMAL, TRAMPAS

ROOT = Path(__file__).resolve().parent


def run(folder: Path, script: str, case: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(folder / script)],
        input=case.encode("utf-8"),
        capture_output=True,
        timeout=30,
    )
    out = (result.stdout or result.stderr).decode("utf-8", "replace").strip()
    return result.returncode, out


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    total = 0
    found = 0
    for name, cases in TRAMPAS.items():
        folder = ROOT / name
        for case in cases:
            total += 1
            left = run(folder, "original.py", case)
            right = run(folder, "port.py", case)
            same = (left[0] == 0) == (right[0] == 0) and (left[0] != 0 or left[1] == right[1])
            if same:
                continue
            found += 1
            print(f"{name:9s} {case!r}")
            print(f"          original {left[0]} {left[1][:70]!r}")
            print(f"          port     {right[0]} {right[1][:70]!r}")

    # Control: el corpus normal, que las seis parejas pasan enteras.
    control = 0
    control_fallos = 0
    for name, cases in NORMAL.items():
        folder = ROOT / name
        for case in cases:
            control += 1
            left = run(folder, "original.py", case)
            right = run(folder, "port.py", case)
            if not ((left[0] == 0) == (right[0] == 0) and (left[0] != 0 or left[1] == right[1])):
                control_fallos += 1

    print(f"\ncorpus normal: {control - control_fallos}/{control} fieles")
    print(f"corpus de trampas: {total - found}/{total} fieles, {found} divergencias")
    return 0


if __name__ == "__main__":
    sys.exit(main())
