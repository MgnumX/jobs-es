"""Adecco España — DESACTIVADO (2026-08-25).

# ponytail: fuera del registro SOURCES; adecco.es 301→SPA global sin API.
Reactivar solo cuando devtools capture el endpoint real de la app/web nueva
y se reescriba como source activo con ese endpoint clavado.
"""
import re

from .. import register, httpclient as hc
from ..models import Job
from ..normalize import classify_text, is_ett, parse_salary, sector_of

PHENOM = ("https://www.adecco.es/api/apply/v2/jobs"
          "?domain=adecco.es&start={start}&num=50&sort_by=new")
SITEMAP_INDEX = "https://www.adecco.es/sitemap.xml"


def _phenom() -> tuple[list[Job], str]:
    jobs = []
    for start in (0,):
        d = hc.get(PHENOM.format(start=start)).json()
        for p in d.get("positions") or []:
            loc = p.get("location") or ""
            city = loc.split(",")[0].strip()
            title = p.get("name") or ""
            jobs.append(Job(
                source="adecco", url=p.get("canonicalPositionUrl") or
                f"https://www.adecco.es/es-es/job/{p.get('id')}",
                title=title, company="Adecco", city=city, province=city,
                sector=sector_of(title), direct=False,
                posted_at=(p.get("publishedDate") or "")[:10]))
    return jobs, f"{len(jobs)} via phenom"


_OFFER_URL = re.compile(r"<loc>\s*(https://www\.adecco\.es/es-es/job/[^<]+)\s*</loc>", re.I)


def _sitemap(con) -> tuple[list[Job], str]:
    from ..db import known_ids
    idx = hc.get(SITEMAP_INDEX).text
    subs = re.findall(r"<loc>\s*([^<]+\.xml)\s*</loc>", idx)
    urls: set[str] = set()
    for s in subs[:12]:  # techo deliberado: primeras 12 sub-sitemaps
        try:
            urls |= set(_OFFER_URL.findall(hc.get(s).text))
        except RuntimeError:
            continue
    stubs = [Job(source="adecco", url=u, title="") for u in sorted(urls)]
    fresh = [s for s in stubs if s.id not in known_ids(con, {x.id for x in stubs})][:150]
    jobs = []
    for u in fresh:
        try:
            text = hc.strip_tags(hc.get(u).text)
        except RuntimeError:
            continue
        t_m = re.search(r"\n\s*([^\n|]{4,90})\n\s*\n?Adecco", text)
        title = t_m.group(1).strip() if t_m else u.rstrip("/").split("/")[-1].replace("-", " ")
        h, f = classify_text(text)
        sal, sal_txt = parse_salary(text)
        jobs.append(Job(source="adecco", url=u, title=title, company="Adecco",
                        sector=sector_of(title, text), housing=h, food=f,
                        hourly=sal, salary_text=sal_txt, direct=False,
                        text=" ".join(text.split())[:1200]))
    return jobs, f"{len(urls)} en sitemap, {len(jobs)} detalles nuevos"


@register("adecco")
def run(con, **_) -> tuple[list[Job], str]:
    try:
        return _phenom()
    except Exception:
        pass
    try:
        return _sitemap(con)
    except Exception as e:
        return [], f"no disponible ({type(e).__name__})"
