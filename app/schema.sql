PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY,
    slug        TEXT    NOT NULL UNIQUE,
    title       TEXT    NOT NULL,
    source_url  TEXT    NOT NULL,
    theme       TEXT    NOT NULL,
    difficulty  INTEGER NOT NULL,
    day         INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS briefs (
    project_id       INTEGER PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    client_name      TEXT NOT NULL,
    context_md       TEXT NOT NULL,
    need_md          TEXT NOT NULL,
    constraints_json TEXT NOT NULL,
    acceptance_json  TEXT NOT NULL,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attempts (
    id         INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    attempt_no INTEGER NOT NULL,
    status     TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL,
    UNIQUE (project_id, attempt_no)
);

CREATE TABLE IF NOT EXISTS understandings (
    id             INTEGER PRIMARY KEY,
    attempt_id     INTEGER NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    body           TEXT    NOT NULL,
    verdict        TEXT    NOT NULL,
    coverage       INTEGER NOT NULL,
    summary_md     TEXT    NOT NULL,
    confirmed_json TEXT    NOT NULL,
    gaps_json      TEXT    NOT NULL,
    offtrack_json  TEXT    NOT NULL,
    created_at     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS hints (
    id         INTEGER PRIMARY KEY,
    attempt_id INTEGER NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    level      INTEGER NOT NULL,
    content_md TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    UNIQUE (attempt_id, level)
);

CREATE TABLE IF NOT EXISTS reviews (
    id             INTEGER PRIMARY KEY,
    attempt_id     INTEGER NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    raw_total      REAL    NOT NULL,
    penalty        REAL    NOT NULL,
    total          REAL    NOT NULL,
    passed         INTEGER NOT NULL,
    scores_json    TEXT    NOT NULL,
    strengths_json TEXT    NOT NULL,
    axes_json      TEXT    NOT NULL,
    summary_md     TEXT    NOT NULL,
    files_json     TEXT    NOT NULL,
    commit_sha     TEXT,
    created_at     TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attempts_project ON attempts(project_id);
CREATE INDEX IF NOT EXISTS idx_understandings_attempt ON understandings(attempt_id);
CREATE INDEX IF NOT EXISTS idx_hints_attempt ON hints(attempt_id);
CREATE INDEX IF NOT EXISTS idx_reviews_attempt ON reviews(attempt_id);
