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

## Les deux modes

`/libre` (mode libre) n'appelle jamais l'API : sujet, squelette, execution, tests. `/projet/{id}`
(mode coache) fait la boucle complete avec le client. Les deux ecrivent dans le meme dossier
`projects/day-NN-slug/`. Une page du mode libre passe `needs_llm=False` : le bandeau
d'avertissement sur la cle API ne doit pas y apparaitre.

## Execution du code de l'utilisateur (`runner.py`)

- Jamais de shell. Les arguments passent par `shlex.split` puis une liste `argv`, ce qui rend
  `; rm ...` inoffensif. Un test verrouille ce comportement.
- `child_env()` retire les variables du coach (`ANTHROPIC_*`, `COACH_*`, ...) : le code d'un
  exercice ne doit jamais voir la cle API.
- Le point d'entree est un nom de fichier `.py` du dossier du projet, jamais un chemin : pas de
  remontee d'arborescence.
- Timeout obligatoire, sortie tronquee. Un plantage du code de l'utilisateur n'est pas une
  erreur de l'app : il remonte dans `RunResult.stderr`, pas en exception.
- Les routes du mode libre rendent la page directement au lieu de rediriger : la sortie doit
  rester visible, et rejouer un lancement local ne coute rien (contrairement au mode coache).

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
