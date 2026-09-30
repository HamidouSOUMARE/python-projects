"""Types du domaine : etats d'une tentative et criteres de notation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Status(StrEnum):
    """Etats possibles d'une tentative de projet.

    Le passage BRIEFED -> CODING n'est franchissable que si la comprehension
    du besoin a ete validee : c'est le verrou central du dispositif.
    """

    BRIEFED = "briefed"
    UNDERSTANDING_REJECTED = "understanding_rejected"
    CODING = "coding"
    REVIEWED = "reviewed"
    VALIDATED = "validated"


#: Transitions autorisees. Toute autre transition leve une erreur.
TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.BRIEFED: frozenset({Status.CODING, Status.UNDERSTANDING_REJECTED}),
    Status.UNDERSTANDING_REJECTED: frozenset({Status.CODING, Status.UNDERSTANDING_REJECTED}),
    Status.CODING: frozenset({Status.REVIEWED, Status.VALIDATED}),
    Status.REVIEWED: frozenset({Status.CODING, Status.VALIDATED}),
    Status.VALIDATED: frozenset(),
}

STATUS_LABELS: dict[Status, str] = {
    Status.BRIEFED: "Brief recu",
    Status.UNDERSTANDING_REJECTED: "Comprehension a preciser",
    Status.CODING: "Besoin valide - en cours de realisation",
    Status.REVIEWED: "Note - a ameliorer",
    Status.VALIDATED: "Valide",
}


@dataclass(frozen=True, slots=True)
class Criterion:
    key: str
    label: str
    weight: float
    description: str


#: Grille de notation. Chaque critere est note de 0 a 20, le total est pondere.
CRITERIA: tuple[Criterion, ...] = (
    Criterion(
        "conformite",
        "Conformite au besoin",
        0.25,
        "Le programme repond-il a ce que le client a demande, sans oubli ni hors-sujet ?",
    ),
    Criterion(
        "structure",
        "Structure et conception",
        0.20,
        "Decoupage en fonctions, responsabilites claires, pas de fonction fourre-tout.",
    ),
    Criterion(
        "lisibilite",
        "Lisibilite et style",
        0.15,
        "PEP 8, nommage explicite, absence de code mort, commentaires utiles.",
    ),
    Criterion(
        "robustesse",
        "Robustesse",
        0.15,
        "Gestion des erreurs, validation des entrees, cas limites traites.",
    ),
    Criterion(
        "idiomes",
        "Idiomatismes Python",
        0.15,
        "Comprehensions, context managers, bibliotheque standard, annotations de type.",
    ),
    Criterion(
        "tests_doc",
        "Tests et documentation",
        0.10,
        "Tests pertinents, README ou docstrings expliquant l'usage.",
    ),
)

CRITERIA_BY_KEY: dict[str, Criterion] = {criterion.key: criterion for criterion in CRITERIA}

HINT_LABELS: dict[int, str] = {
    1: "Question orientante",
    2: "Piste d'approche",
    3: "Extrait de code",
}


class CoachError(RuntimeError):
    """Erreur metier destinee a etre affichee a l'utilisateur."""


class TransitionError(CoachError):
    """Transition d'etat interdite par la machine a etats."""
