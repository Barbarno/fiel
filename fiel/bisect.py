"""fiel bisect - en que commit se rompio la equivalencia.

Recorre los commits de un rango, de viejo a nuevo, en un worktree temporal
(nunca toca tu copia de trabajo) y se queda con el primero que falla.

Lineal, no binario, a proposito: la fidelidad no tiene por que ser monotona,
y un resultado binario puede mentir.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


class BisectError(Exception):
    pass


@dataclass(frozen=True)
class BisectStep:
    commit: str
    subject: str
    ok: bool
    detail: str


def _git(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
        )
    except FileNotFoundError as exc:
        raise BisectError("git no esta instalado o no esta en el PATH") from exc
    if completed.returncode != 0:
        raise BisectError(f"git {' '.join(args)} fallo: {completed.stderr.strip()}")
    return completed.stdout


def commits(root: Path, since: str, until: str = "HEAD") -> list[tuple[str, str]]:
    raw = _git(root, "rev-list", "--reverse", f"{since}..{until}")
    out: list[tuple[str, str]] = []
    for sha in raw.split():
        subject = _git(root, "log", "-1", "--format=%s", sha).strip()
        out.append((sha, subject))
    return out


def run_bisect(
    root: Path,
    since: str,
    until: str = "HEAD",
    pair_ids: list[str] | None = None,
    timeout_s: int = 300,
) -> list[BisectStep]:
    steps: list[BisectStep] = []
    history = commits(root, since, until)
    if not history:
        raise BisectError(f"no hay commits en {since}..{until}")

    temp_root = Path(tempfile.mkdtemp(prefix="fiel-bisect-"))
    try:
        for sha, subject in history:
            worktree = temp_root / sha[:12]
            _git(root, "worktree", "add", "--detach", str(worktree), sha)
            try:
                ok, detail = _check_in(worktree, pair_ids, timeout_s)
            finally:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(worktree)],
                    cwd=str(root),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            steps.append(BisectStep(sha, subject, ok, detail))
            if not ok:
                break
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
    return steps


def _check_in(worktree: Path, pair_ids: list[str] | None, timeout_s: int) -> tuple[bool, str]:
    command = [sys.executable, "-m", "fiel", "check", "--quiet", "--no-baseline"]
    for pid in pair_ids or []:
        command.extend(["--pair", pid])
    try:
        completed = subprocess.run(
            command,
            cwd=str(worktree),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"la comprobacion no termino en {timeout_s} s"
    if completed.returncode == 0:
        return True, ""
    tail = (completed.stdout or completed.stderr).strip().splitlines()
    return False, tail[-1] if tail else f"exit {completed.returncode}"
