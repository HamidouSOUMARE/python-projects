"""Application web du coach Python.

Toutes les actions qui modifient l'etat suivent le schema POST puis redirection :
un rafraichissement de page ne rejoue jamais un appel a l'API.
"""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt

from app import service
from app.config import get_settings
from app.db import connect, init_db
from app.llm import Coach
from app.models import CRITERIA, HINT_LABELS, STATUS_LABELS, CoachError, Status

BASE_DIR = Path(__file__).resolve().parent
MARKDOWN = MarkdownIt("commonmark", {"breaks": True, "linkify": True})


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="Coach Python", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["md"] = lambda text: MARKDOWN.render(str(text or ""))
templates.env.globals.update(
    criteria=CRITERIA,
    status_labels=STATUS_LABELS,
    hint_labels=HINT_LABELS,
    Status=Status,
)


def get_connection() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


Connection = Annotated[sqlite3.Connection, Depends(get_connection)]


def _redirect(path: str, message: str = "", kind: str = "info") -> RedirectResponse:
    query = f"?{urlencode({'message': message, 'kind': kind})}" if message else ""
    return RedirectResponse(f"{path}{query}", status_code=303)


def _flash(request: Request) -> dict[str, str] | None:
    message = request.query_params.get("message")
    if not message:
        return None
    return {"text": message, "kind": request.query_params.get("kind", "info")}


def _context(request: Request, **extra: Any) -> dict[str, Any]:
    settings = get_settings()
    return {
        "request": request,
        "flash": _flash(request),
        "llm_ready": settings.llm_ready,
        "settings": settings,
        **extra,
    }


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, connection: Connection) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        _context(
            request,
            progress=service.progress(connection),
            current=service.next_project(connection),
            projects=service.list_projects(connection),
        ),
    )


@app.get("/catalogue", response_class=HTMLResponse)
def catalog(request: Request, connection: Connection) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "catalog.html",
        _context(request, projects=service.list_projects(connection)),
    )


@app.get("/projet/{project_id}", response_class=HTMLResponse)
def project_page(project_id: int, request: Request, connection: Connection) -> HTMLResponse:
    try:
        state = service.project_state(connection, project_id)
    except CoachError as error:
        return templates.TemplateResponse(
            request, "error.html", _context(request, detail=str(error)), status_code=404
        )
    return templates.TemplateResponse(request, "project.html", _context(request, **state))


# --------------------------------------------------------------------------- #
# Actions
# --------------------------------------------------------------------------- #


@app.post("/projet/{project_id}/brief")
def action_brief(project_id: int, connection: Connection) -> RedirectResponse:
    target = f"/projet/{project_id}"
    try:
        project = service.get_project(connection, project_id)
        service.ensure_brief(connection, Coach(), project)
        service.start_attempt(connection, project_id)
    except CoachError as error:
        return _redirect(target, str(error), "error")
    return _redirect(target, "Brief recu. Reformule le besoin avant de coder.", "success")


@app.post("/projet/{project_id}/comprehension")
def action_understanding(
    project_id: int,
    connection: Connection,
    body: Annotated[str, Form()],
) -> RedirectResponse:
    target = f"/projet/{project_id}"
    try:
        verdict = service.submit_understanding(connection, Coach(), project_id, body)
    except CoachError as error:
        return _redirect(target, str(error), "error")
    if verdict.get("verdict") == "valide":
        return _redirect(target, "Besoin valide par le client. Tu peux coder.", "success")
    return _redirect(target, "Le client t'a relance : precise ta comprehension.", "warning")


@app.post("/projet/{project_id}/indice")
def action_hint(project_id: int, connection: Connection) -> RedirectResponse:
    target = f"/projet/{project_id}#indices"
    try:
        hint = service.request_hint(connection, Coach(), project_id)
    except CoachError as error:
        return _redirect(f"/projet/{project_id}", str(error), "error")
    return _redirect(
        target,
        f"Indice de palier {hint['level']} debloque (-{hint['penalty']} point sur la note).",
        "warning",
    )


@app.post("/projet/{project_id}/rendu")
def action_submit(project_id: int, connection: Connection) -> RedirectResponse:
    target = f"/projet/{project_id}#revue"
    try:
        review = service.submit_code(connection, Coach(), project_id)
    except CoachError as error:
        return _redirect(f"/projet/{project_id}", str(error), "error")
    verdict = "valide" if review["passed"] else "sous le seuil"
    return _redirect(
        target,
        f"Note : {review['total']}/20 - {verdict}. {review['git_message']}",
        "success" if review["passed"] else "warning",
    )


@app.post("/projet/{project_id}/iteration")
def action_iterate(project_id: int, connection: Connection) -> RedirectResponse:
    target = f"/projet/{project_id}"
    try:
        service.start_iteration(connection, project_id)
    except CoachError as error:
        return _redirect(target, str(error), "error")
    return _redirect(target, "Nouvelle iteration ouverte. Les axes restent affiches.", "info")
