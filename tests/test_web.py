"""Couche web : rendu des pages et enchainement POST puis redirection."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import Settings
from app.db import connect
from app.main import app, get_connection
from tests.conftest import FakeCoach

UNDERSTANDING = (
    "Vous voulez un programme qui lit un fichier d'avis clients, compte les occurrences de "
    "chaque mot sans distinguer majuscules et minuscules, et affiche les dix plus frequents."
)


def _connection_factory(db_path: Path) -> Callable[[], Iterator[sqlite3.Connection]]:
    """Une connexion par requete : les routes synchrones tournent dans un pool de threads
    et SQLite interdit de partager une connexion entre threads."""

    def dependency() -> Iterator[sqlite3.Connection]:
        connection = connect(db_path)
        try:
            yield connection
        finally:
            connection.close()

    return dependency


@pytest.fixture
def client(
    db_path: Path,
    settings: Settings,
    coach: FakeCoach,
    projects_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """Client HTTP branche sur la base temporaire et sur le faux coach."""
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "Coach", lambda: coach)
    app.dependency_overrides[get_connection] = _connection_factory(db_path)
    # Pas de gestionnaire de cycle de vie : la base de test est deja amorcee.
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_le_tableau_de_bord_affiche_la_progression(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Un projet par jour" in response.text
    assert "Hello World" in response.text
    assert "Projets valides" in response.text
    assert '<div class="stat__value">0<span class="muted"> / 2</span></div>' in response.text


def test_le_catalogue_liste_tous_les_projets(client: TestClient) -> None:
    response = client.get("/catalogue")
    assert response.status_code == 200
    assert "Compteur de mots" in response.text
    assert "2 projets" in response.text


def test_la_page_projet_propose_de_recevoir_le_brief(client: TestClient) -> None:
    response = client.get("/projet/1")
    assert response.status_code == 200
    assert "Recevoir le brief" in response.text
    # Aucune etape suivante n'est ouverte avant le brief.
    assert "Soumettre au client" not in response.text


def test_un_projet_inconnu_rend_une_page_d_erreur(client: TestClient) -> None:
    response = client.get("/projet/999")
    assert response.status_code == 404
    assert "Projet 999 inconnu" in response.text


def test_recevoir_le_brief_redirige_et_affiche_le_besoin(client: TestClient) -> None:
    redirect = client.post("/projet/1/brief", follow_redirects=False)
    assert redirect.status_code == 303
    assert redirect.headers["location"].startswith("/projet/1?")

    page = client.get(redirect.headers["location"])
    assert "Librairie Fontaine" in page.text
    assert "Brief recu" in page.text
    assert "Soumettre au client" in page.text
    # Les criteres d'acceptation ne fuitent pas dans la page.
    assert "Affiche le top 10" not in page.text


def test_une_reformulation_trop_courte_revient_en_erreur(client: TestClient) -> None:
    client.post("/projet/1/brief")
    redirect = client.post(
        "/projet/1/comprehension", data={"body": "compris"}, follow_redirects=False
    )
    assert redirect.status_code == 303
    assert "kind=error" in redirect.headers["location"]

    page = client.get(redirect.headers["location"])
    assert "flash--error" in page.text
    assert "Soumettre au client" in page.text


def test_le_parcours_complet_passe_par_le_web(
    client: TestClient, projects_dir: Path, coach: FakeCoach
) -> None:
    client.post("/projet/2/brief")
    client.post("/projet/2/comprehension", data={"body": UNDERSTANDING})

    page = client.get("/projet/2")
    assert "Besoin valide" in page.text
    assert "Demander un indice" in page.text

    # Rendre sans code est refuse.
    refus = client.post("/projet/2/rendu", follow_redirects=False)
    assert "kind=error" in refus.headers["location"]

    directory = projects_dir / "day-02-compteur-de-mots"
    (directory / "main.py").write_text("print('ok')\n", encoding="utf-8")

    client.post("/projet/2/indice")
    redirect = client.post("/projet/2/rendu", follow_redirects=False)
    assert "kind=warning" in redirect.headers["location"]  # 12.9/20, sous le seuil

    page = client.get("/projet/2")
    assert "12.9" in page.text
    assert "Gerer le fichier introuvable" in page.text
    assert "Ouvrir la version 2" in page.text
    assert "Indice de palier 1" in page.text


def test_l_iteration_reaffiche_les_axes_a_traiter(client: TestClient, projects_dir: Path) -> None:
    client.post("/projet/2/brief")
    client.post("/projet/2/comprehension", data={"body": UNDERSTANDING})
    (projects_dir / "day-02-compteur-de-mots" / "main.py").write_text("print(1)\n", "utf-8")
    client.post("/projet/2/rendu")
    client.post("/projet/2/iteration")

    page = client.get("/projet/2")
    assert "Axes a traiter dans cette version" in page.text
    assert "version 2" in page.text
    # Les indices de la version precedente ne sont pas reportes.
    assert "Indice de palier" not in page.text


def test_sans_cle_api_les_actions_sont_desactivees(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "get_settings", lambda: Settings(anthropic_api_key=""))
    app.dependency_overrides[get_connection] = _connection_factory(db_path)
    try:
        response = TestClient(app).get("/projet/1")
    finally:
        app.dependency_overrides.clear()

    assert "Aucune cle API Anthropic detectee" in response.text
    assert "disabled" in response.text
