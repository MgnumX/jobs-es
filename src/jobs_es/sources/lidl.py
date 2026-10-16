"""Lidl España: API empleo.lidl.es — sueldo anual explícito 100%."""
import json
import re

from .. import register, httpclient as hc
from ..models import Job
from ..normalize import classify_text, parse_salary, sector_of

API = "https://empleo.lidl.es/api/v1/search"
WEB = "https://empleo.lidl.es"

NAME = "lidl"


@register("lidl")
def run(con, *, pages: int = 14, detail_budget: int = 0, budget: int | None = None, opts: dict | None = None, **_) -> tuple[list[Job], dict]:
    from .. import report as report_mod
    opts = opts or {}
    info = report_mod.new_info()
    jobs: list[Job] = []
    # Lidl paginación: general={"page":1..N,"resultsPerPage":20} Total ~276
    # ponytail: cli default 12 deja Lidl incompleto (14*20=280); si es corrida completa sin --pages explícito pequeño, usa 14
    effective_pages = pages if pages else 14
    if effective_pages == 12 and not opts.get("limit"):
        effective_pages = 14
    max_pages = effective_pages
    for page in range(1, max_pages + 1):
        if opts.get("limit") and len(jobs) >= opts["limit"]:
            break
        general = json.dumps({"page": page, "resultsPerPage": 20}, ensure_ascii=False)
        params = {"general": general}
        try:
            data = hc.get(API, source=NAME, params=params).json()
        except Exception:
            info["http_errors"] += 1
            report_mod.add_warning(info, f"http_error_page_{page}")
            break
        items = data.get("jobs") or []
        meta = data.get("meta") or {}
        total = int(meta.get("totalCount") or 0)
        info["listed"] += len(items)
        if not items:
            break
        for j in items:
            title = (j.get("title") or "").strip()
            if not title:
                continue
            loc = j.get("location") or {}
            city = (loc.get("city") or "").strip()
            # fallback: parse from name "Antigua Polígono ..."
            if not city:
                name = loc.get("name") or ""
                # name like "Antigua Polígono Industrial ... / Store"
                city = name.split("/")[0].strip().split(",")[0][:40] if name else ""
            province = city
            salary_val = (j.get("salaryValue") or "").strip()
            # salaryNote adds context but salaryValue already has range
            hourly, salary_text = parse_salary(salary_val)
            # fallback: try combining with salaryNote if needed (already handled via parse)
            if not hourly and salary_val:
                hourly, salary_text = parse_salary(salary_val + " anual")
            # detalle URL
            url = j.get("jobDetailUrl") or j.get("recruitingUrl") or ""
            if not url:
                url = f"{WEB}/jobs/{j.get('requisitionId')}"
            # ensure https
            if url.startswith("/"):
                url = WEB + url
            company = (j.get("company") or "Lidl").strip()
            desc = ""
            # join desc fields for sector classification
            for k in ("descResponsibilities", "descHeader"):
                v = j.get(k)
                if v:
                    desc += hc.strip_tags(v) + " "
            housing, food = classify_text(title + " " + desc)
            sector = sector_of(title, desc)
            # posted date
            posted = (j.get("onlineFrom") or j.get("created") or "")[:10]
            job = Job(source=NAME, url=url, title=title, company=company,
                      city=city.title()[:40], province=province.title()[:40],
                      sector=sector, salary_text=salary_text, hourly=hourly,
                      housing=housing, food=food, direct=True,
                      posted_at=posted, text=desc[:1500])
            # dedupe by URL within this run (Lidl IDs are unique via requisitionId but URL dedupe suffices)
            jobs.append(job)
            if opts.get("limit") and len(jobs) >= opts["limit"]:
                break
        # stop if we have fetched all total
        if total and len(jobs) >= total:
            break
        if len(items) < 20:
            break
    # dedupe by id (in case API repeats)
    uniq = {}
    for job in jobs:
        if job.id not in uniq:
            uniq[job.id] = job
    jobs = list(uniq.values())
    # ponytail: calcula fresh real para reporte (como turijobs/melia)
    try:
        from ..db import known_ids
        seen = known_ids(con, {j.id for j in jobs})
        info["new"] = len([j for j in jobs if j.id not in seen])
    except Exception:
        info["new"] = len(jobs)
    return jobs, info
