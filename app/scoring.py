"""Calcul des notes. Le LLM note chaque critere, le total est calcule ici."""

from __future__ import annotations

from app.models import CRITERIA, CRITERIA_BY_KEY

APPRECIATIONS: tuple[tuple[float, str], ...] = (
    (17.0, "Niveau professionnel"),
    (14.0, "Solide, quelques finitions"),
    (11.0, "Fonctionnel, conception a retravailler"),
    (8.0, "Le besoin est couvert partiellement"),
    (0.0, "A reprendre en profondeur"),
)


def weighted_total(scores: dict[str, float]) -> float:
    """Moyenne ponderee des criteres presents, ramenee sur 20.

    Les criteres absents sont ignores plutot que comptes zero : une grille
    incomplete ne doit pas sanctionner le code.
    """
    known = {key: value for key, value in scores.items() if key in CRITERIA_BY_KEY}
    if not known:
        return 0.0
    total_weight = sum(CRITERIA_BY_KEY[key].weight for key in known)
    weighted = sum(CRITERIA_BY_KEY[key].weight * value for key, value in known.items())
    return round(weighted / total_weight, 2)


def hint_penalty(levels: list[int], penalties: tuple[float, ...]) -> float:
    """Malus cumule des indices consommes, plafonne a 4 points."""
    total = sum(penalties[level - 1] for level in levels if 1 <= level <= len(penalties))
    return round(min(total, 4.0), 2)


def final_score(
    scores: dict[str, float], levels: list[int], penalties: tuple[float, ...]
) -> tuple[float, float, float]:
    """Retourne (note brute, malus, note finale) - toutes sur 20."""
    raw = weighted_total(scores)
    penalty = hint_penalty(levels, penalties)
    return raw, penalty, round(max(raw - penalty, 0.0), 2)


def appreciation(score: float) -> str:
    return next(label for threshold, label in APPRECIATIONS if score >= threshold)


def missing_criteria(scores: dict[str, float]) -> list[str]:
    return [criterion.key for criterion in CRITERIA if criterion.key not in scores]
