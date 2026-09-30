"""Le calcul de la note reste cote Python : ces regles doivent etre stables."""

from __future__ import annotations

import pytest

from app.scoring import appreciation, final_score, hint_penalty, missing_criteria, weighted_total

PENALTIES = (0.5, 1.0, 2.0)


def test_weighted_total_respecte_les_poids() -> None:
    scores = {
        "conformite": 20.0,
        "structure": 10.0,
        "lisibilite": 10.0,
        "robustesse": 10.0,
        "idiomes": 10.0,
        "tests_doc": 10.0,
    }
    # 0.25 * 20 + 0.75 * 10 = 12.5
    assert weighted_total(scores) == 12.5


def test_weighted_total_ignore_les_criteres_absents() -> None:
    """Une grille incomplete ne doit pas compter les manquants comme des zeros."""
    assert weighted_total({"conformite": 18.0}) == 18.0
    assert weighted_total({}) == 0.0


def test_weighted_total_ignore_les_cles_inconnues() -> None:
    assert weighted_total({"conformite": 12.0, "inconnu": 0.0}) == 12.0


@pytest.mark.parametrize(
    ("levels", "expected"),
    [([], 0.0), ([1], 0.5), ([1, 2], 1.5), ([1, 2, 3], 3.5), ([1, 2, 3, 3, 3], 4.0)],
)
def test_hint_penalty_cumule_et_plafonne(levels: list[int], expected: float) -> None:
    assert hint_penalty(levels, PENALTIES) == expected


def test_final_score_applique_le_malus_sans_passer_sous_zero() -> None:
    scores = dict.fromkeys(
        ("conformite", "structure", "lisibilite", "robustesse", "idiomes", "tests_doc"), 2.0
    )
    raw, penalty, total = final_score(scores, [1, 2, 3], PENALTIES)
    assert (raw, penalty) == (2.0, 3.5)
    assert total == 0.0


def test_final_score_sans_indice_est_la_note_brute() -> None:
    scores = dict.fromkeys(
        ("conformite", "structure", "lisibilite", "robustesse", "idiomes", "tests_doc"), 15.0
    )
    raw, penalty, total = final_score(scores, [], PENALTIES)
    assert (raw, penalty, total) == (15.0, 0.0, 15.0)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (20.0, "Niveau professionnel"),
        (14.0, "Solide, quelques finitions"),
        (11.0, "Fonctionnel, conception a retravailler"),
        (8.0, "Le besoin est couvert partiellement"),
        (0.0, "A reprendre en profondeur"),
    ],
)
def test_appreciation_couvre_toute_l_echelle(score: float, expected: str) -> None:
    assert appreciation(score) == expected


def test_missing_criteria_liste_les_trous() -> None:
    assert missing_criteria({"conformite": 10.0}) == [
        "structure",
        "lisibilite",
        "robustesse",
        "idiomes",
        "tests_doc",
    ]
