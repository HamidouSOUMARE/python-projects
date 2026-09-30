"""Relecture du rendu : ce qui entre dans la notation, et ce qui en est exclu."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import workspace
from app.workspace import code_excerpt, collect_files, ensure_project_dir, files_block, stats


@pytest.fixture
def rendu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(workspace, "PROJECTS_DIR", tmp_path)
    directory = tmp_path / "day-03-demo"
    (directory / "tests").mkdir(parents=True)
    (directory / "__pycache__").mkdir()
    (directory / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (directory / "tests" / "test_main.py").write_text("def test_ok(): assert True\n", "utf-8")
    (directory / "README.md").write_text("# Demo\n", encoding="utf-8")
    (directory / "BRIEF.md").write_text("# Brief\n", encoding="utf-8")
    (directory / "donnees.sqlite").write_bytes(b"\x00binaire")
    (directory / "__pycache__" / "main.cpython-312.pyc").write_bytes(b"\x00cache")
    return directory


def test_collect_files_retient_les_sources_et_ecarte_le_reste(rendu: Path) -> None:
    paths = {source.path for source in collect_files(rendu)}
    assert paths == {"main.py", "tests/test_main.py", "README.md"}


def test_collect_files_ecarte_le_brief(rendu: Path) -> None:
    """Le brief est une consigne, pas une production : il ne doit pas etre note."""
    assert all(source.path != "BRIEF.md" for source in collect_files(rendu))


def test_collect_files_place_le_python_en_premier(rendu: Path) -> None:
    files = collect_files(rendu)
    assert files[0].path.endswith(".py")


def test_collect_files_sur_dossier_absent_retourne_une_liste_vide(tmp_path: Path) -> None:
    assert collect_files(tmp_path / "inexistant") == []


def test_collect_files_tronque_les_fichiers_demesures(
    rendu: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(workspace, "MAX_FILE_CHARS", 20)
    (rendu / "gros.py").write_text("x = 1\n" * 100, encoding="utf-8")
    gros = next(source for source in collect_files(rendu) if source.path == "gros.py")
    assert gros.truncated is True
    assert len(gros.content) == 20


def test_files_block_marque_la_troncature(rendu: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(workspace, "MAX_FILE_CHARS", 20)
    (rendu / "gros.py").write_text("x = 1\n" * 100, encoding="utf-8")
    block = files_block(collect_files(rendu))
    assert "fichier tronque" in block
    assert "### main.py" in block


def test_files_block_sans_fichier_le_dit_explicitement() -> None:
    assert "Aucun fichier source" in files_block([])


def test_code_excerpt_ne_garde_que_le_python(rendu: Path) -> None:
    excerpt = code_excerpt(collect_files(rendu))
    assert "main.py" in excerpt
    assert "README.md" not in excerpt


def test_stats_compte_les_tests(rendu: Path) -> None:
    assert stats(collect_files(rendu)) == {
        "files": 3,
        "python_files": 2,
        "lines": 2,
        "test_files": 1,
    }


def test_ensure_project_dir_ecrase_le_brief_mais_jamais_le_readme(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(workspace, "PROJECTS_DIR", tmp_path)
    directory = ensure_project_dir(4, "demo", "Demo", "# Brief v1\n")
    (directory / "README.md").write_text("mes notes\n", encoding="utf-8")

    ensure_project_dir(4, "demo", "Demo", "# Brief v2\n")

    assert (directory / "BRIEF.md").read_text(encoding="utf-8") == "# Brief v2\n"
    assert (directory / "README.md").read_text(encoding="utf-8") == "mes notes\n"
