"""Construit data/catalog.json depuis le README de Python-World/python-mini-projects.

Usage:
    python scripts/build_catalog.py [--readme chemin/vers/README.md]

Sans --readme, le script telecharge le README depuis GitHub.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

README_URL = "https://raw.githubusercontent.com/Python-World/python-mini-projects/master/README.md"
ROW = re.compile(r"^(?P<num>\d+)\s*\|\s*\[(?P<title>[^\]]+)\]\((?P<url>[^)]+)\)")

# Mots-cles -> theme. L'ordre compte : le premier theme qui matche gagne.
THEMES: list[tuple[str, tuple[str, ...]]] = [
    ("securite", ("encrypt", "decrypt", "hash", "password", "cipher", "secret")),
    (
        "media",
        (
            "image",
            "img",
            "video",
            "photo",
            "watermark",
            "frame",
            "thumbnail",
            "audio",
            "mp3",
            "speech",
            "qr",
            "barcode",
            "pdf",
            "gif",
            "screenshot",
        ),
    ),
    (
        "web",
        (
            "url",
            "web",
            "scrape",
            "http",
            "download",
            "website",
            "site",
            "link",
            "ipaddress",
            "hostname",
            "proxy",
            "api",
            "wikipedia",
            "imdb",
            "youtube",
            "instagram",
            "twitter",
            "reddit",
            "weather",
            "currency",
            "news",
        ),
    ),
    ("framework", ("flask", "django", "streamlit", "dash", "fastapi", "tkinter", "gui")),
    (
        "automatisation",
        (
            "email",
            "notification",
            "bot",
            "whatsapp",
            "schedule",
            "alarm",
            "reminder",
            "battery",
            "sms",
            "telegram",
            "cron",
        ),
    ),
    (
        "fichiers",
        (
            "file",
            "folder",
            "directory",
            "organize",
            "split",
            "compress",
            "zip",
            "rename",
            "move",
            "path",
            "csv",
            "json",
            "xml",
            "excel",
            "sqlite",
            "database",
            "backup",
        ),
    ),
    (
        "donnees",
        (
            "text",
            "analysis",
            "word",
            "string",
            "count",
            "convert",
            "sort",
            "number",
            "matrix",
            "calcul",
            "math",
            "binary",
            "decimal",
            "date",
            "age",
            "random",
            "dictionary",
            "list",
        ),
    ),
]

HARD = (
    "django",
    "flask",
    "streamlit",
    "selenium",
    "machine",
    "neural",
    "async",
    "gui",
    "tkinter",
    "opencv",
    "bot",
    "server",
)
MEDIUM = (
    "scrape",
    "video",
    "api",
    "email",
    "database",
    "sqlite",
    "pdf",
    "ocr",
    "thread",
    "socket",
    "download",
    "encrypt",
    "watermark",
)
EASY = (
    "hello",
    "random",
    "calculate",
    "convert",
    "count",
    "decimal",
    "binary",
    "word",
    "simple",
    "age",
    "sort",
    "string",
    "dictionary",
)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", normalized.lower())).strip("-")


def classify(title: str) -> tuple[str, int]:
    low = title.lower()
    theme = next((name for name, words in THEMES if any(w in low for w in words)), "divers")
    if any(w in low for w in HARD):
        difficulty = 4
    elif any(w in low for w in MEDIUM):
        difficulty = 3
    elif any(w in low for w in EASY):
        difficulty = 1
    else:
        difficulty = 2
    return theme, difficulty


def load_readme(path: Path | None) -> str:
    if path is not None:
        return path.read_text(encoding="utf-8")
    with urllib.request.urlopen(README_URL, timeout=30) as response:  # noqa: S310
        payload: bytes = response.read()
    return payload.decode("utf-8")


def parse(markdown: str) -> list[dict[str, object]]:
    seen: set[str] = set()
    entries: list[dict[str, object]] = []
    for line in markdown.splitlines():
        match = ROW.match(line.strip())
        if match is None:
            continue
        title = match.group("title").strip()
        slug = slugify(title)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        theme, difficulty = classify(title)
        entries.append(
            {
                "slug": slug,
                "title": title,
                "source_url": match.group("url").strip(),
                "theme": theme,
                "difficulty": difficulty,
                "source_rank": int(match.group("num")),
            }
        )
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readme", type=Path, default=None, help="README local a parser")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "catalog.json",
        help="fichier de sortie",
    )
    args = parser.parse_args()

    try:
        markdown = load_readme(args.readme)
    except OSError as error:
        print(f"Impossible de lire le README : {error}", file=sys.stderr)
        return 1

    entries = parse(markdown)
    if not entries:
        print("Aucun projet trouve dans le README.", file=sys.stderr)
        return 1

    # Progression : du plus simple au plus complexe, en gardant l'ordre source a difficulte egale.
    entries.sort(key=lambda entry: (entry["difficulty"], entry["source_rank"]))
    for day, entry in enumerate(entries, start=1):
        entry["day"] = day

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(entries)} projets ecrits dans {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
