# src/jobs_es/source_debug.py

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT / "tests" / "fixtures"
DEBUG_DIR = ROOT / "data" / "debug"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "_", str(value).lower()).strip("_")


def save_fixture(source: str, label: str, text: str) -> Path:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURES_DIR / f"{_slug(source)}_{_slug(label)}.html"
    path.write_text(text, encoding="utf-8")
    return path


def save_debug(source: str, label: str, text: str) -> Path:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    path = DEBUG_DIR / f"{_slug(source)}_{_slug(label)}.html"
    path.write_text(text, encoding="utf-8")
    return path


def maybe_save_fixture(source: str, label: str, text: str, opts: dict | None) -> Path | None:
    if opts and opts.get("save_fixtures"):
        return save_fixture(source, label, text)
    return None


def maybe_save_debug(source: str, label: str, text: str, opts: dict | None) -> Path | None:
    if opts and opts.get("debug_html"):
        return save_debug(source, label, text)
    return None
