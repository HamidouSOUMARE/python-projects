# Coach Python — conventions du projet

App FastAPI qui transforme les projets de `python-mini-projects` en missions client :
brief, validation de la comprehension, realisation, notation, iteration.
Voir [README.md](./README.md) pour la boucle complete et la grille.

## Deux zones distinctes

- `app/`, `tests/`, `scripts/` : **le code de l'app**. Standards pro, mypy strict, tests.
- `projects/day-NN-slug/` : **les exercices de l'utilisateur**. Ne jamais y ecrire de code
  a sa place, ne jamais corriger un de ses fichiers, ne jamais y proposer de solution.
  C'est le materiel note : le modifier viderait l'exercice de son sens.

Seul `BRIEF.md` est ecrit par l'app dans ces dossiers (reecrit a chaque validation), ainsi
que `REVIEW-vN.md` (une par version notee). `README.md` d'un projet appartient a
l'utilisateur : il est cree vide une fois, jamais ecrase.

## Regles d'architecture

- Toute transition d'etat passe par `service._set_status`, qui verifie
  `models.TRANSITIONS`. Ne jamais faire un `UPDATE attempts SET status` ailleurs.
- La note finale est calculee dans `scoring.py`, jamais par le modele. Le modele note
  chaque critere ; la ponderation, le malus et le seuil restent en Python.
- Les criteres d'acceptation d'un brief sont **caches** a l'utilisateur. Ils vont dans
  `service.brief_block` (envoye au modele) et surtout pas dans `service.brief_markdown`
  (ecrit sur disque) ni dans un template.
- Les appels au modele sont forces sur un outil (`tool_choice`), donc la sortie est
  structuree. Pas de parsing de texte libre.
- `service` depend de `llm.CoachProtocol`, pas de `llm.Coach` : les tests jouent le
  parcours complet sans reseau (`tests/conftest.py::FakeCoach`).
- Un prompt modifie change la pedagogie : c'est la partie la plus sensible du projet.
  Relire `prompts.py` en entier avant d'y toucher, notamment les paliers d'indices, qui ne
  doivent jamais se depasser.

## Web

- POST puis redirection (303) pour toute action : un rafraichissement ne doit jamais
  rejouer un appel API facture.
- Les erreurs metier sont des `CoachError` remontees en message flash, jamais une 500.
- Une connexion SQLite par requete (dependance `get_connection`) : les routes synchrones
  tournent dans un pool de threads et SQLite interdit de partager une connexion.

## Style

- Design : toute valeur visuelle vient de `static/tokens.css`. Aucune couleur, taille ou
  espacement en dur dans `app.css` ou les templates.
- Interface et contenu en francais.
- Python : annotations aux frontieres, `from __future__ import annotations`, pas de `catch`
  muet. Lignes a 100 colonnes.

## Avant d'annoncer qu'une tache est finie

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy app scripts tests
```
