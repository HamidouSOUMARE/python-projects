"""Commit et push du rendu dans le monorepo.

Le push n'a lieu que si GIT_REMOTE est configure. Sans remote, le commit local
est fait quand meme : l'historique de progression reste intact.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.config import ROOT, Settings, get_settings

GIT_TIMEOUT = 60


@dataclass(frozen=True, slots=True)
class PushResult:
    committed: bool
    pushed: bool
    commit_sha: str | None
    message: str


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT,
        check=check,
    )


def is_repo() -> bool:
    return (ROOT / ".git").is_dir()


def ensure_repo(settings: Settings | None = None) -> None:
    """Initialise le depot si besoin et aligne la branche courante."""
    config = settings or get_settings()
    if not is_repo():
        _git("init", "-b", config.git_branch)
    if config.git_remote:
        existing = _git("remote", check=False)
        if "origin" not in existing.stdout.split():
            _git("remote", "add", "origin", config.git_remote)
        else:
            _git("remote", "set-url", "origin", config.git_remote)


def commit_and_push(
    paths: list[Path], message: str, settings: Settings | None = None
) -> PushResult:
    """Ajoute les chemins donnes, commite, puis pousse si un remote est configure."""
    config = settings or get_settings()
    try:
        ensure_repo(config)
        relative = [str(path.relative_to(ROOT)) for path in paths]
        _git("add", "--", *relative)

        staged = _git("diff", "--cached", "--name-only", "--", *relative, check=False)
        if not staged.stdout.strip():
            sha = _head_sha()
            return PushResult(False, False, sha, "Aucun changement a commiter.")

        _git("commit", "-m", message)
        sha = _head_sha()

        if not config.git_remote:
            return PushResult(
                True, False, sha, "Commit local effectue. Aucun remote configure (GIT_REMOTE vide)."
            )

        push = _git("push", "-u", "origin", config.git_branch, check=False)
        if push.returncode != 0:
            detail = (push.stderr or push.stdout).strip().splitlines()
            return PushResult(
                True, False, sha, f"Commit effectue, push refuse : {detail[-1] if detail else '?'}"
            )
        return PushResult(True, True, sha, f"Pousse sur origin/{config.git_branch}.")

    except FileNotFoundError:
        return PushResult(False, False, None, "git est introuvable sur cette machine.")
    except subprocess.TimeoutExpired:
        return PushResult(False, False, None, "git n'a pas repondu dans le delai imparti.")
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip().splitlines()
        return PushResult(False, False, None, f"git a echoue : {detail[-1] if detail else error}")


def _head_sha() -> str | None:
    result = _git("rev-parse", "--short", "HEAD", check=False)
    return result.stdout.strip() or None
