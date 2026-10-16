"""Amazon España: API JSON pública de amazon.jobs."""
import datetime as dt

from .. import register, httpclient as hc
from ..models import Job
from ..normalize import sector_of

API = ("https://www.amazon.jobs/en/search.json?country=ESP&sort=recent"
       "&result_limit=100&offset={off}")

# ponytail: Amazon no publica €/h; estimación convenio+extras 2026 (~22.260€/año).
AMAZON_HOURLY_EST = 10.60

_PROVINCE_FIX = {
    "Community of Madrid": "Madrid", "Catalonia": "Barcelona",
    "Andalusia": "Sevilla", "Region of Murcia": "Murcia",
    "Aragon": "Zaragoza", "Castile-La Mancha": "Toledo",
}


def _city(loc: str) -> tuple[str, str]:
    parts = [p.strip() for p in (loc or "").split(",")]
    city = parts[0] if parts else ""
    province = parts[1] if len(parts) > 1 else ""
    return city, _PROVINCE_FIX.get(province, province)


@register("amazon")
def run(con, *, max_pages: int = 10, **_) -> tuple[list[Job], str]:
    """Control principal: `hits` de la 1ª petición fija las iteraciones
    (min(ceil(hits/100), techo API=10 páginas). El try/except es solo la
    salvavidas secundaria por si el endpoint cambia su límite real."""
    jobs: list[Job] = []
    total = 0
    for page in range(max_pages):
        off = page * 100
        try:
            d = hc.get(API.format(off=off)).json()
        except RuntimeError:
            break
        total = int(d.get("hits") or total)
        batch = d.get("jobs") or []
        for j in batch:
            city, prov = _city(j.get("normalized_location", ""))
            jobs.append(Job(
                source="amazon",
                url="https://www.amazon.jobs" + j.get("job_path", ""),
                title=(j.get("title") or "").strip(),
                company=j.get("company_name") or "Amazon",
                city=city, province=prov,
                sector=sector_of(j.get("title") or "", "almacen logistica"),
                salary_text=f"~{AMAZON_HOURLY_EST:.2f} €/h (est. convenio)",
                hourly=AMAZON_HOURLY_EST,
                direct=True,
                posted_at=_iso(j.get("posted_date", "")),
            ))
        if not batch or off + 100 >= min(total, max_pages * 100):
            break
    return jobs, f"{len(jobs)} de {total} totales"


def _iso(s: str) -> str:
    try:
        return dt.datetime.strptime(s, "%B %d, %Y").date().isoformat()
    except ValueError:
        return s[:10]
