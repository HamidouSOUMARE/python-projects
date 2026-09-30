"""Prompts et schemas d'outils du coach.

Chaque appel au modele est force sur un outil : la sortie est donc toujours
structuree, jamais du texte libre a parser.
"""

from __future__ import annotations

from typing import Any

from app.models import CRITERIA

# --------------------------------------------------------------------------- #
# 1. Generation du brief client
# --------------------------------------------------------------------------- #

BRIEF_SYSTEM = """Tu es un client qui commande un petit programme Python a un prestataire.

Tu n'es pas developpeur. Tu decris un besoin metier, jamais une solution technique :
tu ne cites ni bibliotheque, ni nom de fonction, ni structure de donnees.

Ton brief doit etre realiste : un client parle de son probleme, de son contexte et
de ce qu'il veut obtenir. Il laisse naturellement quelques zones a clarifier
(format d'entree, comportement en cas d'erreur, cas limite), mais RIEN d'arbitraire :
chaque critere d'acceptation doit etre deductible du besoin exprime par un
prestataire attentif. Aucune exigence surprise.

Ecris en francais, a la premiere personne, ton professionnel et direct."""

BRIEF_TOOL: dict[str, Any] = {
    "name": "deposer_brief",
    "description": "Depose le brief client pour le projet demande.",
    "input_schema": {
        "type": "object",
        "properties": {
            "client_name": {
                "type": "string",
                "description": (
                    "Nom de l'entreprise ou du service qui commande (invente, credible)."
                ),
            },
            "context_md": {
                "type": "string",
                "description": (
                    "2 a 4 phrases de contexte : qui je suis, quel probleme je vis aujourd'hui."
                ),
            },
            "need_md": {
                "type": "string",
                "description": (
                    "Le besoin exprime, en markdown, 100 a 200 mots. Ce que je veux obtenir "
                    "et pourquoi. Aucune indication technique."
                ),
            },
            "constraints": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "2 a 4 contraintes exprimees en langage client "
                    "(delai, volume, environnement, budget)."
                ),
            },
            "acceptance": {
                "type": "array",
                "minItems": 4,
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Identifiant court, ex: ac1."},
                        "label": {
                            "type": "string",
                            "description": "Le critere, formule comme un resultat observable.",
                        },
                        "critical": {
                            "type": "boolean",
                            "description": "Vrai si le besoin n'est pas rempli sans ce critere.",
                        },
                    },
                    "required": ["id", "label", "critical"],
                },
                "description": (
                    "Criteres d'acceptation caches au prestataire. Ils servent a juger sa "
                    "comprehension puis son code. Chacun doit etre deductible du besoin exprime."
                ),
            },
        },
        "required": ["client_name", "context_md", "need_md", "constraints", "acceptance"],
    },
}


def brief_user_prompt(title: str, theme: str, difficulty: int, source_url: str) -> str:
    return f"""Commande un programme correspondant a ce sujet.

Sujet technique (pour toi seulement, ne le recopie pas tel quel) : {title}
Theme : {theme} - Niveau de complexite attendu : {difficulty}/4
Reference : {source_url}

Transforme ce sujet en un vrai besoin client : donne-lui un contexte metier concret,
des enjeux, et exprime-le comme un probleme a resoudre, pas comme un exercice."""


# --------------------------------------------------------------------------- #
# 2. Validation de la comprehension
# --------------------------------------------------------------------------- #

UNDERSTANDING_SYSTEM = """Tu es le client qui a depose un brief. Le prestataire te renvoie
sa comprehension du besoin avant de commencer. Tu dois lui repondre.

Ton role : verifier qu'il a compris le BESOIN, pas qu'il a devine une solution technique.
- Ne juge jamais les choix techniques qu'il mentionne, meme maladroits : ce n'est pas ton sujet.
- Si un point du besoin est absent ou mal interprete, tu le relances par une question ou une
  precision de client. Tu ne donnes JAMAIS la reponse technique ni la marche a suivre.
- S'il a invente des fonctionnalites que tu n'as pas demandees, signale-le : le hors-sujet
  coute du temps.
- Sois exigeant mais juste. Un prestataire qui a couvert tous tes criteres critiques sans
  contresens est valide, meme si sa formulation est imparfaite.

Reponds en francais, ton client : direct, concret, jamais professoral."""

