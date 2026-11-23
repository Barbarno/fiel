"""Busca diferencias entre dos implementaciones reales de semver.

Ejecuta el original (Python) y el port (Rust) sobre una bateria de entradas y
muestra solo las que no coinciden. Sirve para decidir que va al corpus normal
y que va al corpus de trampas.

    python examples/real-semver/probe.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUST = ROOT / "rust-port" / "target" / "x86_64-pc-windows-gnu" / "release" / "semver-rs.exe"

CASES = [
    "1.2.3",
    "0.0.0",
    "10.20.30",
    "1.2.3-alpha",
    "1.2.3-alpha.1",
    "1.2.3-alpha.beta",
    "1.2.3-0",
    "1.2.3-0.3.7",
    "1.2.3-x.7.z.92",
    "1.2.3+build",
    "1.2.3+build.1",
    "1.2.3+build.001",
    "1.2.3-alpha+20130313144700",
    "1.2.3-beta+exp.sha.5114f85",
    "1.2.3-rc.1+build.5",
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0-x-y-z.--",
    "18446744073709551615.0.0",
    "18446744073709551616.0.0",
    "99999999999999999999.0.0",
    "1.2.3-01",
    "01.2.3",
    "1.02.3",
    "1.2.03",
    "1.2",
    "1.2.3.4",
    "v1.2.3",
    "=1.2.3",
    " 1.2.3 ",
    "1.2.3-",
    "1.2.3+",
    "1.2.3-a..b",
    "1.2.3-a_b",
    "1.2.3-á",
    "1.2.3-α.β",
    "1.2.3-1.0",
    "1.2.3-0.0.0",
    "1.2.3-ALPHA",
    "1.2.3-alpha.01",
    "1.2.3+build.01",
    "1.2.3-beta..1",
    "1.2.3-beta.",
    "1.2.3-.beta",
    "1.2.3+meta_dato",
    "1.2.3+meta-dato",
    "1.2.3-0A",
    "0.0.0-0",
    "1.2.3-rc.1.2.3",
]


def run(command: list[str], case: str) -> tuple[int, str]:
    result = subprocess.run(
        command, input=case.encode(), capture_output=True, timeout=30
    )
    return result.returncode, (result.stdout or result.stderr).decode("utf-8", "replace").strip()


def main() -> int:
    ports = [["python", str(ROOT / "original.py")], [str(RUST)]]
    same = 0
    diff = 0
    for case in CASES:
        left = run(ports[0], case)
        right = run(ports[1], case)
        match = (left[0] == 0) == (right[0] == 0) and (left[0] != 0 or left[1] == right[1])
        if match:
            same += 1
            continue
        diff += 1
        print(f"CASO   {case!r}")
        print(f"  python: exit={left[0]} {left[1][:90]}")
        print(f"  rust:   exit={right[0]} {right[1][:90]}")
    print(f"\n{len(CASES)} entradas: {same} coinciden, {diff} divergen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
