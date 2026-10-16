"""CLI: uv run jobs-es [--only a,b] [--pages N] [--budget N] [--build-only]"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import SOURCES, report
from . import db as dbmod
from .db import all_rows, connect, upsert
from .html import build
from . import normalize
from . import sources as _sources  # noqa: F401 — registra las fuentes


def main(argv=None):
    ap = argparse.ArgumentParser(prog="jobs-es")
    ap.add_argument("--only", help="fuentes separadas por coma")
    ap.add_argument("--pages", type=int, default=12, help="páginas Turijobs")
    ap.add_argument("--budget", type=int, default=200,
                    help="máx detalles nuevos por fuente y corrida")
    ap.add_argument("--build-only", action="store_true",
                    help="regenerar HTML sin scrapear")
    ap.add_argument("--no-detail", action="store_true", help="No pedir detalles")
    ap.add_argument("--no-cache", action="store_true", help="No usar cache de detalles")
    ap.add_argument("--save-fixtures", action="store_true", help="Guarda HTML/JSON para tests")
    ap.add_argument("--debug-html", action="store_true", help="Guarda HTML cuando parseo vacío")
    ap.add_argument("--limit", type=int, default=0, help="Limita nuevas por fuente para pruebas")

    args = ap.parse_args(argv)

    opts = {
        "no_detail": args.no_detail,
        "use_cache": not args.no_cache,
        "save_fixtures": args.save_fixtures,
        "debug_html": args.debug_html,
        "limit": args.limit,
    }

    con = connect()
    run_report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "sources": {},
    }
    if args.build_only:
        try:
            prev = json.loads(Path("data/report.json").read_text(encoding="utf-8"))
            run_report["sources"] = prev.get("sources", {})
            # keep original started_at if exists
            if prev.get("started_at"):
                run_report["started_at"] = prev["started_at"]
        except Exception:
            pass

    if not args.build_only:
        names = args.only.split(",") if args.only else list(SOURCES)
        unknown = set(names) - set(SOURCES)
        if unknown:
            sys.exit(f"fuentes desconocidas: {unknown}; válidas: {list(SOURCES)}")
        for name in names:
            started = time.monotonic()
            try:
                fn = SOURCES[name]
                try:
                    jobs, raw_info = fn(con, pages=args.pages, detail_budget=args.budget, budget=args.budget, opts=opts)
                except TypeError:
                    try:
                        jobs, raw_info = fn(con, pages=args.pages, budget=args.budget, opts=opts)
                    except TypeError:
                        jobs, raw_info = fn(con, pages=args.pages, budget=args.budget)

                if args.limit and len(jobs) > args.limit:
                    jobs = jobs[:args.limit]

                kept = []
                discarded = 0
                for row in jobs:
                    if (normalize.is_excluded(row.title)
                            or row.sector == "hosteleria"
                            or (len(row.text or "") > 80 and normalize.is_excluded_text(row.text))):
                        discarded += 1
                        continue
                    row.urgent = row.urgent or normalize.is_urgent(row.title, row.text)
                    kept.append(row)

                for row in kept:
                    dbmod.upsert(con, row.row())

                info = report.normalize_source_info(name, raw_info, kept=len(kept), discarded=discarded)
                info["elapsed_ms"] = int((time.monotonic() - started) * 1000)
                run_report["sources"][name] = {"ok": True, **info}
                warn_txt = f" warnings={info['warnings']}" if info["warnings"] else ""
                print(f"[ok] {name}: listed={info['listed']} kept={len(kept)} discarded={discarded} detail={info['detail_fetched']} cache={info['cache_hits']} http_err={info['http_errors']} parse_err={info['parse_errors']}{warn_txt}")
            except Exception as e:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                run_report["sources"][name] = {"ok": False, "error": repr(e), "elapsed_ms": elapsed_ms}
                print(f"[X ] {name}: {e}", file=sys.stderr)
                continue

    dbmod.refresh_active(con, days=14)
    try:
        dbmod.score_rows(con)
    except Exception:
        pass

    rows = all_rows(con, only_active=True)
    total = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    active = con.execute("SELECT COUNT(*) FROM jobs WHERE active=1").fetchone()[0]
    run_report["finished_at"] = datetime.now(timezone.utc).isoformat()
    run_report["total_jobs"] = total
    run_report["active_jobs"] = active
    # escribir el reporte ANTES de build(): html.build lee report.json para la
    # línea de estado; si se escribe después, el HTML muestra el reporte viejo.
    Path("data/report.json").write_text(json.dumps(run_report, indent=2, ensure_ascii=False), encoding="utf-8")

    out = build(rows)

    print(f"\nHTML: {out}  ({active}/{total} activas)")
    if any(not v.get("ok") for v in run_report["sources"].values()):
        print(f"Fuentes FAIL: {[k for k,v in run_report['sources'].items() if not v.get('ok')]}", file=sys.stderr)


if __name__ == "__main__":
    main()
