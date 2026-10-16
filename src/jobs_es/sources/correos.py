"""Correos Express — SuccessFactors (logística pura, sueldo convenio/mensual explícito)."""
import re
from urllib.parse import urljoin

from .. import httpclient as hc, register, report
from ..models import Job
from ..normalize import classify_text, parse_salary, sector_of

NAME = "correos"
BASE = "https://empleo.correos.com"
# ponytail: sin q=logistica solo trae 1, con q= vacío trae 26/página y filtramos logistica post-fetch
LIST = BASE + "/search/?q=&locationsearch=Espa%C3%B1a&startrow={off}"

_RE_LINK = re.compile(r'href="(/job/[^"]+)"', re.I)


def _listing(pages: int = 8) -> dict[str, str]:
    out: dict[str, str] = {}
    fails = 0
    for page in range(pages):
        off = page * 25
        url = LIST.format(off=off)
        try:
            html = hc.get(url, source=NAME).text
        except Exception:
            fails += 1
            if fails >= 2:
                break
            continue
        links = _RE_LINK.findall(html)
        # dedupe, normalize
        uniq = []
        for l in links:
            full = urljoin(BASE, l)
            if full not in out and "/job/" in full:
                uniq.append(full)
        if not uniq:
            fails += 1
            if fails >= 2:
                break
            continue
        for u in uniq:
            # title hint from URL slug
            try:
                slug = u.split("/")[2]
                hint = slug.replace("-", " ").replace("%20", " ").strip()
                # slug like Madrid-Jóvenes-Talentos... -> take first meaningful
                hint = re.sub(r"Madrid\s*", "", hint, flags=re.I).strip()[:60]
            except Exception:
                hint = ""
            out[u] = hint
        fails = 0
        if len(uniq) < 5:
            # last page
            break
    return out


def _detail(url: str) -> dict:
    html = hc.get(url, source=NAME).text
    text = hc.strip_tags(html)
    # Title from <title> or h1
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = hc.strip_tags(m.group(1)).strip() if m else ""
    if not title or "Correos" in title and len(title) < 20:
        # fallback from URL slug
        try:
            slug = url.split("/")[2]
            title = slug.replace("-", " ").strip().title()[:80]
        except Exception:
            title = "Personal Correos"
    # cleanup title: remove location prefix Madrid- etc.
    title = re.sub(r"^Madrid\s*[-–]?\s*", "", title, flags=re.I).strip()
    sector = sector_of(title, text)
    housing, food = classify_text(text)
    hourly, salary_text = parse_salary(text)
    return {"title": title, "text": text, "sector": sector, "housing": housing, "food": food, "hourly": hourly, "salary_text": salary_text}


@register("correos")
def run(con, *, pages: int = 8, detail_budget: int = 80, budget: int | None = None, opts: dict | None = None, **_) -> tuple[list[Job], dict]:
    if budget is not None:
        detail_budget = budget
    opts = opts or {}
    info = report.new_info()
    if opts.get("no_detail"):
        detail_budget = 0
    pages = pages or 8
    if pages == 12 and not opts.get("limit"):
        pages = 8
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
        city = ""
        try:
            city = url.split("/")[2].split("-")[0].title()[:30]
        except Exception:
            city = ""
        # filtra logistica ya en stub si hint lo indica, sino deja que detail decida
        sec = sector_of(hint)
        jobs.append(Job(source=NAME, url=url, title=hint, company="Correos Express",
                        city=city, province=city, sector=sec, direct=True))
    from ..db import known_ids
    seen = known_ids(con, {j.id for j in jobs})
    fresh = [j for j in jobs if j.id not in seen]
    info["new"] = len(fresh)
    # only explicit pay? For logística pura queremos solo con €/h para no meter ruido
    # ponytail: Correos sin €/h no entra, como Iman
    to_fetch = fresh[:detail_budget]
    filtered: list[Job] = []
    for job in jobs:
        if job.id in seen:
            # seen ya estaba filtrado previamente si era logistica
            if job.sector == "logistica" or sector_of(job.title) == "logistica":
                filtered.append(job)
            else:
                # si seen era no-logistica, no lo reinsertes (evita acumular)
                continue
    for j in to_fetch:
        try:
            d = _detail(j.url)
        except Exception:
            info["http_errors"] += 1
            continue
        info["detail_fetched"] += 1
        txt = d["text"]
        # solo logistica
        if d["sector"] != "logistica":
            continue
        j.title = d["title"] or j.title
        j.sector = d["sector"]
        j.housing, j.food = d["housing"], d["food"]
        j.hourly = d["hourly"]
        j.salary_text = d["salary_text"] or ""
        j.text = txt[:1500]
        filtered.append(j)
    # stubs fuera de budget solo si hint ya era logistica
    for job in fresh[detail_budget:]:
        if job.id not in {j.id for j in filtered} and job.id not in seen:
            if job.sector == "logistica":
                filtered.append(job)
    return filtered, info
