"""Palladium Hotel Group (iCIMS): listado SSR /search-jobs, detalles solo nuevos.

Hard Rock Ibiza/Tenerife/Marbella, Only YOU, Grand Palladium…
"""
import re
from urllib.parse import unquote

from .. import register, httpclient as hc
from ..models import Job
from ..normalize import classify_text, parse_salary, sector_of

LISTING = "https://jobs.palladiumhotelgroup.com/search-jobs"
_ANCHOR = re.compile(r'<a[^>]+href="(/job/[^"]+)"[^>]*>(.*?)</a>', re.S)


def _title_from(inner: str) -> str:
    parts = [p.strip() for p in re.sub(r"<[^>]+>", "|", inner).split("|") if p.strip()]
    return max(parts, key=len) if parts else ""


def _city_from_path(path: str) -> str:
    # /job/{Ciudad}-{Hotel}-{Puesto}-{cp}/{id}/ → primer token antes de '-'
    slug = unquote(path.split("/")[2])
    return slug.split("-")[0].replace("_", " ").strip().title()


@register("palladium")
def run(con, *, detail_budget: int = 200, **_) -> tuple[list[Job], str]:
    from ..db import known_ids
    html = hc.get(LISTING).text
    found: dict[str, str] = {}
    for path, inner in _ANCHOR.findall(html):
        t = _title_from(inner)
        if t and path not in found:
            found[path] = t
    jobs = []
    for path, title in found.items():
        city = _city_from_path(path)
        jobs.append(Job(source="palladium", url=LISTING.rstrip("/") + path,
                        title=title, company="Palladium Hotel Group",
                        city=city, province=city,
                        sector=sector_of(title), direct=True))
    seen = known_ids(con, {j.id for j in jobs})
    fresh = [j for j in jobs if j.id not in seen][:detail_budget]
    fetched = 0
    import time
    for j in fresh:
        try:
            dhtml = hc.get(j.url).text
        except RuntimeError:
            dhtml = ""
        if len(dhtml) < 3000:
            time.sleep(1.2)
            try:
                dhtml = hc.get(j.url).text
            except RuntimeError:
                dhtml = ""
        if dhtml:
            fetched += 1
            text = hc.strip_tags(dhtml)
            j.housing, j.food = classify_text(text)
            j.hourly, j.salary_text = parse_salary(text)
            desc = " ".join(text.split())
            j.sector = sector_of(j.title, desc)
            j.text = desc[:1500]
    return jobs, f"{len(found)} listadas, {len(fresh)} nuevas, {fetched} detalles"
