"""Execution du code d'un projet, pour le mode libre.

On lance le script de l'utilisateur dans un sous-processus, sans passer par un
shell : les arguments sont transmis tels quels, jamais interpretes. La cle API
est retiree de l'environnement du processus fils - le code d'un exercice n'a
aucune raison d'y avoir acces.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from app.models import CoachError

#: Un exercice qui ne rend pas la main en 15 s est considere comme bloque.
DEFAULT_TIMEOUT = 15
TESTS_TIMEOUT = 60
MAX_OUTPUT_CHARS = 20_000

#: Prefixes de variables d'environnement masquees au code de l'utilisateur.
MASKED_ENV_PREFIXES = ("ANTHROPIC_", "COACH_", "GIT_REMOTE", "PASS_THRESHOLD", "HINT_")


@dataclass(frozen=True, slots=True)
class RunResult:
    command: str
    stdout: str
    stderr: str
    returncode: int | None
    duration_ms: int
    timed_out: bool

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    @property
    def silent(self) -> bool:
        return not self.stdout.strip() and not self.stderr.strip()


def child_env() -> dict[str, str]:
    """Environnement du sous-processus, prive des reglages du coach."""
    env = {
        key: value for key, value in os.environ.items() if not key.startswith(MASKED_ENV_PREFIXES)
    }
    env["PYTHONUNBUFFERED"] = "1"
    return env


def entrypoints(directory: Path) -> list[str]:
    """Scripts Python lancables a la racine du projet, hors fichiers de test."""
    if not directory.is_dir():
        return []
    names = sorted(
        path.name
        for path in directory.glob("*.py")
        if path.is_file() and not path.name.startswith("test_")
    )
    # main.py d'abord : c'est la convention proposee par le squelette.
    names.sort(key=lambda name: (name != "main.py", name))
    return names


def has_tests(directory: Path) -> bool:
    if not directory.is_dir():
        return False
    return any(directory.glob("test_*.py")) or any(directory.glob("tests/test_*.py"))


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n[... sortie tronquee ...]"


def _execute(command: list[str], directory: Path, stdin_text: str, timeout: int) -> RunResult:
    started = time.monotonic()
    try:
        completed = subprocess.run(  # noqa: S603 - commande construite ici, jamais un shell
            command,
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=stdin_text,
            env=child_env(),
            check=False,
        )
    except subprocess.TimeoutExpired as expired:
        return RunResult(
            command=shlex.join(command),
            stdout=_truncate(_decode(expired.stdout)),
            stderr=_truncate(_decode(expired.stderr)),
            returncode=None,
            duration_ms=int((time.monotonic() - started) * 1000),
            timed_out=True,
        )
    except OSError as error:
        raise CoachError(f"Lancement impossible : {error}") from error

    return RunResult(
        command=shlex.join(command),
        stdout=_truncate(completed.stdout),
        stderr=_truncate(completed.stderr),
        returncode=completed.returncode,
        duration_ms=int((time.monotonic() - started) * 1000),
        timed_out=False,
    )


def _decode(output: str | bytes | None) -> str:
    """Un timeout renvoie ce qui avait deja ete ecrit, parfois en octets."""
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def run_script(
    directory: Path,
    entrypoint: str = "main.py",
    args: str = "",
    stdin_text: str = "",
    timeout: int = DEFAULT_TIMEOUT,
) -> RunResult:
    """Lance un script du projet et capture sa sortie."""
    if not directory.is_dir():
        raise CoachError("Le dossier de ce projet n'existe pas encore.")

    name = Path(entrypoint).name
    if name != entrypoint or not name.endswith(".py"):
        raise CoachError("Le point d'entree doit etre un fichier .py du dossier du projet.")

    script = directory / name
    if not script.is_file():
        raise CoachError(f"{name} est introuvable dans {directory.name}.")

    try:
        parsed_args = shlex.split(args)
    except ValueError as error:
        raise CoachError(f"Arguments illisibles (guillemet non ferme ?) : {error}") from error

    return _execute([sys.executable, name, *parsed_args], directory, stdin_text, timeout)


def run_tests(directory: Path, timeout: int = TESTS_TIMEOUT) -> RunResult:
    """Lance pytest dans le dossier du projet."""
    if not directory.is_dir():
        raise CoachError("Le dossier de ce projet n'existe pas encore.")
    if not has_tests(directory):
        raise CoachError(
            "Aucun test trouve. Cree un fichier test_quelquechose.py dans le dossier "
            "du projet, puis relance."
        )
    return _execute([sys.executable, "-m", "pytest", "-q", "--no-header"], directory, "", timeout)
