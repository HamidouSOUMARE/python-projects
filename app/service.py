"""Orchestration du parcours : brief, comprehension, indices, rendu, notation.

Toute transition d'etat passe par `_set_status`, qui refuse les enchainements
interdits. Le verrou central : on ne code pas avant que le besoin soit valide.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.config import Settings, get_settings
from app.db import now
from app.gitops import PushResult, commit_and_push
from app.llm import CoachProtocol
from app.models import (
    CRITERIA,
    TRANSITIONS,
    CoachError,
    Status,
    TransitionError,
)
from app.scoring import appreciation, final_score
from app.workspace import (
    code_excerpt,
    collect_files,
    ensure_project_dir,
    files_block,
    project_dir,
    stats,
)

MAX_HINT_LEVEL = 3


# --------------------------------------------------------------------------- #
# Lecture du catalogue
# --------------------------------------------------------------------------- #


def get_project(connection: sqlite3.Connection, project_id: int) -> dict[str, Any]:
    row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        raise CoachError(f"Projet {project_id} inconnu.")
    return dict(row)


def list_projects(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Catalogue complet, enrichi du statut et de la meilleure note obtenue."""
    rows = connection.execute(
        """
        SELECT
            p.*,
            (SELECT status FROM attempts a WHERE a.project_id = p.id
             ORDER BY a.attempt_no DESC LIMIT 1)                        AS status,
            (SELECT COUNT(*) FROM attempts a WHERE a.project_id = p.id) AS attempts_count,
            (SELECT MAX(r.total) FROM reviews r
             JOIN attempts a ON a.id = r.attempt_id
             WHERE a.project_id = p.id)                                 AS best_score
        FROM projects p
        ORDER BY p.day
        """
    ).fetchall()
    return [dict(row) for row in rows]


def next_project(connection: sqlite3.Connection) -> dict[str, Any] | None:
    """Le projet du jour : le premier non valide dans l'ordre de progression."""
    row = connection.execute(
        """
        SELECT p.* FROM projects p
        WHERE NOT EXISTS (
            SELECT 1 FROM attempts a
            WHERE a.project_id = p.id AND a.status = ?
        )
        ORDER BY p.day
        LIMIT 1
        """,
        (Status.VALIDATED.value,),
    ).fetchone()
    return dict(row) if row else None


# --------------------------------------------------------------------------- #
# Brief
# --------------------------------------------------------------------------- #


def get_brief(connection: sqlite3.Connection, project_id: int) -> dict[str, Any] | None:
    row = connection.execute("SELECT * FROM briefs WHERE project_id = ?", (project_id,)).fetchone()
    if row is None:
        return None
    brief = dict(row)
    brief["constraints"] = json.loads(brief.pop("constraints_json"))
    brief["acceptance"] = json.loads(brief.pop("acceptance_json"))
    return brief


