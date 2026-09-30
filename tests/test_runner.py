"""Execution du code de l'utilisateur en mode libre."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.models import CoachError
from app.runner import (
    MASKED_ENV_PREFIXES,
    child_env,
    entrypoints,
    has_tests,
    run_script,
    run_tests,
)


@pytest.fixture
def projet(tmp_path: Path) -> Path:
    directory = tmp_path / "day-01-demo"
    directory.mkdir()
    return directory


def _script(directory: Path, name: str, body: str) -> None:
    (directory / name).write_text(body, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Execution nominale
# --------------------------------------------------------------------------- #


def test_un_script_qui_marche_est_signale_comme_reussi(projet: Path) -> None:
    _script(projet, "main.py", "print('bonjour')\n")
    result = run_script(projet)

    assert result.ok is True
    assert result.returncode == 0
    assert result.stdout.strip() == "bonjour"
    assert result.timed_out is False


def test_une_erreur_python_remonte_la_trace_sans_lever(projet: Path) -> None:
    """Un plantage du code de l'utilisateur n'est pas une erreur de l'app."""
    _script(projet, "main.py", "raise ValueError('cassé')\n")
    result = run_script(projet)

    assert result.ok is False
    assert result.returncode == 1
    assert "ValueError" in result.stderr


def test_les_arguments_sont_transmis_au_script(projet: Path) -> None:
    _script(projet, "main.py", "import sys\nprint(sys.argv[1:])\n")
    result = run_script(projet, args="avis.txt 10")
    assert "['avis.txt', '10']" in result.stdout


def test_un_argument_entre_guillemets_reste_entier(projet: Path) -> None:
    _script(projet, "main.py", "import sys\nprint(sys.argv[1])\n")
    result = run_script(projet, args='"mon fichier.txt"')
    assert result.stdout.strip() == "mon fichier.txt"


def test_un_guillemet_non_ferme_est_refuse_avec_un_message_clair(projet: Path) -> None:
    _script(projet, "main.py", "print(1)\n")
    with pytest.raises(CoachError, match="Arguments illisibles"):
        run_script(projet, args='"oups')


def test_l_entree_standard_est_fournie_au_script(projet: Path) -> None:
    _script(projet, "main.py", "nom = input()\nprint(f'salut {nom}')\n")
    result = run_script(projet, stdin_text="Hamidou\n")
    assert result.stdout.strip() == "salut Hamidou"


def test_les_arguments_ne_passent_pas_par_un_shell(projet: Path) -> None:
    """`; rm` doit arriver au script comme une chaine, pas etre interprete."""
    _script(projet, "main.py", "import sys\nprint(sys.argv[1:])\n")
    temoin = projet / "temoin.txt"
    temoin.write_text("intact", encoding="utf-8")

    result = run_script(projet, args="'; rm temoin.txt'")

    assert temoin.read_text(encoding="utf-8") == "intact"
    assert "; rm temoin.txt" in result.stdout


def test_un_script_sans_sortie_est_signale(projet: Path) -> None:
    _script(projet, "main.py", "x = 1\n")
    result = run_script(projet)
    assert result.ok is True
    assert result.silent is True


def test_le_script_tourne_dans_le_dossier_du_projet(projet: Path) -> None:
    """Un chemin relatif dans le code de l'utilisateur doit viser son dossier."""
    (projet / "donnees.txt").write_text("contenu", encoding="utf-8")
    _script(projet, "main.py", "print(open('donnees.txt').read())\n")
    assert run_script(projet).stdout.strip() == "contenu"


# --------------------------------------------------------------------------- #
# Garde-fous
# --------------------------------------------------------------------------- #


def test_une_boucle_infinie_est_interrompue(projet: Path) -> None:
    _script(projet, "main.py", "while True:\n    pass\n")
    result = run_script(projet, timeout=1)

    assert result.timed_out is True
    assert result.ok is False
    assert result.returncode is None


def test_une_attente_de_saisie_sans_entree_est_interrompue(projet: Path) -> None:
    _script(projet, "main.py", "input('ton nom ? ')\n")
    result = run_script(projet, timeout=1)
    # Sans entree fournie, input() leve EOFError et le script s'arrete.
    assert result.timed_out is False
    assert result.ok is False


