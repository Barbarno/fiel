"""Publica el informe en un pull request, sin spamear.

Idempotente por marcador: si ya hay un comentario de fiel, lo actualiza. Si el
informe es identico al anterior, no hace nada (ni una peticion de escritura).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .report import MARKER

API = "https://api.github.com"


class BotError(Exception):
    pass


def _request(method: str, url: str, token: str, payload: dict | None = None) -> tuple[int, object]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    request.add_header("User-Agent", "fiel")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", "replace")
            return response.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise BotError(f"GitHub respondio {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise BotError(f"no se pudo conectar con GitHub: {exc.reason}") from exc


def find_comment(repo: str, number: int, token: str) -> int | None:
    page = 1
    while page <= 10:
        status, body = _request("GET", f"{API}/repos/{repo}/issues/{number}/comments?per_page=100&page={page}", token)
        if status != 200 or not isinstance(body, list):
            raise BotError(f"respuesta inesperada al listar comentarios ({status})")
        for comment in body:
            if isinstance(comment, dict) and MARKER in str(comment.get("body", "")):
                return int(comment["id"])
        if len(body) < 100:
            return None
        page += 1
    return None


def resolve_token(token: str | None) -> str:
    value = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not value:
        raise BotError("falta el token: pasa --token o define GH_TOKEN")
    return value


def upsert_comment(repo: str, number: int, body: str, token: str, dry_run: bool = False) -> str:
    if dry_run:
        return "dry-run: no se ha publicado nada"
    existing = find_comment(repo, number, token)
    if existing is None:
        status, _ = _request("POST", f"{API}/repos/{repo}/issues/{number}/comments", token, {"body": body})
        if status not in (200, 201):
            raise BotError(f"no se pudo crear el comentario ({status})")
        return "comentario creado"

    status, current = _request("GET", f"{API}/repos/{repo}/issues/comments/{existing}", token)
    if status == 200 and isinstance(current, dict) and current.get("body") == body:
        return "sin cambios: el comentario ya estaba actualizado"

    status, _ = _request("PATCH", f"{API}/repos/{repo}/issues/comments/{existing}", token, {"body": body})
    if status not in (200, 201):
        raise BotError(f"no se pudo actualizar el comentario ({status})")
    return "comentario actualizado"


def repo_from_env() -> str | None:
    return os.environ.get("GITHUB_REPOSITORY")


def pr_from_env() -> int | None:
    raw = os.environ.get("PR_NUMBER") or os.environ.get("GITHUB_REF_NAME")
    if not raw:
        return None
    try:
        return int(str(raw).lstrip("#"))
    except ValueError:
        return None
