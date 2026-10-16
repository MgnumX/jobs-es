"""InfoJobs España — API pública oficial (api.infojobs.net).

Auth: HTTP Basic (client_id:client_secret), scope público.
Consulta: q="mozo de almacen" + q="plaza", province=zaragoza.
Detalle (budget-limited): /api/9/offer/{id} para texto completo.
"""
import base64
import os
import re
import time

from .. import register, httpclient as hc
from ..models import Job
from ..normalize import classify_text, is_ett, parse_salary, sector_of

API_LIST = "https://api.infojobs.net/api/9/offer"
QUERIES = ["mozo de almacen", "plaza"]


def _basic_auth() -> str:
    cid = os.environ.get("INFOJOBS_CLIENT_ID", "")
    sec = os.environ.get("INFOJOBS_CLIENT_SECRET", "")
    if not cid or not sec:
        return ""
    cred = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    return f"Basic {cred}"


def _auth_header() -> dict:
    tok = _basic_auth()
    return {"Authorization": tok} if tok else {}


def _search(q: str, pages: int = 5) -> list[dict]:
    """Devuelve lista de offers del API. Corta con página vacía o 2 fallos."""
    auth = _auth_header()
    if not auth:
        return []
    out: list[dict] = []
    fails = 0
    for page in range(1, pages + 1):
        try:
            resp = hc.get(API_LIST, source="infojobs", params={
                "q": q,
                "province": "zaragoza",
                "maxResults": 50,
                "page": page,
            }, headers=auth)
            data = resp.json()
        except Exception:
            fails += 1
            if fails >= 2:
                break
            continue
        offers = data.get("offers") or []
        if not offers:
            break
        out.extend(offers)
        fails = 0
    return out


def _detail(offer_id: str, auth: dict) -> str:
    """Detalle completo de una oferta. Devuelve texto plano o vacío."""
    for _ in range(2):
        try:
            resp = hc.get(
                f"https://api.infojobs.net/api/9/offer/{offer_id}",
                source="infojobs", headers=auth)
            data = resp.json()
            # cityPD is the full description
            return data.get("cityPD") or data.get("description") or ""
        except Exception:
            time.sleep(hc.PAUSE)
    return ""


@register("infojobs")
def run(con, *, detail_budget: int = 100, **_) -> tuple[list[Job], str]:
    from ..db import known_ids

    auth = _auth_header()
    if not auth:
        return [], "sin credenciales INFOJOBS_CLIENT_ID/SECRET"

    all_offers = {}
    for q in QUERIES:
        for offer in _search(q):
            lid = offer.get("link") or ""
            if lid and lid not in all_offers:
                all_offers[lid] = offer

    stubs = []
    for link, offer in all_offers.items():
        title = offer.get("title") or ""
        prov = (offer.get("province") or {}).get("value") or ""
        city = offer.get("city") or ""
        author = offer.get("author") or {}
        company = author.get("name") or ""
        posted = (offer.get("creationDate") or "")[:10]
        stubs.append(Job(
            source="infojobs", url=link, title=title.strip(),
            company=company, city=city.title(), province=prov.title(),
            sector=sector_of(title), posted_at=posted,
            direct=not is_ett(company),
        ))

    ids = {j.id for j in stubs}
    seen = known_ids(con, ids)
    fresh = [j for j in stubs if j.id not in seen]

    # enriquecer con detalle: salary del listado, texto del detalle
    kept = 0
    for j in fresh[:detail_budget]:
        sal_min = all_offers.get(j.url, {}).get("salaryMin")
        sal_max = all_offers.get(j.url, {}).get("salaryMax")
        salary_text = ""
        if sal_min and sal_max:
            salary_text = f"{sal_min} € - {sal_max} €"
        elif sal_min:
            salary_text = f"{sal_min} €"

        text = _detail(
            all_offers.get(j.url, {}).get("id") or "", auth)
        desc = f"{salary_text} {text[:2000]}" if text else salary_text

        h, f = classify_text(desc)
        sal, sal_txt = parse_salary(desc) if desc else (None, "")
        j.housing, j.food = h, f
        if sal:
            j.hourly, j.salary_text = sal, sal_txt
        elif salary_text:
            j.salary_text = salary_text
        j.sector = sector_of(j.title, desc)
        j.text = desc[:1500]
        kept += 1
        time.sleep(hc.PAUSE)

    # incluir los que ya existían con salario explícito
    out = [j for j in stubs if j.id in seen or j.hourly is not None or j.salary_text]

    return out, (f"{len(all_offers)} ofertas, {len(fresh)} nuevas, "
                 f"{kept} detalles")
