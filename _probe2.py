from pathlib import Path
import subprocess

ROOT = Path("examples/real-semver")
RUST = ROOT / "rust-port" / "target" / "x86_64-pc-windows-gnu" / "release" / "semver-rs.exe"

PAIRS = [
    ("1.0.0-alpha", "1.0.0-alpha.1"),
    ("1.0.0-alpha.1", "1.0.0-alpha.beta"),
    ("1.0.0-beta.2", "1.0.0-beta.11"),
    ("1.0.0-rc.1", "1.0.0"),
    ("1.0.0+build1", "1.0.0+build2"),
    ("1.0.0-ALPHA", "1.0.0-alpha"),
    ("1.0.0-Alpha", "1.0.0-alpha"),
    ("1.0.0-a", "1.0.0-A"),
    ("1.0.0-2", "1.0.0-10"),
    ("1.0.0-1", "1.0.0-alpha"),
    ("1.0.0-alpha", "1.0.0-1"),
    ("0.0.1", "0.1.0"),
    ("1.0.0", "1.0.0"),
    ("1.0.0-0", "1.0.0-0.0"),
    ("1.0.0-x.7.z.92", "1.0.0-x.7.z.93"),
    ("1.0.0-alpha.beta", "1.0.0-beta"),
    ("2.0.0", "10.0.0"),
    ("1.0.0-alpha+001", "1.0.0-alpha+002"),
    ("1.0.0-0.0.1", "1.0.0-0.0.2"),
    ("1.0.0-A.1", "1.0.0-a.1"),
    ("1.0.0-alpha.1", "1.0.0-alpha.1+build"),
]


def run(cmd, text):
    r = subprocess.run(cmd, input=text.encode(), capture_output=True, timeout=30)
    return r.returncode, (r.stdout or r.stderr).decode("utf-8", "replace").strip()


diff = 0
for a, b in PAIRS:
    expr = f"{a} {b}"
    left = run(["python", str(ROOT / "original.py")], expr)
    right = run([str(RUST)], expr)
    ok = (left[0] == 0) == (right[0] == 0) and (left[0] != 0 or left[1] == right[1])
    if not ok:
        diff += 1
        print(f"DIVERGE {expr!r}\n  python: exit={left[0]} {left[1][:80]}\n  rust:   exit={right[0]} {right[1][:80]}")
print(f"\n{len(PAIRS)} pares, {diff} divergencias")
