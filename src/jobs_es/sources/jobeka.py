"""Jobeka — agregador logística (solo con pago explícito, sector logistica)."""
import re

from .. import httpclient as hc, register, report
from ..models import Job
from ..normalize import classify_text, parse_salary, sector_of

NAME = "jobeka"
BASE = "https://es.jobeka.com"
LIST = BASE + "/empleos-logistica?page={page}"

_RE_LINK = re.compile(r'href="(https://es\.jobeka\.com/oferta-[^"]+)"', re.I)


def _listing(pages: int = 8) -> dict[str, str]:
    out: dict[str, str] = {}
    fails = 0
    for page in range(1, pages + 1):
        url = LIST.format(page=page)
        try:
            html = hc.get(url, source=NAME).text
        except Exception:
            fails += 1
            if fails >= 2:
                break
            continue
        links = _RE_LINK.findall(html)
        if not links:
            fails += 1
            if fails >= 2:
                break
            continue
        uniq = []
        for l in links:
            # normalize: remove ?source
            base = l.split("?")[0]
            if base not in out:
                uniq.append(base)
        if not uniq:
            fails += 1
            if fails >= 2:
                break
            continue
        for link in uniq:
            # title hint from next <a> text? Use slug as fallback
            # Try to extract title near link
            # Look ahead 2000 chars for <a ...>Title</a>
            # Simpler: use slug
            try:
                # link like https://es.jobeka.com/oferta-528... -> need title from HTML near link
                # Find surrounding <h2> like earlier structure: <a ... oferta-...>Title</a>
                # Use regex for this specific link
                pat = re.compile(re.escape(link) + r'[^>]*>(.*?)</a>', re.S | re.I)
                m = re.search(pat.pattern, html, re.S | re.I)
                # Actually search directly
                m2 = re.search(r'href="' + re.escape(link) + r'"[^>]*>(.*?)</a>', html, re.S | re.I)
                title = hc.strip_tags(m2.group(1)).strip() if m2 else ""
            except Exception:
                title = ""
            if not title or len(title) < 5:
                # fallback slug not useful, use empty and detail will refine
                title = ""
            out[link.split("?")[0]] = title
        fails = 0
        if len(uniq) < 10:
            break
    return out


def _detail(url: str) -> dict:
    html = hc.get(url, source=NAME).text
    text = hc.strip_tags(html)
    # Title from <title> or <h1>
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = hc.strip_tags(m.group(1)).strip() if m else ""
    # Jobeka title often like "Ejecutivo/a Comercial junior- Sector Logística y Transporte Madrid | Jobeka" -> clean
    title = title.split("|")[0].strip()[:80]
    # Remove location suffix " Madrid"
    # Keep as is, sector will be logistica anyway
    sector = sector_of(title, text)
    if sector != "logistica":
        sector = "logistica"
    housing, food = classify_text(text)
    hourly, salary_text = parse_salary(text)
    return {"title": title, "text": text, "sector": sector, "housing": housing, "food": food, "hourly": hourly, "salary_text": salary_text}


@register("jobeka")
def run(con, *, pages: int = 6, detail_budget: int = 80, budget: int | None = None, opts: dict | None = None, **_) -> tuple[list[Job], dict]:
    if budget is not None:
        detail_budget = budget
    opts = opts or {}
    info = report.new_info()
    if opts.get("no_detail"):
        detail_budget = 0
    pages = pages or 6
    if pages == 12 and not opts.get("limit"):
        pages = 6
    try:
        listing = _listing(pages)
    except Exception:
        info["http_errors"] += 1
        return [], info
    info["listed"] = len(listing)
    if not listing:
        report.add_warning(info, "zero_cards")
        return [], info
    jobs: list[Job] = []
    for url, hint in listing.items():
        # city from Jobeka detail not in listing, leave empty, detail will refine via text location?
        # For now city empty, detail may contain location in title "Madrid"
        city = ""
        # try to extract city from hint " ... Madrid" last word
        if hint:
            parts = hint.rsplit(" ", 1)
            if len(parts) == 2 and len(parts[1]) > 3:
                city = parts[1].title()[:30]
        jobs.append(Job(source=NAME, url=url, title=hint, company="",
                        city=city, province=city, sector="logistica", direct=False))
    from ..db import known_ids
    seen = known_ids(con, {j.id for j in jobs})
    fresh = [j for j in jobs if j.id not in seen]
    info["new"] = len(fresh)
    to_fetch = fresh[:detail_budget]
    filtered: list[Job] = []
    for job in jobs:
        if job.id in seen:
            # keep seen regardless (already filtered before)
            filtered.append(job)
    for j in to_fetch:
        try:
            d = _detail(j.url)
        except Exception:
            info["http_errors"] += 1
            continue
        info["detail_fetched"] += 1
        # logistica pura: aunque sin €/h, se guarda para estimar vía convenio (como Turijobs)
        # ponytail: no exigir explicit para Jobeka agregador, si hay hourly se marca REAL si no ESTIMADO
        j.title = d["title"] or j.title or "Operario Logística"
        if not j.city and d["title"]:
            m = re.search(r"\b(Madrid|Barcelona|Valencia|Sevilla|Zaragoza|Málaga|Murcia|Bilbao|Vigo|Alicante|Granada|Valladolid|Córdoba|Girona|Tarragona|Castellón|Almería|Gipuzkoa|Navarra|Asturias)\b", d["title"], re.I)
            if m:
                j.city = m.group(1).title()
                j.province = j.city
        j.sector = "logistica"
        j.housing, j.food = d["housing"], d["food"]
        j.hourly = d["hourly"]
        j.salary_text = d["salary_text"]
        j.text = d["text"][:1500]
        filtered.append(j)
    # también incluir los no fetcheados (fuera de budget) como stubs logistica para no perder volumen
    for job in fresh[detail_budget:]:
        if job.id not in {j.id for j in filtered} and job.id not in seen:
            # keep stub as logistica sin salario (estimado luego)
            job.sector = "logistica"
            filtered.append(job)
    return filtered, info
