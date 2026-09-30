"""Acces SQLite : connexion, schema et amorcage du catalogue."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from app.config import CATALOG_PATH, DB_PATH
from app.models import CoachError

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def now() -> str:
    """Horodatage ISO 8601 en UTC, stocke tel quel en base."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def transaction(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Connexion transactionnelle : commit en sortie, rollback sur exception."""
    connection = connect(db_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db(db_path: Path | None = None, catalog_path: Path | None = None) -> None:
    """Cree le schema puis synchronise le catalogue de projets."""
    with transaction(db_path) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _seed_catalog(connection, catalog_path or CATALOG_PATH)


def _seed_catalog(connection: sqlite3.Connection, catalog_path: Path) -> None:
    if not catalog_path.exists():
        raise CoachError(
            f"Catalogue introuvable ({catalog_path}). Lance : python scripts/build_catalog.py"
        )
    try:
        entries = json.loads(catalog_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise CoachError(f"Catalogue illisible ({catalog_path}) : {error}") from error

    connection.executemany(
        """
        INSERT INTO projects (slug, title, source_url, theme, difficulty, day)
        VALUES (:slug, :title, :source_url, :theme, :difficulty, :day)
        ON CONFLICT(slug) DO UPDATE SET
            title = excluded.title,
            source_url = excluded.source_url,
            theme = excluded.theme,
            difficulty = excluded.difficulty,
            day = excluded.day
        """,
        entries,
    )
