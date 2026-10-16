"""Randstad España — SSR listing de randstad.es/candidatos/ofertas-empleo.

El listado renderiza títulos, salario inline y ubicación en HTML del servidor.
Filtro: Zaragoza (descubre la URL filtrada del HTML, fallback cliente).
Detalle: /oferta/{slug}-{id}/ para descripción completa (turnos, carretilla, etc.).
"""
import re
import time

from .. import register, httpclient as hc
from ..models import Job
from ..normalize import classify_text, is_ett, parse_salary, sector_of

BASE = "https://www.randstad.es/candidatos/ofertas-empleo"

# Browser-like headers para evitar 403 anti-bot
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.5",
}

# Paginación Randstad: el patrón es /pg-N
_OFFER_RE = re.compile(
    r'<a[^>]+href="(/candidatos/ofertas-empleo/oferta/[^"]+)"[^>]*>',
    re.S,
)
_LOC_RE = re.compile(
    r"(?:operational|professional|randstad)\s*###\s*(.+?)\s+"
    r"([A-ZÁÉÍÓÚa-záéíóú\s()]+?)\s*-\s*Zaragoza\s+"
    r"([\d.,]+(?:\s*[-–]\s*[\d.,]+)?\s*€/[añoahmes]+)?",
    re.I,
)
_DATE_RE = re.compile(r"publicada el (\d{2}/\d{2}/\d{4})")
_SLUG_ID_RE = re.compile(r"/oferta/(.+?)-(\d{5,})")


def _fetch_page(url: str) -> str:
    try:
        resp = hc.get(url, source="randstad", headers=_HEADERS)
        return resp.text
    except Exception:
        return ""


def _find_province_filter(html: str) -> str | None:
    """Busca en el HTML el link del filtro de provincia Zaragoza."""
    m = re.search(r'href="([^"]*zaragoza[^"]*)"', html, re.I)
    return m.group(1) if m else None


def _parse_offers(html: str) -> list[dict]:
    """Extrae ofertas del HTML del listado. Devuelve [{url, title, city, salary_text, posted}]."""
    offers = []
    seen_urls = set()

    for m in _OFFER_RE.finditer(html):
        href = m.group(1)
        if href in seen_urls:
            continue
        seen_urls.add(href)

        # Contexto: 400 chars después del enlace
        pos = m.end()
        ctx = html[pos:pos + 400]
        ctx_text = re.sub(r"<[^>]+>", " ", ctx)

        title = ""
        city = ""
        salary_text = ""
        posted = ""

        # Buscar título: primer texto no vacío tras el enlace
        t_m = re.search(r">\s*([A-ZÁÉÍÓÚa-záéíóú\s\d/.,()]+?)\s*<", ctx[:200])
        if t_m:
            title = t_m.group(1).strip()

        # Ciudad y salario del contexto
        loc_m = _LOC_RE.search(ctx_text)
        if loc_m:
            city = loc_m.group(2).strip()
            salary_text = (loc_m.group(3) or "").strip()

        date_m = _DATE_RE.search(ctx_text)
        if date_m:
            posted = date_m.group(1)

        if not title:
            slug_m = _SLUG_ID_RE.search(href)
            if slug_m:
                title = slug_m.group(1).replace("-", " ").strip()

        full_url = f"https://www.randstad.es{href}"
        offers.append({
            "url": full_url,
            "title": title,
            "city": city,
            "salary_text": salary_text,
            "posted": posted,
        })

    return offers


def _detail_text(url: str) -> str:
    """Detalle de oferta. Devuelve texto plano o vacío."""
    html = _fetch_page(url)
    if not html or len(html) < 2000:
        return ""
    return hc.strip_tags(html)


@register("randstad")
def run(con, *, detail_budget: int = 100, **_) -> tuple[list[Job], str]:
    from ..db import known_ids
    from datetime import datetime

    # 1. Buscar URL filtrada de Zaragoza
    base_html = _fetch_page(BASE)
    if not base_html:
        return [], "no se pudo cargar listado randstad.es"

    filter_path = _find_province_filter(base_html)
    list_base = f"https://www.randstad.es{filter_path}" if filter_path else BASE

    # 2. Paginar (hasta 20 páginas, corta con vacío)
    all_offers = []
    for page in range(1, 21):
        url = f"{list_base}/pg-{page}" if page > 1 else list_base
        html = _fetch_page(url)
        offers = _parse_offers(html)
        if not offers:
            break
        all_offers.extend(offers)

    # 3. Filtrar solo Zaragoza (fallback si no hay filtro URL)
    if not filter_path:
        all_offers = [
            o for o in all_offers
            if "Zaragoza" in o.get("city", "")
        ]

    # 4. Construir Jobs
    stubs = []
    for o in all_offers:
        posted = ""
        if o["posted"]:
            try:
                posted = datetime.strptime(o["posted"], "%d/%m/%Y").strftime("%Y-%m-%d")
            except ValueError:
                pass
        stubs.append(Job(
            source="randstad", url=o["url"], title=o["title"].strip(),
            company="Randstad", city="Zaragoza", province="Zaragoza",
            sector="logistica", salary_text=o["salary_text"],
            posted_at=posted, direct=False,
        ))

    # 5. Enriquecer con salario y detalle
    seen = known_ids(con, {j.id for j in stubs})
    fresh = [j for j in stubs if j.id not in seen]

    kept = 0
    for j in fresh[:detail_budget]:
        # Parsear salario del listado
        if j.salary_text:
            sal, sal_txt = parse_salary(j.salary_text)
            if sal:
                j.hourly = sal
                j.salary_text = sal_txt

        # Texto del detalle para clasificar
        text = _detail_text(j.url)
        if text:
            desc = " ".join(text.split())
            h, f = classify_text(desc)
            j.housing, j.food = h, f
            if not j.hourly:
                sal2, sal_txt2 = parse_salary(desc)
                if sal2:
                    j.hourly, j.salary_text = sal2, sal_txt2
            j.text = desc[:1500]

        kept += 1
        time.sleep(hc.PAUSE)

    return stubs, (f"{len(all_offers)} ofertas Zaragoza, {len(fresh)} nuevas, "
                   f"{kept} detalles")
