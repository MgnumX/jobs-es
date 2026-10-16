"""DIA España: Teamtailor jobs.json — logística pura (filtrado sector logistica)."""
import re

from .. import register, httpclient as hc
from ..models import Job
from ..normalize import classify_text, parse_salary, sector_of

FEED = "https://empleo.dia.es/jobs.json"


@register("dia")
def run(con, **_) -> tuple[list[Job], str]:
    jobs: list[Job] = []
    url = FEED
    total = 0
    pages = 0
    while url and pages < 5:  # 5*100=500 max, suficiente
        pages += 1
        try:
            d = hc.get(url, source="dia").json()
        except Exception:
            break
        items = d.get("items") or []
        total += len(items)
        for item in items:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            raw = item.get("content_html") or ""
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw))
            # solo logistica pura: filtra por título para no coger Cajero que menciona "mercancía" en la descripción
            if sector_of(title) != "logistica":
                continue
            url_job = item.get("url") or ""
            if not url_job:
                continue
            h, f = classify_text(text)
            sal, sal_txt = parse_salary(text)
            # city from _jobposting if available
            jp = item.get("_jobposting") or {}
            city = ""
            if isinstance(jp, dict):
                locs = jp.get("jobLocation")
                if isinstance(locs, dict):
                    locs = [locs]
                if isinstance(locs, list):
                    for L in locs:
                        a = (L or {}).get("address") or {}
                        if a.get("addressLocality"):
                            city = a.get("addressLocality").strip()
                            break
            jobs.append(Job(source="dia", url=url_job, title=title, company="DIA España",
                            city=city.title()[:40], province=city.title()[:40],
                            sector="logistica", salary_text=sal_txt, hourly=sal,
                            housing=h, food=f, direct=True,
                            posted_at=(item.get("date_published") or "")[:10],
                            text=text[:1500]))
        # next_url for pagination
        nxt = d.get("next_url") or d.get("nextUrl")
        if nxt and nxt != url:
            url = nxt
        else:
            break
    return jobs, f"{len(jobs)} logística de {total} del feed ({pages} páginas)"
