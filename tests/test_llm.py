"""Assainissement des reponses du modele.

Ces tests existent parce qu'un appel reel a renvoye un brief sans le champ
`constraints`, pourtant declare `required` dans le schema de l'outil. Le
`required` d'un schema n'est pas une garantie dure : la sortie du modele est
une entree externe, donc validee avant d'entrer dans le domaine.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.llm import normalize_brief
from app.models import CoachError

VALID: dict[str, Any] = {
    "client_name": "Librairie Le Marque-Page",
    "context_md": "Je gere une librairie independante.",
    "need_md": "Je veux analyser mes fichiers texte.",
    "constraints": ["Doit tourner sur mon portable"],
    "acceptance": [
        {"id": "ac1", "label": "Compte les mots", "critical": True},
        {"id": "ac2", "label": "Ignore la casse", "critical": False},
    ],
}


def test_un_brief_complet_traverse_sans_alteration() -> None:
    assert normalize_brief(dict(VALID)) == VALID


def test_un_brief_sans_contraintes_reste_exploitable() -> None:
    """Le cas rencontre en vrai : le modele omet la cle `constraints`."""
    payload = {key: value for key, value in VALID.items() if key != "constraints"}
    assert normalize_brief(payload)["constraints"] == []


def test_les_contraintes_vides_sont_ecartees() -> None:
    payload = dict(VALID, constraints=["Delai court", "  ", ""])
    assert normalize_brief(payload)["constraints"] == ["Delai court"]


def test_les_contraintes_mal_typees_sont_ignorees() -> None:
    assert normalize_brief(dict(VALID, constraints="pas une liste"))["constraints"] == []


@pytest.mark.parametrize("champ", ["client_name", "context_md", "need_md"])
def test_un_champ_essentiel_manquant_est_une_erreur_lisible(champ: str) -> None:
    payload = {key: value for key, value in VALID.items() if key != champ}
    with pytest.raises(CoachError, match=champ):
        normalize_brief(payload)


@pytest.mark.parametrize("champ", ["client_name", "context_md", "need_md"])
def test_un_champ_essentiel_vide_vaut_absent(champ: str) -> None:
    with pytest.raises(CoachError, match=champ):
        normalize_brief(dict(VALID, **{champ: "   "}))


def test_un_brief_sans_critere_est_refuse() -> None:
    with pytest.raises(CoachError, match="critere d'acceptation"):
        normalize_brief(dict(VALID, acceptance=[]))


def test_un_brief_dont_les_criteres_sont_mal_typees_est_refuse() -> None:
    with pytest.raises(CoachError, match="critere d'acceptation"):
        normalize_brief(dict(VALID, acceptance="ac1, ac2"))


def test_les_criteres_sans_enonce_sont_ecartes() -> None:
    payload = dict(
        VALID,
        acceptance=[
            {"id": "ac1", "label": "Compte les mots", "critical": True},
            {"id": "ac2", "label": "   "},
            "pas un objet",
        ],
    )
    acceptance = normalize_brief(payload)["acceptance"]
    assert [item["label"] for item in acceptance] == ["Compte les mots"]


def test_un_critere_sans_identifiant_en_recoit_un() -> None:
    payload = dict(VALID, acceptance=[{"label": "Compte les mots"}])
    assert normalize_brief(payload)["acceptance"] == [
        {"id": "ac1", "label": "Compte les mots", "critical": False}
    ]


def test_le_caractere_critique_est_toujours_un_booleen() -> None:
    payload = dict(VALID, acceptance=[{"id": "ac1", "label": "Compte", "critical": "oui"}])
    assert normalize_brief(payload)["acceptance"][0]["critical"] is True


def test_les_champs_inattendus_sont_ecartes() -> None:
    """Le brief entrant dans le domaine a une forme connue, et seulement celle-la."""
    assert set(normalize_brief(dict(VALID, bonus="ignore-moi"))) == set(VALID)
