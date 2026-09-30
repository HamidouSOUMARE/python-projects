"""Gestion du dossier de travail d'un projet dans le monorepo `projects/`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import PROJECTS_DIR

#: Extensions relues lors de la notation.
GRADED_SUFFIXES = frozenset(
    {".py", ".md", ".txt", ".toml", ".cfg", ".ini", ".json", ".yml", ".yaml"}
)

#: Dossiers ignores : ils ne font pas partie du rendu.
IGNORED_DIRS = frozenset(
    {
        ".venv",
        "venv",
        "__pycache__",
        ".git",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        ".idea",
        ".vscode",
    }
)

MAX_FILES = 40
MAX_FILE_CHARS = 40_000
MAX_TOTAL_CHARS = 120_000


@dataclass(frozen=True, slots=True)
class SourceFile:
    path: str
    content: str
    truncated: bool


def project_dir(day: int, slug: str) -> Path:
    return PROJECTS_DIR / f"day-{day:02d}-{slug}"


def ensure_project_dir(day: int, slug: str, title: str, brief_md: str) -> Path:
    """Cree le dossier du projet et y depose le brief, sans jamais ecraser du code."""
    directory = project_dir(day, slug)
    directory.mkdir(parents=True, exist_ok=True)

    # Le brief est reecrit a chaque fois : il est la reference, pas une production.
    (directory / "BRIEF.md").write_text(brief_md, encoding="utf-8")

    readme = directory / "README.md"
    if not readme.exists():
        readme.write_text(
            f"# Jour {day:02d} - {title}\n\n"
            "## Besoin\n\nVoir [BRIEF.md](./BRIEF.md).\n\n"
            "## Utilisation\n\n```bash\npython main.py\n```\n\n"
            "## Choix techniques\n\n_A completer._\n",
            encoding="utf-8",
        )
    return directory


def _is_ignored(path: Path, root: Path) -> bool:
    return any(part in IGNORED_DIRS for part in path.relative_to(root).parts[:-1])


def collect_files(directory: Path) -> list[SourceFile]:
    """Relit le rendu : fichiers sources triés, tronques si demesures."""
    if not directory.is_dir():
        return []

    candidates = sorted(
        (
            path
            for path in directory.rglob("*")
            if path.is_file()
            and path.suffix.lower() in GRADED_SUFFIXES
            and path.name != "BRIEF.md"
            and not _is_ignored(path, directory)
        ),
        key=lambda path: (path.suffix != ".py", str(path).lower()),
    )

    files: list[SourceFile] = []
    budget = MAX_TOTAL_CHARS
    for path in candidates[:MAX_FILES]:
        if budget <= 0:
            break
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue  # fichier binaire ou illisible : hors perimetre de notation
        limit = min(MAX_FILE_CHARS, budget)
        truncated = len(raw) > limit
        files.append(
            SourceFile(
                path=str(path.relative_to(directory)),
                content=raw[:limit],
                truncated=truncated,
            )
        )
        budget -= len(raw[:limit])
    return files


def files_block(files: list[SourceFile]) -> str:
    """Serialise le rendu pour le prompt de notation."""
    if not files:
        return "Aucun fichier source trouve dans le dossier du projet."
    parts: list[str] = []
    for source in files:
        suffix = "\n[... fichier tronque ...]" if source.truncated else ""
        language = "python" if source.path.endswith(".py") else ""
        parts.append(f"### {source.path}\n```{language}\n{source.content}{suffix}\n```")
    return "\n\n".join(parts)


def code_excerpt(files: list[SourceFile], max_chars: int = 12_000) -> str:
    """Extrait court du code Python, pour contextualiser un indice."""
    python_files = [source for source in files if source.path.endswith(".py")]
    if not python_files:
        return ""
    parts: list[str] = []
    budget = max_chars
    for source in python_files:
        chunk = source.content[:budget]
        parts.append(f"### {source.path}\n```python\n{chunk}\n```")
        budget -= len(chunk)
        if budget <= 0:
            break
    return "\n\n".join(parts)


def stats(files: list[SourceFile]) -> dict[str, int]:
    python_files = [source for source in files if source.path.endswith(".py")]
    return {
        "files": len(files),
        "python_files": len(python_files),
        "lines": sum(len(source.content.splitlines()) for source in python_files),
        "test_files": sum(
            1
            for source in python_files
            if "test" in Path(source.path).name.lower() or source.path.startswith("tests/")
        ),
    }
