"""Turijobs: listado SSR paginado + detalle por oferta nueva."""
import hashlib
import re
from urllib.parse import urljoin

from .. import httpclient, register, report, source_debug
from ..models import Job
from ..normalize import classify_text, is_ett, parse_salary, sector_of

NAME = "turijobs"
BASE_URL = "https://www.turijobs.com"

_COMPANY = re.compile(r'/es/empresa/[a-zA-Z0-9-]+"[^>]*>.*?<span[^>]*>\s*([^<]+?)\s*</span>', re.S)
_LOC = re.compile(r'/es/ofertas-trabajo/([a-z0-9-]+)"')
_DATE = re.compile(r'Publicada el (\d{2}/\d{2}/\d{2})')


def fetch_page(page: int, opts: dict | None = None) -> str:
    url = f"{BASE_URL}/es/ofertas-trabajo?page={page}"
    resp = httpclient.get(url, source=NAME)
    source_debug.maybe_save_fixture(NAME, f"page_{page}", resp.text, opts)
    return resp.text


def parse_listing(html: str) -> list[dict]:
    items = _parse_listing_generic(html)
    if items:
        return items
    items = _parse_listing_selectolax(html)
    if items:
        return items
    items = _parse_listing_regex(html)
    return items


def _parse_listing_generic(html: str) -> list[dict]:
    """Nuevo layout Turijobs 2026: <a href=/oferta-trabajo/...><h2>Título</h2></a>.
    Regex directo href→h2, más robusto que clases Tailwind cambiantes."""
    pat = re.compile(r'href="(https://www\.turijobs\.com/es/oferta-trabajo/[^"]+)"[^>]*>.*?<h2[^>]*>(.*?)</h2>', re.S | re.I)
    out = []
    for m in pat.finditer(html):
        url = m.group(1)
        title_raw = m.group(2)
        title = httpclient.strip_tags(title_raw).strip()
        window = html[m.start():m.start() + 6000]
        comp_m = _COMPANY.search(window)
        loc_m = _LOC.search(window)
        out.append({
            "url": url,
            "title": title,
            "company": comp_m.group(1).strip() if comp_m else "",
            "loc": loc_m.group(1).replace("-", " ") if loc_m else "",
        })
    # dedupe por url manteniendo orden
    seen = {}
    for it in out:
        if it["url"] not in seen:
            seen[it["url"]] = it
    return list(seen.values())


def _parse_listing_selectolax(html: str) -> list[dict]:
    try:
        from selectolax.parser import HTMLParser
    except ImportError:
        return []
    tree = HTMLParser(html)
    out = []
    for card in tree.css("div.rounded-lg.shadow"):
        a = card.css_first("a[href]")
        h3 = card.css_first("h3")
        h2 = card.css_first("h2")
        if not a:
            continue
        href = a.attributes.get("href") or ""
        if not href or "/es/oferta-trabajo/" not in href:
            continue
        url = urljoin(BASE_URL, href)
        title = ""
        if h2:
            title = h2.text(strip=True)
        elif h3:
            title = h3.text(strip=True)
        # company/loc from card text fallback
        html_card = card.html or ""
        comp_m = _COMPANY.search(html_card)
        loc_m = _LOC.search(html_card)
        out.append({
            "url": url,
            "title": title,
            "company": comp_m.group(1).strip() if comp_m else "",
            "loc": loc_m.group(1).replace("-", " ") if loc_m else "",
        })
    return out


def _parse_listing_regex(html: str) -> list[dict]:
    out = []
    chunks = re.split(r"rounded-lg shadow-", html)[1:]
    for chunk in chunks:
        href_m = re.search(r'href="(' + re.escape(BASE_URL) + r'/es/oferta-trabajo/[^"]+)"', chunk)
        if not href_m:
            continue
        url = href_m.group(1)
        # h3 legacy → h2 actual; intenta ambos
        title_m = re.search(r"<h3[^>]*>(.*?)</h3>", chunk, re.S | re.I)
        if not title_m:
            title_m = re.search(r"<h2[^>]*>(.*?)</h2>", chunk, re.S | re.I)
        title = httpclient.strip_tags(title_m.group(1)).strip() if title_m else ""
        comp_m = _COMPANY.search(chunk)
        loc_m = _LOC.search(chunk)
        out.append({
            "url": url,
            "title": title,
            "company": comp_m.group(1).strip() if comp_m else "",
            "loc": loc_m.group(1).replace("-", " ") if loc_m else "",
        })
    return out


