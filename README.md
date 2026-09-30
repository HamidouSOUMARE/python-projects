# Coach Python

Un projet par jour, **compris avant d'etre code**, note apres, refait jusqu'a la note visee.

L'app prend les 101 projets de
[Python-World/python-mini-projects](https://github.com/Python-World/python-mini-projects)
et les transforme en missions client. Le sujet n'est jamais donne comme un exercice : un
client decrit un probleme metier, et c'est a toi de faire apparaitre le besoin reel.

## Deux modes

**Mode libre** (`/libre`) — le sujet, ton code, un bouton pour lancer. Tu choisis un projet,
l'app cree le dossier avec un `main.py` de depart, tu codes dans ton editeur, puis tu lances
le programme (avec arguments et entree standard si besoin) ou tes tests depuis la page. La
sortie s'affiche telle quelle. **Aucun appel a l'API, aucune cle necessaire.**

**Mode coache** (`/projet/{id}`) — la boucle complete ci-dessous : un client formule un besoin,
valide ta comprehension avant que tu codes, puis note ton rendu et te donne des axes. Necessite
une cle API.

Les deux modes partagent le meme dossier `projects/day-NN-slug/` : commencer en libre puis
passer en coache sur le meme projet ne perd rien.

## La boucle du mode coache

```
1. BRIEF          Le client depose son besoin. Aucune indication technique.
                  Ses criteres d'acceptation restent caches.
        v
2. COMPREHENSION  Tu reformules ce que tu as comprise. Le client valide, relance
                  ou signale le hors-sujet.  <-- verrou : pas de code avant validation
        v
3. REALISATION    Tu codes dans projects/day-NN-slug/.
                  Bouton indice : 3 paliers, chacun facture en points.
        v
4. RENDU          Commit + push, puis notation sur 6 criteres.
        v
5. REVUE          Note /20, points forts, axes d'amelioration classes par priorite.
                  >= seuil : projet valide, on passe au suivant.
                  <  seuil : nouvelle version, les axes deviennent ton cahier des charges.
```

Le brief est genere **une seule fois par projet** et ne change jamais : deux versions du meme
projet sont donc comparables. La comprehension validee reste acquise — une nouvelle version
repart directement en realisation.

## Grille de notation

| Critere | Poids | Ce qui est regarde |
| --- | --- | --- |
| Conformite au besoin | 25 % | Les criteres d'acceptation du client, rien d'autre |
| Structure et conception | 20 % | Decoupage, responsabilites, pas de fonction fourre-tout |
| Lisibilite et style | 15 % | PEP 8, nommage, code mort, commentaires utiles |
| Robustesse | 15 % | Erreurs gerees, entrees validees, cas limites |
| Idiomatismes Python | 15 % | Comprehensions, context managers, stdlib, annotations |
| Tests et documentation | 10 % | Tests pertinents, README, docstrings |

La note ponderee est calculee cote Python, pas par le modele. Les indices consommes sont
deduits : −0,5 / −1 / −2 points selon le palier, plafonnes a −4.

## Installation

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
cp .env.example .env     # puis renseigne ANTHROPIC_API_KEY
```

Cle API : <https://console.anthropic.com/settings/keys>. Sans elle, l'app demarre et affiche
la progression, mais le client ne peut ni valider une comprehension ni noter du code.

## Lancer

```bash
.venv/bin/uvicorn app.main:app --reload
```

Puis <http://127.0.0.1:8000>.

## Configuration (`.env`)

| Variable | Defaut | Role |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | — | Cle API. Jamais commitee. |
| `COACH_MODEL` | `claude-sonnet-5` | Modele utilise pour les quatre roles. |
| `PASS_THRESHOLD` | `14.0` | Note minimale pour valider un projet. |
| `HINT_PENALTIES` | `0.5,1.0,2.0` | Malus par palier d'indice. |
| `GIT_REMOTE` | vide | Remote du monorepo. Vide = commit local seulement. |
| `GIT_BRANCH` | `main` | Branche poussee. |

## Pousser sur GitHub

Cree un depot vide sur GitHub, puis renseigne son URL dans `GIT_REMOTE` :

```bash
# .env
GIT_REMOTE=git@github.com:<toi>/python-100-days.git
```

Au premier rendu, l'app initialise le depot si besoin, commite le dossier du projet et pousse.
Sans remote, le commit local est fait quand meme : l'historique de progression reste intact.

## Commandes

```bash
.venv/bin/python -m pytest              # tests
.venv/bin/ruff check . && .venv/bin/ruff format .   # lint et format
.venv/bin/mypy app scripts tests        # types (strict)
python scripts/build_catalog.py         # reconstruire data/catalog.json depuis GitHub
```

## Organisation

```
app/
  config.py      Reglages (env / .env), chemins
  models.py      Etats, transitions autorisees, grille de criteres
  runner.py      Execution du code en mode libre (sous-processus, sans shell)
  db.py          SQLite : connexion, schema, amorcage du catalogue
  schema.sql     Schema
  prompts.py     Les 4 prompts et leurs schemas d'outils
  llm.py         Client Claude (sortie forcee sur un outil) + CoachProtocol
  workspace.py   Lecture du rendu dans projects/
  gitops.py      Commit et push
  service.py     Orchestration et machine a etats
  main.py        Routes FastAPI
  templates/     Jinja2
  static/        tokens.css (design tokens) + app.css
data/
  catalog.json   Les 101 projets, ordonnes par difficulte
  coach.db       Base locale (non commitee)
projects/
  day-NN-slug/   Ton code, BRIEF.md, REVIEW-vN.md
scripts/
  build_catalog.py
```

## Cout

Quatre appels par projet en moyenne (brief, validation, rendu, plus les indices). Avec
`claude-sonnet-5`, l'ordre de grandeur est de quelques centimes par projet — la notation est
l'appel le plus lourd puisqu'elle lit tout le code rendu.
