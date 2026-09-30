"""Lecture de la configuration depuis un vrai fichier .env.

Ces tests existent parce que le format documente `HINT_PENALTIES=0.5,1.0,2.0`
echouait : pydantic-settings tentait un json.loads sur la valeur brute avant
d'appeler le validateur. Un reglage qui ne se lit pas depuis .env n'est pas
un reglage.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings


def _write_env(tmp_path: Path, body: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(body, encoding="utf-8")
    return path


def _settings(env: Path | None, api_key: str | None = None) -> Settings:
    """Construit les reglages en pointant un .env choisi.

    `_env_file` est un parametre reel de pydantic-settings, absent de l'`__init__`
    synthetise que voit mypy : d'ou les exemptions, cantonnees ici. La cle n'est
    passee que si le test la fournit : un argument explicite prime sur le .env et
    masquerait la valeur qu'on veut justement verifier.
    """
    if api_key is None:
        return Settings(_env_file=env)  # type: ignore[call-arg]
    return Settings(_env_file=env, anthropic_api_key=api_key)  # type: ignore[call-arg]


def test_les_reglages_se_lisent_depuis_un_fichier_env(tmp_path: Path) -> None:
    env = _write_env(
        tmp_path,
        "ANTHROPIC_API_KEY=une-cle\n"
        "COACH_MODEL=claude-opus-5\n"
        "PASS_THRESHOLD=12.5\n"
        "HINT_PENALTIES=0.25,0.75,1.5\n"
        "GIT_REMOTE=git@github.com:moi/mon-depot.git\n"
        "GIT_BRANCH=main\n",
    )
    settings = _settings(env)

    assert settings.hint_penalties == (0.25, 0.75, 1.5)
    assert settings.pass_threshold == 12.5
    assert settings.coach_model == "claude-opus-5"
    assert settings.git_remote == "git@github.com:moi/mon-depot.git"
    assert settings.llm_ready is True


def test_les_malus_acceptent_les_espaces(tmp_path: Path) -> None:
    settings = _settings(_write_env(tmp_path, "HINT_PENALTIES= 1 , 2 , 3 \n"))
    assert settings.hint_penalties == (1.0, 2.0, 3.0)


def test_un_env_vide_garde_les_defauts(tmp_path: Path) -> None:
    settings = _settings(_write_env(tmp_path, "ANTHROPIC_API_KEY=\n"))
    assert settings.hint_penalties == (0.5, 1.0, 2.0)
    assert settings.pass_threshold == 14.0
    assert settings.coach_model == "claude-sonnet-5"
    assert settings.git_remote == ""
    assert settings.llm_ready is False


def test_une_cle_faite_d_espaces_ne_compte_pas(tmp_path: Path) -> None:
    settings = _settings(_write_env(tmp_path, "ANTHROPIC_API_KEY=   \n"))
    assert settings.llm_ready is False


@pytest.mark.parametrize("valeur", ["0.5,1.0", "0.5,1.0,2.0,3.0", "beaucoup,un,peu"])
def test_un_malus_mal_forme_est_rejete_au_demarrage(tmp_path: Path, valeur: str) -> None:
    """Mieux vaut un echec au demarrage qu'un bareme silencieusement faux."""
    with pytest.raises(ValidationError):
        _settings(_write_env(tmp_path, f"HINT_PENALTIES={valeur}\n"))


def test_un_seuil_hors_bareme_est_rejete(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        _settings(_write_env(tmp_path, "PASS_THRESHOLD=25\n"))


@pytest.mark.parametrize(
    ("level", "expected"), [(1, 0.5), (2, 1.0), (3, 2.0), (0, 0.0), (4, 0.0), (-1, 0.0)]
)
def test_penalty_for_level_borne_les_paliers(level: int, expected: float) -> None:
    # _env_file=None : ce test porte sur les defauts, pas sur le .env de la machine.
    settings = _settings(None, api_key="x")
    assert settings.penalty_for_level(level) == expected