def ensure_brief(
    connection: sqlite3.Connection, coach: CoachProtocol, project: dict[str, Any]
) -> dict[str, Any]:
    """Genere le brief une seule fois par projet, puis le reutilise.

    Le brief est stable d'une tentative a l'autre : sans cela, comparer deux
    iterations du meme projet n'aurait aucun sens.
    """
    existing = get_brief(connection, project["id"])
    if existing is not None:
        return existing

    payload = coach.generate_brief(
        project["title"], project["theme"], int(project["difficulty"]), project["source_url"]
    )
    connection.execute(
        """
        INSERT INTO briefs (project_id, client_name, context_md, need_md,
                            constraints_json, acceptance_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project["id"],
            payload["client_name"],
            payload["context_md"],
            payload["need_md"],
            json.dumps(payload["constraints"], ensure_ascii=False),
            json.dumps(payload["acceptance"], ensure_ascii=False),
            now(),
        ),
    )
    connection.commit()
    brief = get_brief(connection, project["id"])
    if brief is None:  # pragma: no cover - garde-fou
        raise CoachError("Le brief n'a pas pu etre enregistre.")
    return brief


def brief_markdown(project: dict[str, Any], brief: dict[str, Any]) -> str:
    """Version lisible du brief, deposee dans le dossier du projet.

    Les criteres d'acceptation en sont volontairement absents : ils servent a
    juger la comprehension, les reveler viderait l'exercice de son sens.
    """
    constraints = "\n".join(f"- {item}" for item in brief["constraints"])
    return (
        f"# Jour {project['day']:02d} - {project['title']}\n\n"
        f"**Client :** {brief['client_name']}\n\n"
        f"## Contexte\n\n{brief['context_md']}\n\n"
        f"## Besoin\n\n{brief['need_md']}\n\n"
        f"## Contraintes\n\n{constraints}\n\n"
        f"---\n_Sujet d'origine : {project['source_url']}_\n"
    )


def brief_block(brief: dict[str, Any]) -> str:
    """Bloc de contexte envoye au modele : inclut les criteres caches."""
    constraints = "\n".join(f"- {item}" for item in brief["constraints"])
    acceptance = "\n".join(
        f"- [{item['id']}]{' (critique)' if item.get('critical') else ''} {item['label']}"
        for item in brief["acceptance"]
    )
    return f"""--- Brief deja depose (client : {brief["client_name"]}) ---
Contexte : {brief["context_md"]}

Besoin exprime :
{brief["need_md"]}

Contraintes :
{constraints}

Criteres d'acceptation (connus de toi seul) :
{acceptance}
--- fin du brief ---"""


# --------------------------------------------------------------------------- #
# Tentatives et machine a etats
# --------------------------------------------------------------------------- #


def latest_attempt(connection: sqlite3.Connection, project_id: int) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM attempts WHERE project_id = ? ORDER BY attempt_no DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    return dict(row) if row else None


def get_attempt(connection: sqlite3.Connection, attempt_id: int) -> dict[str, Any]:
    row = connection.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    if row is None:
        raise CoachError(f"Tentative {attempt_id} inconnue.")
    return dict(row)


def start_attempt(connection: sqlite3.Connection, project_id: int) -> dict[str, Any]:
    """Ouvre la premiere tentative d'un projet, ou retourne celle en cours."""
    existing = latest_attempt(connection, project_id)
    if existing is not None:
        return existing
    timestamp = now()
    cursor = connection.execute(
        """
        INSERT INTO attempts (project_id, attempt_no, status, created_at, updated_at)
        VALUES (?, 1, ?, ?, ?)
        """,
        (project_id, Status.BRIEFED.value, timestamp, timestamp),
    )
    connection.commit()
    return get_attempt(connection, int(cursor.lastrowid or 0))


def start_iteration(connection: sqlite3.Connection, project_id: int) -> dict[str, Any]:
    """Ouvre une nouvelle tentative apres une note insuffisante.

    La comprehension du besoin reste acquise : la nouvelle tentative demarre
    directement en phase de realisation, axes d'amelioration en main.
    """
    current = latest_attempt(connection, project_id)
    if current is None:
        raise CoachError("Ce projet n'a pas encore ete demarre.")
    if Status(current["status"]) is not Status.REVIEWED:
        raise TransitionError(
            "Une nouvelle iteration ne s'ouvre qu'apres une notation insuffisante."
        )
    timestamp = now()
    cursor = connection.execute(
        """
        INSERT INTO attempts (project_id, attempt_no, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (project_id, int(current["attempt_no"]) + 1, Status.CODING.value, timestamp, timestamp),
    )
    connection.commit()
    return get_attempt(connection, int(cursor.lastrowid or 0))


def _set_status(connection: sqlite3.Connection, attempt_id: int, target: Status) -> None:
    current = Status(get_attempt(connection, attempt_id)["status"])
    if target not in TRANSITIONS[current]:
        raise TransitionError(f"Transition refusee : {current.value} -> {target.value}.")
    connection.execute(
        "UPDATE attempts SET status = ?, updated_at = ? WHERE id = ?",
        (target.value, now(), attempt_id),
    )


def _require_status(attempt: dict[str, Any], *allowed: Status) -> Status:
    status = Status(attempt["status"])
    if status not in allowed:
        expected = " ou ".join(item.value for item in allowed)
        raise TransitionError(
            f"Action impossible dans l'etat '{status.value}' (attendu : {expected})."
        )
    return status


# --------------------------------------------------------------------------- #
# Etape 2 : comprehension du besoin
# --------------------------------------------------------------------------- #


def understandings(connection: sqlite3.Connection, attempt_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT * FROM understandings WHERE attempt_id = ? ORDER BY id",
        (attempt_id,),
    ).fetchall()
    return [_hydrate_understanding(row) for row in rows]


def _hydrate_understanding(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["confirmed"] = json.loads(item.pop("confirmed_json"))
    item["gaps"] = json.loads(item.pop("gaps_json"))
    item["offtrack"] = json.loads(item.pop("offtrack_json"))
    return item


def validated_understanding(connection: sqlite3.Connection, project_id: int) -> str | None:
    """La comprehension validee du besoin, acquise pour tout le projet."""
    row = connection.execute(
        """
        SELECT u.body FROM understandings u
        JOIN attempts a ON a.id = u.attempt_id
        WHERE a.project_id = ? AND u.verdict = 'valide'
        ORDER BY u.id DESC LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    return str(row["body"]) if row else None


def submit_understanding(
    connection: sqlite3.Connection,
    coach: CoachProtocol,
    project_id: int,
    body: str,
) -> dict[str, Any]:
    """Soumet la reformulation du besoin au client et applique son verdict."""
    text = body.strip()
    if len(text) < 80:
        raise CoachError(
            "Reformulation trop courte pour etre evaluee : detaille ce que le client attend, "
            "les contraintes, et les cas particuliers que tu anticipes (80 caracteres minimum)."
        )

    project = get_project(connection, project_id)
    attempt = start_attempt(connection, project_id)
    _require_status(attempt, Status.BRIEFED, Status.UNDERSTANDING_REJECTED)

    brief = get_brief(connection, project_id)
    if brief is None:
        raise CoachError("Le brief de ce projet n'a pas encore ete genere.")

    verdict = coach.review_understanding(brief_block(brief), text, int(attempt["attempt_no"]))
    accepted = verdict.get("verdict") == "valide"

    connection.execute(
        """
        INSERT INTO understandings (attempt_id, body, verdict, coverage, summary_md,
                                    confirmed_json, gaps_json, offtrack_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            attempt["id"],
            text,
            "valide" if accepted else "a_preciser",
            int(verdict.get("coverage", 0)),
            verdict.get("summary_md", ""),
            json.dumps(verdict.get("confirmed", []), ensure_ascii=False),
            json.dumps(verdict.get("gaps", []), ensure_ascii=False),
            json.dumps(verdict.get("offtrack", []), ensure_ascii=False),
            now(),
        ),
    )
    _set_status(
        connection,
        int(attempt["id"]),
        Status.CODING if accepted else Status.UNDERSTANDING_REJECTED,
    )
    connection.commit()

    if accepted:
        # Le besoin est fige : on ouvre le chantier sur le disque.
        ensure_project_dir(
            int(project["day"]), project["slug"], project["title"], brief_markdown(project, brief)
        )
    return verdict


# --------------------------------------------------------------------------- #
# Etape 3 : indices
# --------------------------------------------------------------------------- #


def hints(connection: sqlite3.Connection, attempt_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT * FROM hints WHERE attempt_id = ? ORDER BY level",
        (attempt_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def request_hint(
    connection: sqlite3.Connection,
    coach: CoachProtocol,
    project_id: int,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Debloque le palier d'indice suivant, en facturant son malus."""
    config = settings or get_settings()
    project = get_project(connection, project_id)
    attempt = latest_attempt(connection, project_id)
    if attempt is None:
        raise CoachError("Ce projet n'a pas encore ete demarre.")
    _require_status(attempt, Status.CODING)

    used = hints(connection, int(attempt["id"]))
    level = len(used) + 1
    if level > MAX_HINT_LEVEL:
        raise CoachError("Les trois paliers d'indices sont deja consommes pour cette tentative.")

    brief = get_brief(connection, project_id)
    understanding = validated_understanding(connection, project_id)
    if brief is None or understanding is None:
        raise CoachError("Le besoin doit etre valide avant de demander un indice.")

    files = collect_files(project_dir(int(project["day"]), project["slug"]))
    content = coach.give_hint(
        brief_block(brief),
        understanding,
        level,
        [item["content_md"] for item in used],
        code_excerpt(files),
    )
    connection.execute(
        "INSERT INTO hints (attempt_id, level, content_md, created_at) VALUES (?, ?, ?, ?)",
        (attempt["id"], level, content, now()),
    )
    connection.commit()
    return {
        "level": level,
        "content_md": content,
        "penalty": config.penalty_for_level(level),
        "remaining": MAX_HINT_LEVEL - level,
    }


# --------------------------------------------------------------------------- #
# Etape 4 et 5 : rendu, push, notation
# --------------------------------------------------------------------------- #


def reviews(connection: sqlite3.Connection, attempt_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT * FROM reviews WHERE attempt_id = ? ORDER BY id",
        (attempt_id,),
    ).fetchall()
    return [_hydrate_review(row) for row in rows]


def _hydrate_review(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["scores"] = json.loads(item.pop("scores_json"))
    item["strengths"] = json.loads(item.pop("strengths_json"))
    item["axes"] = json.loads(item.pop("axes_json"))
    item["files"] = json.loads(item.pop("files_json"))
    item["passed"] = bool(item["passed"])
    item["appreciation"] = appreciation(float(item["total"]))
    return item


def previous_axes(connection: sqlite3.Connection, project_id: int, attempt_no: int) -> list[str]:
    row = connection.execute(
        """
        SELECT r.axes_json FROM reviews r
        JOIN attempts a ON a.id = r.attempt_id
        WHERE a.project_id = ? AND a.attempt_no < ?
        ORDER BY a.attempt_no DESC, r.id DESC LIMIT 1
        """,
        (project_id, attempt_no),
    ).fetchone()
    if row is None:
        return []
    return [f"{axis['titre']} ({axis['critere']})" for axis in json.loads(row["axes_json"])]


def submit_code(
    connection: sqlite3.Connection,
    coach: CoachProtocol,
    project_id: int,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Relit le rendu, le fait noter, l'ecrit, le commite et pousse."""
    config = settings or get_settings()
    project = get_project(connection, project_id)
    attempt = latest_attempt(connection, project_id)
    if attempt is None:
        raise CoachError("Ce projet n'a pas encore ete demarre.")
    _require_status(attempt, Status.CODING)

    directory = project_dir(int(project["day"]), project["slug"])
    files = collect_files(directory)
    if not any(source.path.endswith(".py") for source in files):
        raise CoachError(
            f"Aucun fichier Python trouve dans {directory.name}. "
            "Ecris ton code dans ce dossier avant de rendre."
        )

    brief = get_brief(connection, project_id)
    understanding = validated_understanding(connection, project_id)
    if brief is None or understanding is None:
        raise CoachError("Le besoin doit etre valide avant de rendre.")

    used_levels = [int(item["level"]) for item in hints(connection, int(attempt["id"]))]
    payload = coach.grade(
        brief_block(brief),
        understanding,
        files_block(files),
        used_levels,
        int(attempt["attempt_no"]),
        previous_axes(connection, project_id, int(attempt["attempt_no"])),
    )

    scores = {
        key: float(value["score"])
        for key, value in payload["scores"].items()
        if isinstance(value, dict) and "score" in value
    }
    raw, penalty, total = final_score(scores, used_levels, config.hint_penalties)
    passed = total >= config.pass_threshold

    review = {
        "total": total,
        "raw_total": raw,
        "penalty": penalty,
        "passed": passed,
        "appreciation": appreciation(total),
        "scores": payload["scores"],
        "strengths": payload.get("strengths", []),
        "axes": sorted(payload.get("axes", []), key=lambda axis: axis.get("priorite", 3)),
        "summary_md": payload.get("summary_md", ""),
        "stats": stats(files),
    }

    # La revue est versionnee a cote du code : l'historique git raconte la progression.
    (directory / f"REVIEW-v{int(attempt['attempt_no'])}.md").write_text(
        review_markdown(project, int(attempt["attempt_no"]), review, config),
        encoding="utf-8",
    )
    push: PushResult = commit_and_push(
        [directory],
        f"feat(day-{int(project['day']):02d}): {project['title']} v{attempt['attempt_no']} "
        f"- {total}/20",
        config,
    )

    connection.execute(
        """
        INSERT INTO reviews (attempt_id, raw_total, penalty, total, passed, scores_json,
                             strengths_json, axes_json, summary_md, files_json,
                             commit_sha, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            attempt["id"],
            raw,
            penalty,
            total,
            int(passed),
            json.dumps(review["scores"], ensure_ascii=False),
            json.dumps(review["strengths"], ensure_ascii=False),
            json.dumps(review["axes"], ensure_ascii=False),
            review["summary_md"],
            json.dumps([source.path for source in files], ensure_ascii=False),
            push.commit_sha,
            now(),
        ),
    )
    _set_status(
        connection,
        int(attempt["id"]),
        Status.VALIDATED if passed else Status.REVIEWED,
    )
    connection.commit()

    review["commit_sha"] = push.commit_sha
    review["git_message"] = push.message
    review["threshold"] = config.pass_threshold
    return review


def review_markdown(
    project: dict[str, Any], attempt_no: int, review: dict[str, Any], settings: Settings
) -> str:
    """Compte rendu de notation, ecrit dans le dossier du projet."""
    lines = [
        f"# Revue - Jour {project['day']:02d} - {project['title']} (v{attempt_no})",
        "",
        f"**Note : {review['total']}/20** - {review['appreciation']}",
        "",
        f"Note brute {review['raw_total']}/20, malus indices -{review['penalty']}, "
        f"seuil de validation {settings.pass_threshold}/20.",
        "",
        "## Verdict",
        "",
        str(review["summary_md"]),
        "",
        "## Grille",
        "",
        "| Critere | Note | Justification |",
        "| --- | --- | --- |",
    ]
    for criterion in CRITERIA:
        entry = review["scores"].get(criterion.key, {})
        justification = str(entry.get("justification", "")).replace("|", "/").replace("\n", " ")
        lines.append(f"| {criterion.label} | {entry.get('score', '-')}/20 | {justification} |")

    lines += ["", "## Points forts", ""]
    lines += [f"- {item}" for item in review["strengths"]]
    lines += ["", "## Axes d'amelioration", ""]
    for index, axis in enumerate(review["axes"], start=1):
        lines += [
            f"### {index}. {axis['titre']} (priorite {axis['priorite']}, {axis['critere']})",
            "",
            f"**Pourquoi :** {axis['pourquoi']}",
            "",
            f"**Comment :** {axis['comment']}",
            "",
        ]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Vue d'ensemble
# --------------------------------------------------------------------------- #


def project_state(
    connection: sqlite3.Connection, project_id: int, settings: Settings | None = None
) -> dict[str, Any]:
    """Tout ce dont la page d'un projet a besoin, en une seule lecture."""
    config = settings or get_settings()
    project = get_project(connection, project_id)
    attempt = latest_attempt(connection, project_id)
    brief = get_brief(connection, project_id)

    state: dict[str, Any] = {
        "project": project,
        "brief": brief,
        "attempt": attempt,
        "status": Status(attempt["status"]) if attempt else None,
        "understandings": [],
        "hints": [],
        "review": None,
        "previous_axes": [],
        "directory": project_dir(int(project["day"]), project["slug"]),
        "validated_understanding": validated_understanding(connection, project_id),
        "threshold": config.pass_threshold,
        "hint_penalties": config.hint_penalties,
    }
    if attempt is None:
        return state

    attempt_id = int(attempt["id"])
    state["understandings"] = understandings(connection, attempt_id)
    state["hints"] = hints(connection, attempt_id)
    attempt_reviews = reviews(connection, attempt_id)
    state["review"] = attempt_reviews[-1] if attempt_reviews else None
    state["previous_axes"] = _previous_axes_detailed(
        connection, project_id, int(attempt["attempt_no"])
    )
    state["files"] = collect_files(state["directory"])
    return state


def _previous_axes_detailed(
    connection: sqlite3.Connection, project_id: int, attempt_no: int
) -> list[dict[str, Any]]:
    row = connection.execute(
        """
        SELECT r.axes_json, r.total, a.attempt_no FROM reviews r
        JOIN attempts a ON a.id = r.attempt_id
        WHERE a.project_id = ? AND a.attempt_no < ?
        ORDER BY a.attempt_no DESC, r.id DESC LIMIT 1
        """,
        (project_id, attempt_no),
    ).fetchone()
    return json.loads(row["axes_json"]) if row else []


def progress(connection: sqlite3.Connection) -> dict[str, Any]:
    """Statistiques de progression affichees sur le tableau de bord."""
    total = int(connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0])
    validated = int(
        connection.execute(
            "SELECT COUNT(DISTINCT project_id) FROM attempts WHERE status = ?",
            (Status.VALIDATED.value,),
        ).fetchone()[0]
    )
    row = connection.execute(
        """
        SELECT AVG(best.total) AS average, MAX(best.total) AS best, COUNT(*) AS graded
        FROM (
            SELECT a.project_id, MAX(r.total) AS total
            FROM reviews r JOIN attempts a ON a.id = r.attempt_id
            WHERE a.status = ?
            GROUP BY a.project_id
        ) AS best
        """,
        (Status.VALIDATED.value,),
    ).fetchone()
    hints_used = int(connection.execute("SELECT COUNT(*) FROM hints").fetchone()[0])
    iterations = int(connection.execute("SELECT COUNT(*) FROM reviews").fetchone()[0])

    return {
        "total": total,
        "validated": validated,
        "percent": round(100 * validated / total, 1) if total else 0.0,
        "average": round(float(row["average"]), 2) if row["average"] is not None else None,
        "best": round(float(row["best"]), 2) if row["best"] is not None else None,
        "iterations": iterations,
        "hints_used": hints_used,
        "streak": _streak(connection),
        "trend": _trend(connection),
    }


def _streak(connection: sqlite3.Connection) -> int:
    """Nombre de jours consecutifs, jusqu'a aujourd'hui ou hier, avec un projet valide."""
    rows = connection.execute(
        """
        SELECT DISTINCT date(updated_at) AS day FROM attempts
        WHERE status = ? ORDER BY day DESC
        """,
        (Status.VALIDATED.value,),
    ).fetchall()
    days = {date.fromisoformat(row["day"]) for row in rows}
    if not days:
        return 0
    today = datetime.now(UTC).date()
    cursor = today if today in days else today - timedelta(days=1)
    if cursor not in days:
        return 0
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _trend(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Les dix dernieres notes, pour la courbe de progression."""
    rows = connection.execute(
        """
        SELECT r.total, p.day, p.title, a.attempt_no
        FROM reviews r
        JOIN attempts a ON a.id = r.attempt_id
        JOIN projects p ON p.id = a.project_id
        ORDER BY r.id DESC LIMIT 10
        """
    ).fetchall()
    return [dict(row) for row in reversed(rows)]
