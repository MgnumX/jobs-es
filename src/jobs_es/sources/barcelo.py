"""Barceló Hotel Group: API Workday CXS (POST documentado de facto).

barcelo.wd3.myworkdayjobs.com — 2ª cadena de España, ~526 puestos.
"""
import re

from .. import register, httpclient as hc
from ..models import Job
from ..normalize import classify_text, sector_of

API = ("https://barcelo.wd3.myworkdayjobs.com/wday/cxs/barcelo/"
       "Barcelo_Careers/jobs")
WEB = "https://barcelo.wd3.myworkdayjobs.com/es/Barcelo_Careers"
PAGE = 20
MAX_PAGES = 30  # techo duro: 600 puestos


@register("barcelo")
def run(con, **_) -> tuple[list[Job], str]:
    jobs: list[Job] = []
    total = 0
    for page in range(MAX_PAGES):  # control matemático como Amazon
        offset = page * PAGE
        try:
            d = hc.post_json(API, {"appliedFacets": {}, "limit": PAGE,
                                   "offset": offset, "searchText": ""})
        except RuntimeError:
            break  # salvavidas; el límite real lo marca `total`
        total = int(d.get("total") or total)
        for p in d.get("jobPostings") or []:
            title = (p.get("title") or "").strip()
            path = p.get("externalPath") or ""
            if not (title and path):
                continue
            locs = [x.strip() for x in (p.get("locationsText") or "").split(",")]
            city = locs[-1] if len(locs) > 1 else (locs[0] if locs else "")
            h, f = classify_text(title)
            jobs.append(Job(
                source="barcelo", url=WEB + path, title=title,
                company="Barceló Hotel Group",
                city=(city or "").title(), province=(city or "").title(),
                sector=sector_of(title),
                housing=h, food=f, direct=True,
                posted_at="",
                text=title[:400]))
        if not d.get("jobPostings") or offset + PAGE >= min(total, MAX_PAGES * PAGE):
            break
    # ponytail: sin detalle Barceló (0/363 con alojamiento hoy), re-añadir si housing supera 5%
    return jobs, f"{len(jobs)} de {total} totales"


def _unused():
    assert hc.PAUSE >= 0
