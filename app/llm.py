"""Client Claude du coach : brief, validation, indices, notation.

Tous les appels forcent l'usage d'un outil, ce qui garantit une reponse conforme
au schema plutot qu'un texte libre a parser.
"""

from __future__ import annotations

from typing import Any, Protocol, cast

import anthropic
from anthropic.types import MessageParam, ToolChoiceToolParam, ToolParam

from app.config import Settings, get_settings
from app.models import CoachError
from app.prompts import (
    BRIEF_SYSTEM,
    BRIEF_TOOL,
    GRADE_SYSTEM,
    GRADE_TOOL,
    HINT_SYSTEM,
    HINT_TOOL,
    UNDERSTANDING_SYSTEM,
    UNDERSTANDING_TOOL,
    brief_user_prompt,
    grade_user_prompt,
    hint_user_prompt,
    understanding_user_prompt,
)

#: Budget de sortie par type d'appel. La notation est la plus verbeuse.
MAX_TOKENS = {"brief": 2000, "understanding": 2000, "hint": 1200, "grade": 4000}


class CoachProtocol(Protocol):
    """Contrat attendu par la couche service.

    Le service depend de cette interface et non de la classe concrete : les tests
    peuvent donc jouer le parcours complet sans appeler l'API.
    """

    def generate_brief(
        self, title: str, theme: str, difficulty: int, source_url: str
    ) -> dict[str, Any]: ...

    def review_understanding(
        self, brief_block: str, understanding: str, attempt_no: int
    ) -> dict[str, Any]: ...

    def give_hint(
        self,
        brief_block: str,
        understanding: str,
        level: int,
        previous: list[str],
        code_excerpt: str,
    ) -> str: ...

    def grade(
        self,
        brief_block: str,
        understanding: str,
        files_block: str,
        hints_used: list[int],
        attempt_no: int,
        previous_axes: list[str],
    ) -> dict[str, Any]: ...


class Coach:
    """Facade typee au-dessus de l'API Messages."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.llm_ready:
            raise CoachError(
                "Cle API Anthropic absente. Copie .env.example vers .env et renseigne "
                "ANTHROPIC_API_KEY."
            )
        self._client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)

    # -- appel bas niveau --------------------------------------------------- #

    def _call(self, system: str, user: str, tool: dict[str, Any], budget: str) -> dict[str, Any]:
        name = str(tool["name"])
        messages: list[MessageParam] = [{"role": "user", "content": user}]
        tool_choice: ToolChoiceToolParam = {"type": "tool", "name": name}
        try:
            response = self._client.messages.create(
                model=self._settings.coach_model,
                max_tokens=MAX_TOKENS[budget],
                system=system,
                messages=messages,
                tools=[cast(ToolParam, tool)],
                tool_choice=tool_choice,
            )
        except anthropic.APIConnectionError as error:
            raise CoachError(f"Connexion a l'API Claude impossible : {error}") from error
        except anthropic.RateLimitError as error:
            raise CoachError(
                "Limite de debit de l'API atteinte, reessaie dans un moment."
            ) from error
        except anthropic.AuthenticationError as error:
            raise CoachError("Cle API Anthropic refusee. Verifie ANTHROPIC_API_KEY.") from error
        except anthropic.APIStatusError as error:
            raise CoachError(
                f"L'API Claude a repondu {error.status_code} : {error.message}"
            ) from error

        for block in response.content:
            if block.type == "tool_use" and block.name == name:
                payload = block.input
                if not isinstance(payload, dict):
                    raise CoachError(
                        "Reponse de l'API inattendue : l'outil n'a pas renvoye d'objet."
                    )
                return payload

        raise CoachError(
            f"Le modele n'a pas appele l'outil {name} (arret : {response.stop_reason}). Reessaie."
        )

    # -- cas d'usage -------------------------------------------------------- #

    def generate_brief(
        self, title: str, theme: str, difficulty: int, source_url: str
    ) -> dict[str, Any]:
        payload = self._call(
            BRIEF_SYSTEM,
            brief_user_prompt(title, theme, difficulty, source_url),
            BRIEF_TOOL,
            "brief",
        )
        if not payload.get("acceptance"):
            raise CoachError("Le brief genere n'a aucun critere d'acceptation. Reessaie.")
        return payload

    def review_understanding(
        self, brief_block: str, understanding: str, attempt_no: int
    ) -> dict[str, Any]:
        return self._call(
            UNDERSTANDING_SYSTEM,
            understanding_user_prompt(brief_block, understanding, attempt_no),
            UNDERSTANDING_TOOL,
            "understanding",
        )

    def give_hint(
        self,
        brief_block: str,
        understanding: str,
        level: int,
        previous: list[str],
        code_excerpt: str,
    ) -> str:
        payload = self._call(
            HINT_SYSTEM,
            hint_user_prompt(brief_block, understanding, level, previous, code_excerpt),
            HINT_TOOL,
            "hint",
        )
        content = str(payload.get("content_md", "")).strip()
        if not content:
            raise CoachError("L'indice renvoye est vide. Reessaie.")
        return content

    def grade(
        self,
        brief_block: str,
        understanding: str,
        files_block: str,
        hints_used: list[int],
        attempt_no: int,
        previous_axes: list[str],
    ) -> dict[str, Any]:
        payload = self._call(
            GRADE_SYSTEM,
            grade_user_prompt(
                brief_block, understanding, files_block, hints_used, attempt_no, previous_axes
            ),
            GRADE_TOOL,
            "grade",
        )
        if not isinstance(payload.get("scores"), dict):
            raise CoachError("La notation renvoyee est incomplete. Reessaie.")
        return payload
