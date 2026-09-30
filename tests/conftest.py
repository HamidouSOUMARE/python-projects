"""Fixtures partagees : base temporaire, faux coach, dossier de travail isole."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app import service, workspace
from app.config import Settings
from app.db import connect, init_db
from app.gitops import PushResult

CATALOG = [
    {
        "slug": "hello-world",
        "title": "Hello World",
        "source_url": "https://example.test/hello",
        "theme": "divers",
        "difficulty": 1,
        "day": 1,
    },
    {
        "slug": "compteur-de-mots",
        "title": "Compteur de mots",
        "source_url": "https://example.test/words",
        "theme": "donnees",
        "difficulty": 2,
        "day": 2,
    },
]

BRIEF_PAYLOAD: dict[str, Any] = {
    "client_name": "Librairie Fontaine",
    "context_md": "Je gere une petite librairie.",
    "need_md": "Je veux savoir quels mots reviennent le plus dans les avis clients.",
    "constraints": ["Doit tourner sur mon portable", "Rendu pour vendredi"],
    "acceptance": [
        {"id": "ac1", "label": "Lit un fichier texte", "critical": True},
        {"id": "ac2", "label": "Compte les occurrences", "critical": True},
        {"id": "ac3", "label": "Ignore la casse", "critical": False},
        {"id": "ac4", "label": "Affiche le top 10", "critical": True},
    ],
}

GRADE_PAYLOAD: dict[str, Any] = {
    "scores": {
        "conformite": {"score": 16, "justification": "Le top 10 est bien affiche."},
        "structure": {"score": 14, "justification": "Decoupage correct."},
        "lisibilite": {"score": 15, "justification": "Nommage clair."},
        "robustesse": {"score": 12, "justification": "Fichier absent non gere."},
        "idiomes": {"score": 13, "justification": "Counter aurait simplifie."},
        "tests_doc": {"score": 6, "justification": "Aucun test."},
    },
    "summary_md": "Rendu fonctionnel, la robustesse et les tests manquent.",
    "strengths": ["Lecture du fichier via un context manager"],
    "axes": [
        {
            "titre": "Gerer le fichier introuvable",
            "pourquoi": "Le client verra une trace Python illisible.",
            "comment": "Encadre l'ouverture et affiche un message utile.",
            "critere": "robustesse",
            "priorite": 1,
        },
        {
            "titre": "Ajouter des tests",
            "pourquoi": "Aucune garantie de non-regression.",
            "comment": "Teste le comptage sur un texte court connu.",
            "critere": "tests_doc",
            "priorite": 2,
        },
    ],
}


class FakeCoach:
    """Coach deterministe : aucune requete reseau, verdicts pilotes par le test."""

    def __init__(self, *, accept_understanding: bool = True) -> None:
        self.accept_understanding = accept_understanding
        self.calls: list[str] = []

    def generate_brief(
        self, title: str, theme: str, difficulty: int, source_url: str
    ) -> dict[str, Any]:
        self.calls.append("brief")
        return dict(BRIEF_PAYLOAD)

    def review_understanding(
        self, brief_block: str, understanding: str, attempt_no: int
    ) -> dict[str, Any]:
        self.calls.append("understanding")
        if self.accept_understanding:
            return {
                "verdict": "valide",
                "coverage": 100,
                "summary_md": "C'est bien ca.",
                "confirmed": ["Le comptage", "Le top 10"],
                "gaps": [],
                "offtrack": [],
            }
        return {
            "verdict": "a_preciser",
            "coverage": 40,
            "summary_md": "Il me manque l'essentiel.",
            "confirmed": ["La lecture du fichier"],
            "gaps": [{"point": "Le classement", "relance": "Combien de mots voulez-vous voir ?"}],
            "offtrack": ["Une interface graphique"],
        }

    def give_hint(
        self,
        brief_block: str,
        understanding: str,
        level: int,
        previous: list[str],
        code_excerpt: str,
    ) -> str:
        self.calls.append(f"hint{level}")
        return f"Indice de palier {level}."

    def grade(
        self,
        brief_block: str,
        understanding: str,
        files_block: str,
        hints_used: list[int],
        attempt_no: int,
        previous_axes: list[str],
    ) -> dict[str, Any]:
        self.calls.append("grade")
        self.last_previous_axes = previous_axes
        return dict(GRADE_PAYLOAD)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        anthropic_api_key="test-key",
        pass_threshold=14.0,
        hint_penalties=(0.5, 1.0, 2.0),
        git_remote="",
        git_branch="main",
    )


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Base temporaire amorcee avec un catalogue reduit a deux projets."""
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(CATALOG), encoding="utf-8")
    path = tmp_path / "coach.db"
    init_db(path, catalog_path)
    return path


@pytest.fixture
def connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    yield conn
    conn.close()


@pytest.fixture
def projects_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isole le monorepo d'exercices et neutralise git."""
    directory = tmp_path / "projects"
    directory.mkdir()
    monkeypatch.setattr(workspace, "PROJECTS_DIR", directory)
    monkeypatch.setattr(
        service,
        "commit_and_push",
        lambda paths, message, config=None: PushResult(True, False, "abc1234", "Commit local."),
    )
    return directory


@pytest.fixture
def coach() -> FakeCoach:
    return FakeCoach()
