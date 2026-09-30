"""Parcours complet d'un projet, et garde-fous de la machine a etats."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from app import service
from app.config import Settings
from app.models import CoachError, Status, TransitionError
from tests.conftest import GRADE_PAYLOAD, FakeCoach

UNDERSTANDING = (
    "Vous voulez un programme qui lit un fichier d'avis clients, compte combien de fois "
    "chaque mot apparait, et affiche les dix mots les plus frequents. La casse ne doit pas "
    "creer de doublons, et le tout doit tourner sur votre portable sans installation lourde."
)


class GenerousCoach(FakeCoach):
    """Coach qui note au-dessus du seuil, pour eprouver le chemin de validation."""

    def grade(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        payload = dict(GRADE_PAYLOAD)
        payload["scores"] = {
            key: {"score": 18, "justification": "Tres bien."} for key in GRADE_PAYLOAD["scores"]
        }
        return payload


def _write_solution(directory: Path) -> None:
    (directory / "main.py").write_text(
        "from collections import Counter\n\n\n"
        "def top_words(path: str, limit: int = 10) -> list[tuple[str, int]]:\n"
        "    with open(path, encoding='utf-8') as handle:\n"
        "        words = handle.read().lower().split()\n"
        "    return Counter(words).most_common(limit)\n",
        encoding="utf-8",
    )


def _bring_to_coding(
    connection: sqlite3.Connection, coach: FakeCoach, project_id: int = 2
) -> dict[str, Any]:
    project = service.get_project(connection, project_id)
    service.ensure_brief(connection, coach, project)
    service.start_attempt(connection, project_id)
    service.submit_understanding(connection, coach, project_id, UNDERSTANDING)
    return project


# --------------------------------------------------------------------------- #
# Brief
# --------------------------------------------------------------------------- #


def test_le_brief_est_genere_une_seule_fois(
    connection: sqlite3.Connection, coach: FakeCoach
) -> None:
    project = service.get_project(connection, 1)
    first = service.ensure_brief(connection, coach, project)
    second = service.ensure_brief(connection, coach, project)
    assert coach.calls.count("brief") == 1
    assert first["need_md"] == second["need_md"]


def test_le_bloc_envoye_au_modele_contient_les_criteres_caches(
    connection: sqlite3.Connection, coach: FakeCoach
) -> None:
    project = service.get_project(connection, 1)
    brief = service.ensure_brief(connection, coach, project)
    block = service.brief_block(brief)
    assert "Affiche le top 10" in block
    assert "(critique)" in block


def test_le_brief_ecrit_sur_disque_ne_revele_pas_les_criteres(
    connection: sqlite3.Connection, coach: FakeCoach
) -> None:
    project = service.get_project(connection, 1)
    brief = service.ensure_brief(connection, coach, project)
    markdown = service.brief_markdown(project, brief)
    assert "Affiche le top 10" not in markdown
    assert brief["need_md"] in markdown


# --------------------------------------------------------------------------- #
# Verrou de la comprehension
# --------------------------------------------------------------------------- #


def test_reformulation_trop_courte_est_refusee(
    connection: sqlite3.Connection, coach: FakeCoach
) -> None:
    project = service.get_project(connection, 1)
    service.ensure_brief(connection, coach, project)
    with pytest.raises(CoachError, match="trop courte"):
        service.submit_understanding(connection, coach, 1, "J'ai compris.")
    assert "understanding" not in coach.calls


def test_comprehension_refusee_laisse_le_chantier_ferme(
    connection: sqlite3.Connection, projects_dir: Path
) -> None:
    coach = FakeCoach(accept_understanding=False)
    project = service.get_project(connection, 1)
    service.ensure_brief(connection, coach, project)
    verdict = service.submit_understanding(connection, coach, 1, UNDERSTANDING)

    assert verdict["verdict"] == "a_preciser"
    attempt = service.latest_attempt(connection, 1)
    assert attempt is not None
    assert Status(attempt["status"]) is Status.UNDERSTANDING_REJECTED
    assert service.validated_understanding(connection, 1) is None
    assert list(projects_dir.iterdir()) == []


def test_comprehension_validee_ouvre_le_chantier(
    connection: sqlite3.Connection, coach: FakeCoach, projects_dir: Path
) -> None:
    project = service.get_project(connection, 1)
    service.ensure_brief(connection, coach, project)
    verdict = service.submit_understanding(connection, coach, 1, UNDERSTANDING)

    assert verdict["verdict"] == "valide"
    attempt = service.latest_attempt(connection, 1)
    assert attempt is not None
    assert Status(attempt["status"]) is Status.CODING

    directory = projects_dir / "day-01-hello-world"
    assert (directory / "BRIEF.md").is_file()
    assert (directory / "README.md").is_file()


def test_on_ne_peut_ni_rendre_ni_demander_un_indice_avant_validation(
    connection: sqlite3.Connection, coach: FakeCoach, settings: Settings
) -> None:
    project = service.get_project(connection, 1)
    service.ensure_brief(connection, coach, project)
    service.start_attempt(connection, 1)

    with pytest.raises(TransitionError):
        service.request_hint(connection, coach, 1, settings)
    with pytest.raises(TransitionError):
        service.submit_code(connection, coach, 1, settings)


def test_une_comprehension_validee_reste_acquise_pour_le_projet(
    connection: sqlite3.Connection, coach: FakeCoach, projects_dir: Path
) -> None:
    _bring_to_coding(connection, coach)
    assert service.validated_understanding(connection, 2) == UNDERSTANDING
    # Les autres projets ne beneficient pas de cette validation.
    assert service.validated_understanding(connection, 1) is None


# --------------------------------------------------------------------------- #
# Indices
# --------------------------------------------------------------------------- #


def test_les_indices_montent_en_palier_et_facturent(
    connection: sqlite3.Connection, coach: FakeCoach, projects_dir: Path, settings: Settings
) -> None:
    _bring_to_coding(connection, coach)

    first = service.request_hint(connection, coach, 2, settings)
    second = service.request_hint(connection, coach, 2, settings)
    third = service.request_hint(connection, coach, 2, settings)

    assert [first["level"], second["level"], third["level"]] == [1, 2, 3]
    assert [first["penalty"], second["penalty"], third["penalty"]] == [0.5, 1.0, 2.0]
    assert third["remaining"] == 0

    with pytest.raises(CoachError, match="paliers"):
        service.request_hint(connection, coach, 2, settings)


# --------------------------------------------------------------------------- #
# Rendu et notation
# --------------------------------------------------------------------------- #


def test_rendu_sans_fichier_python_est_refuse(
    connection: sqlite3.Connection, coach: FakeCoach, projects_dir: Path, settings: Settings
) -> None:
    _bring_to_coding(connection, coach)
    with pytest.raises(CoachError, match="Aucun fichier Python"):
        service.submit_code(connection, coach, 2, settings)


def test_note_sous_le_seuil_impose_une_iteration(
    connection: sqlite3.Connection, coach: FakeCoach, projects_dir: Path, settings: Settings
) -> None:
    _bring_to_coding(connection, coach)
    _write_solution(projects_dir / "day-02-compteur-de-mots")

    review = service.submit_code(connection, coach, 2, settings)

    assert review["total"] == 13.4  # 0.25*16 + 0.20*14 + 0.15*15 + 0.15*12 + 0.15*13 + 0.10*6
    assert review["passed"] is False
    attempt = service.latest_attempt(connection, 2)
    assert attempt is not None
    assert Status(attempt["status"]) is Status.REVIEWED
    assert (projects_dir / "day-02-compteur-de-mots" / "REVIEW-v1.md").is_file()

    iteration = service.start_iteration(connection, 2)
    assert iteration["attempt_no"] == 2
    assert Status(iteration["status"]) is Status.CODING
    # Les axes de la version precedente sont transmis au correcteur suivant.
    assert service.previous_axes(connection, 2, 2) == [
        "Gerer le fichier introuvable (robustesse)",
        "Ajouter des tests (tests_doc)",
    ]


def test_les_indices_consommes_amputent_la_note(
    connection: sqlite3.Connection, coach: FakeCoach, projects_dir: Path, settings: Settings
) -> None:
    _bring_to_coding(connection, coach)
    _write_solution(projects_dir / "day-02-compteur-de-mots")
    service.request_hint(connection, coach, 2, settings)
    service.request_hint(connection, coach, 2, settings)

    review = service.submit_code(connection, coach, 2, settings)
    assert review["raw_total"] == 13.4
    assert review["penalty"] == 1.5
    assert review["total"] == 11.9


def test_note_au_dessus_du_seuil_valide_le_projet(
    connection: sqlite3.Connection, projects_dir: Path, settings: Settings
) -> None:
    coach = GenerousCoach()
    _bring_to_coding(connection, coach)
    _write_solution(projects_dir / "day-02-compteur-de-mots")

    review = service.submit_code(connection, coach, 2, settings)

    assert review["passed"] is True
    attempt = service.latest_attempt(connection, 2)
    assert attempt is not None
    assert Status(attempt["status"]) is Status.VALIDATED

    with pytest.raises(TransitionError):
        service.start_iteration(connection, 2)
    with pytest.raises(TransitionError):
        service.submit_code(connection, coach, 2, settings)


def test_un_projet_valide_sort_de_la_file(
    connection: sqlite3.Connection, projects_dir: Path, settings: Settings
) -> None:
    coach = GenerousCoach()
    assert service.next_project(connection)["id"] == 1  # type: ignore[index]

    _bring_to_coding(connection, coach, project_id=1)
    _write_solution(projects_dir / "day-01-hello-world")
    service.submit_code(connection, coach, 1, settings)

    assert service.next_project(connection)["id"] == 2  # type: ignore[index]
    stats = service.progress(connection)
    assert stats["validated"] == 1
    assert stats["streak"] == 1
    assert stats["average"] == 18.0


def test_project_state_agrege_tout_le_necessaire(
    connection: sqlite3.Connection, coach: FakeCoach, projects_dir: Path, settings: Settings
) -> None:
    _bring_to_coding(connection, coach)
    _write_solution(projects_dir / "day-02-compteur-de-mots")
    service.request_hint(connection, coach, 2, settings)
    service.submit_code(connection, coach, 2, settings)

    state = service.project_state(connection, 2, settings)
    assert state["status"] is Status.REVIEWED
    assert state["brief"]["client_name"] == "Librairie Fontaine"
    assert len(state["hints"]) == 1
    assert state["review"]["total"] == 12.9
    assert state["validated_understanding"] == UNDERSTANDING
    assert any(source.path == "main.py" for source in state["files"])
