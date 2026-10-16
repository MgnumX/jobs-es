# src/jobs_es/source_meta.py

SOURCE_META = {
    "amazon": {
        "pause": 0.25,
        "needs_detail": False,
        "min_expected": 20,
        "default_pages": 10,
        "detail_budget": 0,
    },
    "jobandtalent": {
        "pause": 0.25,
        "needs_detail": False,
        "min_expected": 50,
        "default_pages": 8,
        "detail_budget": 0,
    },
    "riu": {
        "pause": 0.25,
        "needs_detail": False,
        "min_expected": 5,
        "default_pages": 1,
        "detail_budget": 0,
    },
    "barcelo": {
        "pause": 0.80,
        "needs_detail": False,
        "min_expected": 20,
        "default_pages": 30,
        "detail_budget": 0,
    },
    "melia": {
        "pause": 0.80,
        "needs_detail": True,
        "min_expected": 5,
        "default_pages": 10,
        "detail_budget": 250,
    },
    "palladium": {
        "pause": 0.80,
        "needs_detail": True,
        "min_expected": 1,
        "default_pages": 1,
        "detail_budget": 200,
    },
    "turijobs": {
        "pause": 0.70,
        "needs_detail": True,
        "min_expected": 5,
        "default_pages": 12,
        "detail_budget": 200,
    },
    "fuerte": {
        "pause": 0.80,
        "needs_detail": True,
        "min_expected": 1,
        "default_pages": 25,
        "detail_budget": 250,
    },
    "iman": {
        "pause": 0.80,
        "needs_detail": True,
        "min_expected": 1,
        "default_pages": 25,
        "detail_budget": 250,
    },
    "lidl": {
        "pause": 0.30,
        "needs_detail": False,
        "min_expected": 20,
        "default_pages": 14,
        "detail_budget": 0,
    },
    "mercadona": {
        "pause": 0.80,
        "needs_detail": True,
        "min_expected": 10,
        "default_pages": 25,
        "detail_budget": 150,
    },
    "correos": {
        "pause": 0.80,
        "needs_detail": True,
        "min_expected": 1,
        "default_pages": 8,
        "detail_budget": 80,
    },
    "jobeka": {
        "pause": 0.70,
        "needs_detail": True,
        "min_expected": 5,
        "default_pages": 6,
        "detail_budget": 80,
    },
    "dia": {
        "pause": 0.25,
        "needs_detail": False,
        "min_expected": 5,
        "default_pages": 5,
        "detail_budget": 0,
    },
    "infojobs": {
        "pause": 1.0,
        "needs_detail": True,
        "min_expected": 5,
        "default_pages": 1,
        "detail_budget": 100,
    },
    "randstad": {
        "pause": 1.0,
        "needs_detail": True,
        "min_expected": 20,
        "default_pages": 10,
        "detail_budget": 100,
    },
}


def meta(name: str | None) -> dict:
    return SOURCE_META.get(name or "", {})


def pause_for(name: str | None) -> float:
    return float(meta(name).get("pause", 0.45))


def needs_detail(name: str | None) -> bool:
    return bool(meta(name).get("needs_detail", True))


def min_expected(name: str | None) -> int:
    return int(meta(name).get("min_expected", 0))


def detail_budget(name: str | None) -> int:
    return int(meta(name).get("detail_budget", 200))
