"""Ejecuta un lado de la pareja: le pasa bytes por stdin, recoge bytes de stdout.

Nada de shell. Sin dependencias. Un caso que se cuelga no cuelga la suite.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

OK = "ok"
ERR = "err"
TIMEOUT = "timeout"
CRASH = "crash"

MISSING_OUTPUT_LIMIT = 1 << 20  # 1 MiB: mas que esto no es una salida, es una fuga


@dataclass(frozen=True)
class Observation:
    status: str
    output: bytes
    detail: str = ""


def _normalize_argv(command: list[str], cwd: Path | None) -> list[str]:
    """Un fiel.toml escrito en Linux tiene barras normales y rutas relativas.
    En Windows hay que traducirlas o CreateProcess no encuentra el binario."""
    if os.sep == "/":
        return command
    argv = list(command)
    head = argv[0]
    if "/" in head and not head.startswith(("http://", "https://")):
        candidate = head.replace("/", os.sep)
        base = cwd if cwd is not None else Path.cwd()
        target = base / candidate
        if target.exists():
            # absoluta: en Windows la ruta del ejecutable se resuelve contra el
            # directorio del proceso padre, no contra el cwd del hijo
            argv[0] = str(target.resolve())
        elif (base / head).exists():
            argv[0] = str((base / head).resolve())
    return argv


def run(
    command: list[str],
    payload: bytes,
    timeout_ms: int,
    cwd: Path | None = None,
) -> Observation:
    argv = _normalize_argv(command, cwd)
    try:
        completed = subprocess.run(
            argv,
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(cwd) if cwd else None,
            timeout=timeout_ms / 1000.0,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return Observation(TIMEOUT, b"", f"no termino en {timeout_ms} ms")
    except FileNotFoundError as exc:
        return Observation(CRASH, b"", f"no se pudo ejecutar {command[0]}: {exc}")
    except OSError as exc:
        return Observation(CRASH, b"", f"error al ejecutar: {exc}")

    stdout = completed.stdout[:MISSING_OUTPUT_LIMIT]
    if completed.returncode == 0:
        return Observation(OK, stdout)
    if completed.returncode > 0:
        # codigo de salida positivo = error controlado del programa
        detail = completed.stderr.decode("utf-8", "replace").strip().splitlines()
        return Observation(ERR, stdout, detail[-1] if detail else "")
    # codigo negativo = senal (panic, segfault, abort) en POSIX
    detail = completed.stderr.decode("utf-8", "replace").strip().splitlines()
    return Observation(CRASH, stdout, detail[-1] if detail else f"signal {-completed.returncode}")