def parse_detail(html: str) -> dict:
    title = ""
    try:
        from selectolax.parser import HTMLParser
        tree = HTMLParser(html)
        h1 = tree.css_first("h1")
        if h1:
            title = h1.text(strip=True)
        body = tree.body.text(separator="\n", strip=True) if tree.body else httpclient.strip_tags(html)
        if not title:
            # fallback regex si selectolax no encontró h1 (Next.js SSR dentro de JSON)
            m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
            if m:
                title = httpclient.strip_tags(m.group(1)).strip()
        return {"title": title, "text": body}
    except Exception:
        pass
    # fallback sin selectolax
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    if m:
        title = httpclient.strip_tags(m.group(1)).strip()
    return {"title": title, "text": httpclient.strip_tags(html)}


def fetch_detail(url: str, info: dict, opts: dict | None = None):
    use_cache = bool((opts or {}).get("use_cache", True))
    try:
        resp = httpclient.get(url, source=NAME, cache=use_cache, cache_ttl_hours=24*7)
    except Exception as e:
        info["http_errors"] += 1
        raise
    info["detail_fetched"] += 1
    if getattr(resp, "from_cache", False):
        info["cache_hits"] += 1
    label = "detail_" + hashlib.sha1(url.encode()).hexdigest()[:10]
    source_debug.maybe_save_fixture(NAME, label, resp.text, opts)
    try:
        return parse_detail(resp.text)
    except Exception:
        info["parse_errors"] += 1
        return {"text": httpclient.strip_tags(resp.text)}


@register("turijobs")
def run(con, *, pages: int = 12, detail_budget: int = 200, budget: int | None = None, opts: dict | None = None, **kwargs):  # ponytail: budget alias
    if budget is not None:
        detail_budget = budget
    opts = opts or {}
    info = report.new_info()
    if opts.get("no_detail"):
        detail_budget = 0

    jobs: list[Job] = []
    seen_urls: dict[str, dict] = {}

    for page in range(1, pages + 1):
        if opts.get("limit") and len(seen_urls) >= opts["limit"]:
            break
        try:
            html = fetch_page(page, opts)
        except Exception:
            info["http_errors"] += 1
            report.add_warning(info, f"http_error_page_{page}")
            break
        cards = parse_listing(html)
        info["listed"] += len(cards)
        if not cards and len(html) > 5000:
            report.add_warning(info, "zero_cards")
            source_debug.maybe_save_debug(NAME, f"page_{page}", html, opts)

        for card in cards:
            if opts.get("limit") and len(seen_urls) >= opts["limit"]:
                break
            url = card["url"]
            if url not in seen_urls:
                seen_urls[url] = card

    # build Job stubs
    for url, card in seen_urls.items():
        jobs.append(Job(source=NAME, url=url, title=card["title"], company=card.get("company",""),
                        city=card.get("loc","").title(), province=card.get("loc","").title(),
                        sector=sector_of(card["title"]), direct=not is_ett(card.get("company",""))))

    from ..db import known_ids
    seen_ids = known_ids(con, {j.id for j in jobs})
    fresh = [j for j in jobs if j.id not in seen_ids]

    for j in fresh[:detail_budget]:
        if opts.get("no_detail"):
            break
        try:
            detail = fetch_detail(j.url, info, opts)
        except Exception:
            continue
        text = detail.get("text", "")
        title = (detail.get("title") or "").strip()
        if title:
            j.title = title
        j.housing, j.food = classify_text(text)
        j.hourly, j.salary_text = parse_salary(text)
        m = _DATE.search(text)
        j.posted_at = m.group(1) if m else ""
        j.sector = sector_of(j.title, text)
        j.text = text[:1500]

    info["new"] = len([j for j in jobs if j.id not in seen_ids])
    return jobs, info
