"""RIU Hotels: feed JSON oficial de Teamtailor (jobs.riu.com/jobs.json).

schema.org JobPosting embebido; filtramos addressCountry == ES.
"""
import re

from .. import register, httpclient as hc
from ..models import Job
from ..normalize import classify_text, parse_salary, sector_of

FEED = "https://jobs.riu.com/jobs.json"


def _spain(jp: dict) -> tuple[bool, str]:
    locs = jp.get("jobLocation") or [jp.get("jobLocation")] if jp.get("jobLocation") else []
    if isinstance(locs, dict):
        locs = [locs]
    for L in locs:
        a = (L or {}).get("address") or {}
        if a.get("addressCountry") in ("ES", "España"):
            return True, (a.get("addressLocality") or "").strip()
    return False, ""


@register("riu")
def run(con, **_) -> tuple[list[Job], str]:
    d = hc.get_json(FEED)
    items = d.get("items") or []
    jobs: list[Job] = []
    for item in items:
        jp = item.get("_jobposting") or {}
        es, city = _spain(jp if isinstance(jp, dict) else {})
        if not es:
            continue
        title = (item.get("title") or jp.get("title") or "").strip()
        raw = (jp.get("description") if isinstance(jp, dict) else "") or \
              item.get("content_html") or ""
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw))
        h, f = classify_text(text)
        sal, sal_txt = parse_salary(text)
        url = item.get("url") or ""
        if not (title and url):
            continue
        jobs.append(Job(
            source="riu", url=url, title=title,
            company="RIU Hotels & Resorts",
            city=city.title(), province=city.title(),
            sector=sector_of(title, text),
            salary_text=sal_txt, hourly=sal,
            housing=h, food=f, direct=True,
            posted_at=(item.get("date_published") or "")[:10],
            text=text[:1500]))
    return jobs, f"{len(jobs)} en España (de {len(items)} del feed)"
