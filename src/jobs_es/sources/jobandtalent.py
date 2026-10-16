"""JobandTalent: API JSON interna (/job_opportunities) — datos estructurados."""
import re
import unicodedata

from .. import register, httpclient as hc
from ..models import Job
from ..normalize import classify_text, period_hourly, sector_of

API = "https://jobs.jobandtalent.com/job_opportunities"
HDRS = {"Accept": "application/json", "Content-Type": "application/json",
        "X-Organization": "Jobandtalent"}

# Provincias con más volumen logístico/hostelero en JT (EDITAR A GUSTO;
# Canarias/Las Palmas devuelven 0 hoy — re-agregar cuando JT publique ahí)
PROVINCES = ["madrid", "barcelona", "valencia", "sevilla", "zaragoza", "malaga",
             "murcia", "vizcaya", "a-coruna", "islas-baleares", "guadalajara",
             "toledo", "alicante", "girona", "tarragona", "cordoba", "granada",
             "alava", "valladolid", "cadiz", "gipuzkoa", "castellon", "huesca",
             "almeria", "salamanca"]


def _slugify(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


_STREETY = re.compile(r"(calle|avenida|avda|camino|pol[ií]gono|parcela|kalea|pla[çc]a|carretera|\d)", re.I)


def _loc(loc: str) -> tuple[str, str]:
    """'Calle X 12, 19171, Ciudad, Provincia, Spain' → (ciudad, provincia).
    Si la parte candidata a ciudad es una calle/número, sube un nivel."""
    p = [x.strip() for x in (loc or "").split(",")]
    if len(p) >= 4 and p[-1].lower().startswith(("spain", "espa")):
        city, prov = p[-3], p[-2]
        if _STREETY.search(city):  # la "ciudad" era un CP/calle; la provincia manda
            city = prov
        return city, prov
    return (p[0] if p else ""), ""


@register("jobandtalent")
def run(con, *, detail_budget: int = 200, **_) -> tuple[list[Job], str]:
    jobs: dict[str, Job] = {}
    pages_hit = 0
    empty_provs = 0
    for prov in PROVINCES:
        page = 1
        while page <= 8:  # techo cortesía por provincia y corrida
            try:
                d = hc.get_json(API, params={"country_code": "ES",
                                             "provinces[]": prov, "page": page},
                                headers=HDRS)
            except Exception:
                break
            meta = d.get("meta") or {}
            items = (d.get("data") or {}).get("jobOpportunities") or []
            for x in items:
                pay = x.get("payRate") or {}
                sal = pay.get("baseSalary")
                period = pay.get("baseSalaryPeriod") or ""
                hourly = period_hourly(sal, period)
                sal_txt = f"{sal} €/{'h' if 'hour' in period else 'mes'}" if sal else ""
                city, prov_name = _loc(x.get("formattedLocation", ""))
                title = x.get("title") or ""
                desc = re.sub(r"\s+", " ", x.get("description") or "")
                h, f = classify_text(desc)
                fn = x.get("jobFunctionSlug") or "ofertas"
                pslug = _slugify(prov_name) or prov
                url = f"https://jobs.jobandtalent.com/es/{fn}/{pslug}/{x.get('slug')}"
                # dedupe: JT repite la misma oferta como "versiones" distintas
                jobs[f"{title}|{x.get('companyName')}|{city}"] = Job(
                    source="jobandtalent", url=url,
                    title=title, company=(x.get("companyName") or "").strip(),
                    city=city, province=prov_name.title() or prov.title(),
                    sector=sector_of(title, desc),
                    salary_text=sal_txt, hourly=hourly,
                    housing=h, food=f, direct=False,
                    posted_at=(x.get("createdAt") or "")[:10],
                    text=desc[:1200])
            pages_hit += 1
            total_pages = int(meta.get("totalPages") or 1)
            if not items or page >= total_pages:
                if not items:
                    empty_provs += 1
                break
            page += 1
    return list(jobs.values()), (f"{len(jobs)} ofertas via API "
                                 f"({pages_hit} páginas, {empty_provs} provincias vacías)")