def test_une_sortie_demesuree_est_tronquee(projet: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.runner.MAX_OUTPUT_CHARS", 100)
    _script(projet, "main.py", "print('x' * 5000)\n")
    result = run_script(projet)
    assert "sortie tronquee" in result.stdout
    assert len(result.stdout) < 200


def test_un_point_d_entree_hors_du_dossier_est_refuse(projet: Path) -> None:
    """Aucune remontee d'arborescence : le script doit etre dans le dossier."""
    with pytest.raises(CoachError, match="fichier .py du dossier"):
        run_script(projet, entrypoint="../../secrets.py")


def test_un_fichier_non_python_est_refuse(projet: Path) -> None:
    (projet / "notes.txt").write_text("rien", encoding="utf-8")
    with pytest.raises(CoachError, match="fichier .py du dossier"):
        run_script(projet, entrypoint="notes.txt")


def test_un_point_d_entree_absent_est_signale(projet: Path) -> None:
    with pytest.raises(CoachError, match="introuvable"):
        run_script(projet, entrypoint="absent.py")


def test_un_dossier_absent_est_signale(tmp_path: Path) -> None:
    with pytest.raises(CoachError, match="n'existe pas encore"):
        run_script(tmp_path / "nulle-part")


def test_la_cle_api_est_masquee_au_code_de_l_utilisateur(
    projet: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un exercice n'a aucune raison de voir la cle du coach."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-a-ne-pas-fuiter")
    monkeypatch.setenv("COACH_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("CHEMIN_NEUTRE", "visible")

    _script(
        projet,
        "main.py",
        "import os\nprint(sorted(k for k in os.environ if 'ANTHROPIC' in k or 'COACH' in k))\n"
        "print(os.environ.get('CHEMIN_NEUTRE'))\n",
    )
    result = run_script(projet)

    assert result.stdout.splitlines()[0] == "[]"
    assert result.stdout.splitlines()[1] == "visible"
    assert "secret-a-ne-pas-fuiter" not in result.stdout


def test_child_env_masque_les_prefixes_du_coach(monkeypatch: pytest.MonkeyPatch) -> None:
    for prefix in MASKED_ENV_PREFIXES:
        monkeypatch.setenv(f"{prefix}TEST", "x")
    env = child_env()
    assert not [key for key in env if key.startswith(MASKED_ENV_PREFIXES)]
    assert env["PYTHONUNBUFFERED"] == "1"
    assert "PATH" in env or "PATH" not in os.environ


# --------------------------------------------------------------------------- #
# Points d'entree et tests
# --------------------------------------------------------------------------- #


def test_entrypoints_met_main_en_premier_et_ecarte_les_tests(projet: Path) -> None:
    for name in ("zebre.py", "main.py", "test_main.py", "alpha.py"):
        _script(projet, name, "")
    assert entrypoints(projet) == ["main.py", "alpha.py", "zebre.py"]


def test_entrypoints_sur_dossier_absent_est_vide(tmp_path: Path) -> None:
    assert entrypoints(tmp_path / "nulle-part") == []


def test_has_tests_reconnait_les_deux_emplacements(projet: Path) -> None:
    assert has_tests(projet) is False
    _script(projet, "test_main.py", "")
    assert has_tests(projet) is True

    autre = projet.parent / "day-02-demo"
    (autre / "tests").mkdir(parents=True)
    assert has_tests(autre) is False
    _script(autre / "tests", "test_x.py", "")
    assert has_tests(autre) is True


def test_les_tests_qui_passent_sont_signales(projet: Path) -> None:
    _script(projet, "main.py", "def double(n):\n    return n * 2\n")
    _script(
        projet,
        "test_main.py",
        "from main import double\n\n\ndef test_double():\n    assert double(2) == 4\n",
    )
    result = run_tests(projet, timeout=60)
    assert result.ok is True
    assert "1 passed" in result.stdout


def test_un_test_qui_echoue_remonte_le_detail(projet: Path) -> None:
    _script(projet, "main.py", "def double(n):\n    return n * 3\n")
    _script(
        projet,
        "test_main.py",
        "from main import double\n\n\ndef test_double():\n    assert double(2) == 4\n",
    )
    result = run_tests(projet, timeout=60)
    assert result.ok is False
    assert "1 failed" in result.stdout


def test_lancer_les_tests_sans_test_donne_une_consigne(projet: Path) -> None:
    _script(projet, "main.py", "print(1)\n")
    with pytest.raises(CoachError, match="test_quelquechose.py"):
        run_tests(projet)