UNDERSTANDING_TOOL: dict[str, Any] = {
    "name": "rendre_verdict",
    "description": "Repond au prestataire sur sa comprehension du besoin.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["valide", "a_preciser"],
                "description": (
                    "'valide' si tous les criteres critiques sont couverts et sans contresens. "
                    "'a_preciser' sinon."
                ),
            },
            "coverage": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Pourcentage des criteres d'acceptation reellement couverts.",
            },
            "summary_md": {
                "type": "string",
                "description": "Ta reponse au prestataire, 2 a 4 phrases, ton client.",
            },
            "confirmed": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Les points qu'il a bien compris, formules brievement.",
            },
            "gaps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "point": {
                            "type": "string",
                            "description": "Ce qui manque ou ce qui est mal compris.",
                        },
                        "relance": {
                            "type": "string",
                            "description": (
                                "Ta question ou precision de client. Elle oriente sans donner "
                                "la solution technique."
                            ),
                        },
                    },
                    "required": ["point", "relance"],
                },
            },
            "offtrack": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ce qu'il a ajoute et que tu n'as pas demande.",
            },
        },
        "required": ["verdict", "coverage", "summary_md", "confirmed", "gaps", "offtrack"],
    },
}


def understanding_user_prompt(brief_block: str, understanding: str, attempt_no: int) -> str:
    return f"""{brief_block}

--- Comprehension envoyee par le prestataire (tentative {attempt_no}) ---
{understanding}
--- fin ---

Evalue cette comprehension par rapport a tes criteres d'acceptation.
Rappel : tu juges la comprehension du besoin, pas la solution technique."""


# --------------------------------------------------------------------------- #
# 3. Indices gradues
# --------------------------------------------------------------------------- #

HINT_SYSTEM = """Tu es un mentor Python senior. Le developpeur bloque sur un projet et
demande un indice d'un palier precis. Tu respectes strictement le palier demande :
en donner plus le priverait de l'apprentissage, et l'indice est facture en points.

Palier 1 - Question orientante : UNE seule question qui le fait reflechir au bon endroit.
  Aucun element de solution, aucun nom de module, aucun code.
Palier 2 - Piste d'approche : les etapes du raisonnement et les concepts ou modules de la
  bibliotheque standard a regarder. Toujours AUCUN code.
Palier 3 - Extrait de code : un extrait de 15 lignes maximum qui illustre le point bloquant
  precis. Jamais la solution complete du projet.

Ecris en francais, markdown, concis. Va droit au but, pas de preambule."""

HINT_TOOL: dict[str, Any] = {
    "name": "donner_indice",
    "description": "Fournit un indice au palier demande, sans jamais le depasser.",
    "input_schema": {
        "type": "object",
        "properties": {
            "content_md": {
                "type": "string",
                "description": "L'indice en markdown, strictement au niveau du palier demande.",
            }
        },
        "required": ["content_md"],
    },
}


def hint_user_prompt(
    brief_block: str,
    understanding: str,
    level: int,
    previous: list[str],
    code_excerpt: str,
) -> str:
    history = "\n\n".join(f"Indice deja donne :\n{item}" for item in previous) or "Aucun"
    code_block = code_excerpt.strip() or "Aucun code ecrit pour l'instant."
    return f"""{brief_block}

--- Comprehension validee du besoin ---
{understanding}
--- fin ---

--- Indices deja consommes ---
{history}
--- fin ---

--- Code actuel ---
{code_block}
--- fin ---

Donne l'indice de palier {level}, et rien de plus."""


# --------------------------------------------------------------------------- #
# 4. Notation du code
# --------------------------------------------------------------------------- #

