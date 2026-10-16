"""Fuerte Group (Bizneo HR): listado SSR + detalle por oferta nueva.

jobs.grupoelfuerte.com — cadena hotelera Costa del Sol/Cádiz/Ibiza,
muchas ofertas con 🏠 alojamiento para no residentes. Sin anti-bot.
"""
import datetime as dt
import re

from .. import register, httpclient as hc
from ..models import Job
from ..normalize import classify_text, parse_salary, sector_of

BASE = "https://jobs.grupoelfuerte.com"
LIST = BASE + "/jobs?page={n}"

_ANCHOR = re.compile(
    r'<a[^>]+href="(' + re.escape(BASE) + r'/jobs/[^"]+)"[^>]*>(.*?)</a>', re.S)
_MESES = {m: i for i, m in enumerate(
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre "
    "noviembre diciembre".split(), 1)}


_MODALIDAD = {"presencial", "híbrido", "hibrido", "teletrabajo/remoto", "remoto"}


def _title_from(inner: str) -> str:
    """El título es el trozo más largo del ancla (la cola suele ser ciudad/modalidad)."""
    import html as _html
    parts = [_html.unescape(p.strip())
             for p in re.sub(r"<[^>]+>", "|", inner).split("|") if p.strip()]
    real = [p for p in parts if p.lower() not in _MODALIDAD]
    return max(real, key=len) if real else ""


def _listing(pages: int = 25) -> dict[str, str]:
    """{url: título}. Corta con 2 fallos de red seguidos o página vacía."""
    out: dict[str, str] = {}
    fails = 0
    for n in range(1, pages + 1):
        try:
            html = hc.get(LIST.format(n=n)).text
        except RuntimeError:
            fails += 1
            if fails >= 2:
                break
            continue
        before = len(out)
        for url, inner in _ANCHOR.findall(html):
            t = _title_from(inner)
            if url not in out and t:
                out[url] = t
        if len(out) == before:
            fails += 1
            if fails >= 2:
                break
            continue
        fails = 0
    return out


def _detail(url: str) -> str:
    """Texto del detalle con reintento corto (el dominio a veces suelta cuerpos vacíos)."""
    for attempt in range(3):
        try:
            html = hc.get(url).text
        except RuntimeError:
            html = ""
        if len(html) > 5000:
            return hc.strip_tags(html)
        time.sleep(1.2)
    return ""


def _iso_es(s: str) -> str:
    m = re.search(r"(\d{1,2}) de (\w+)(?: de (\d{4}))?", s)
    if not m or m.group(2).lower() not in _MESES:
        return ""
    year = int(m.group(3)) if m.group(3) else dt.date.today().year
    return f"{year}-{_MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


@register("fuerte")
def run(con, *, pages: int = 25, detail_budget: int = 250, **_) -> tuple[list[Job], str]:
    from ..db import known_ids

    def make(url, title):
        return Job(source="fuerte", url=url, title=title.strip(),
                   company="Fuerte Group", direct=True)

    listings = _listing(pages)
    jobs = [make(u, t) for u, t in listings.items()]
    seen = known_ids(con, {j.id for j in jobs})
    fresh = [j for j in jobs if j.id not in seen]
    fetched = 0
    import time
    for j in fresh[:detail_budget]:
        text = _detail(j.url)
        if not text:
            continue
        fetched += 1
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        # ciudad: primera línea tras '¡Aplica ahora!'
        city = ""
        try:
            i0 = lines.index("¡Aplica ahora!")
            city = lines[i0 + 1][:40]
        except ValueError:
            pass
        posted = ""
        try:
            ip = lines.index("Publicada")
            posted = _iso_es(lines[ip + 1])
        except ValueError:
            pass
        desc = " ".join(text.split())
        h, f = classify_text(text)
        sal, sal_txt = parse_salary(text)
        j.city = city.title()
        j.province = j.city
        j.housing, j.food = h, f
        j.hourly, j.salary_text = sal, sal_txt
        j.sector = sector_of(j.title, desc)
        j.posted_at = posted
        j.text = desc[:1500]
    return jobs, (f"{len(listings)} listadas, {len(fresh)} nuevas, "
                  f"{fetched} detalles")


def _unused():
    assert hc.PAUSE >= 0
