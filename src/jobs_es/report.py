# src/jobs_es/report.py

from .source_meta import min_expected


def new_info() -> dict:
    return {
        "listed": 0,
        "new": 0,
        "updated": 0,
        "discarded": 0,
        "detail_fetched": 0,
        "cache_hits": 0,
        "parse_errors": 0,
        "http_errors": 0,
        "warnings": [],
    }


def add_warning(info: dict, warning: str) -> None:
    if warning not in info["warnings"]:
        info["warnings"].append(warning)


def normalize_source_info(
    name: str,
    raw_info,
    kept: int = 0,
    discarded: int = 0,
) -> dict:
    """
    Convierte lo que devuelva cada fuente en métricas estándar.
    Compatible con fuentes que devuelven int/str/dict.
    """
    info = new_info()

    if isinstance(raw_info, dict):
        if "total" in raw_info and "listed" not in raw_info:
            info["listed"] = raw_info["total"]
        for key in (
            "listed",
            "new",
            "updated",
            "discarded",
            "detail_fetched",
            "cache_hits",
            "parse_errors",
            "http_errors",
        ):
            if key in raw_info:
                info[key] = raw_info[key]
        for warning in raw_info.get("warnings", []):
            add_warning(info, str(warning))
        extra = {
            k: v
            for k, v in raw_info.items()
            if k not in info and k != "warnings"
        }
        if extra:
            info["extra"] = extra
    elif isinstance(raw_info, int):
        info["new"] = raw_info
        info["listed"] = raw_info + discarded
    else:
        info["raw"] = str(raw_info)
        info["new"] = kept
        info["listed"] = kept + discarded

    if info.get("new") is None:
        info["new"] = kept
    if info.get("discarded") is None:
        info["discarded"] = discarded
    if info.get("listed") is None:
        info["listed"] = int(info.get("new", 0)) + int(info.get("discarded", 0))

    expected = min_expected(name)
    if expected and int(info.get("listed", 0)) < expected:
        add_warning(info, "below_expected_minimum")

    return info