_CRITERIA_BLOCK = "\n".join(
    f"- {criterion.key} ({criterion.label}, poids {criterion.weight:.0%}) : {criterion.description}"
    for criterion in CRITERIA
)

GRADE_SYSTEM = f"""Tu es relecteur technique Python senior. Tu notes un rendu sur une grille
fixe, avec la severite d'une revue de code professionnelle mais l'utilite d'un mentor.

Grille - chaque critere est note de 0 a 20 :
{_CRITERIA_BLOCK}

Regles de notation :
- 20 = irreprochable pour ce niveau de projet. 14 = solide avec des finitions a faire.
  10 = fonctionne mais conception faible. En dessous de 8 = defaut bloquant.
- Ne sanctionne pas l'absence de choses que le client n'a pas demandees.
- Le critere conformite se juge contre les criteres d'acceptation du brief, rien d'autre.
- Un projet sans aucun test ne peut pas depasser 8 sur tests_doc.

Les axes d'amelioration sont le livrable le plus important : ils doivent etre actionnables.
Chacun dit quoi changer, pourquoi ca compte, et comment s'y prendre - sans ecrire le code
a la place du developpeur. Classe-les par priorite : le premier axe est celui qui ferait
gagner le plus de points a la prochaine iteration.

Ecris en francais."""

GRADE_TOOL: dict[str, Any] = {
    "name": "rendre_note",
    "description": "Rend la notation detaillee du rendu.",
    "input_schema": {
        "type": "object",
        "properties": {
            "scores": {
                "type": "object",
                "properties": {
                    criterion.key: {
                        "type": "object",
                        "properties": {
                            "score": {"type": "number", "minimum": 0, "maximum": 20},
                            "justification": {
                                "type": "string",
                                "description": "1 a 2 phrases, avec un exemple pris dans le code.",
                            },
                        },
                        "required": ["score", "justification"],
                    }
                    for criterion in CRITERIA
                },
                "required": [criterion.key for criterion in CRITERIA],
            },
            "summary_md": {
                "type": "string",
                "description": (
                    "Verdict global en 3 a 5 phrases : ce que vaut le rendu et ce qui le bloque."
                ),
            },
            "strengths": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "description": "Ce qui est reussi, precisement. Pas de compliment generique.",
            },
            "axes": {
                "type": "array",
                "minItems": 2,
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "properties": {
                        "titre": {
                            "type": "string",
                            "description": "L'axe en une phrase imperative.",
                        },
                        "pourquoi": {
                            "type": "string",
                            "description": "L'impact concret du defaut.",
                        },
                        "comment": {
                            "type": "string",
                            "description": "La demarche a suivre, sans ecrire la solution.",
                        },
                        "critere": {
                            "type": "string",
                            "enum": [criterion.key for criterion in CRITERIA],
                        },
                        "priorite": {"type": "integer", "minimum": 1, "maximum": 3},
                    },
                    "required": ["titre", "pourquoi", "comment", "critere", "priorite"],
                },
            },
        },
        "required": ["scores", "summary_md", "strengths", "axes"],
    },
}


def grade_user_prompt(
    brief_block: str,
    understanding: str,
    files_block: str,
    hints_used: list[int],
    attempt_no: int,
    previous_axes: list[str],
) -> str:
    hints = ", ".join(f"palier {level}" for level in sorted(hints_used)) or "aucun"
    history = (
        "\n".join(f"- {axis}" for axis in previous_axes)
        if previous_axes
        else "Premiere tentative, aucun axe anterieur."
    )
    return f"""{brief_block}

--- Comprehension validee du besoin ---
{understanding}
--- fin ---

Tentative n {attempt_no}. Indices consommes : {hints}.

--- Axes d'amelioration donnes a la tentative precedente ---
{history}
--- fin ---

--- Code rendu ---
{files_block}
--- fin ---

Note ce rendu sur la grille. Si des axes anterieurs sont listes, dis explicitement dans le
verdict global lesquels ont ete traites et lesquels restent ouverts."""
