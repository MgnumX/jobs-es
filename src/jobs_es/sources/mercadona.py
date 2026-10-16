"""Mercadona: Avature portal — sueldo mensual explícito 100% (Retribución mensual)."""
import re
from urllib.parse import urljoin

from .. import httpclient as hc, register, report, source_debug
from ..models import Job
from ..normalize import classify_text, parse_salary, sector_of

NAME = "mercadona"
BASE = "https://mercadona.avature.net"
LIST = BASE + "/es_ES/careers/SearchJobs?jobRecordsPerPage=6&jobOffset={off}"

# avature listing: enlaces a JobDetail
_RE_DETAIL_LINK = re.compile(r'href="(https://mercadona\.avature\.net/es_ES/Careers/JobDetail/[^"]+)"', re.I)
# fallback título dentro del mismo ancla
_RE_TITLE = re.compile(r'JobDetail/[^"]+"[^>]*>\s*(?:<[^>]+>\s*)*([^<]{4,120}?)\s*</a>', re.S)


def _listing(pages: int = 20) -> dict[str, str]:
    """{url: title_hint}. Paginación offset 6 cada página (6 ofertas/página)."""
    out: dict[str, str] = {}
    fails = 0
    # ponytail: Mercadona 200+ ofertas → 35 páginas *6 =210, techo 20*6=120 para no abusar
    for page in range(pages):
        off = page * 6
        url = LIST.format(off=off)
        try:
            html = hc.get(url, source=NAME).text
        except Exception:
            fails += 1
            if fails >= 2:
                break
            continue
        links = _RE_DETAIL_LINK.findall(html)
        if not links:
            fails += 1
            if fails >= 2:
                break
            continue
        # dedupe y título hint
        for link in links:
            if link in out:
                continue
            # título hint del ancla
            # busca el texto del ancla de ese link
            # local search window
            # simple: busca patrón link + > ... </a>
            m = re.search(re.escape(link) + r'"[^>]*>(.*?)</a>', html, re.S | re.I)
            title_hint = ""
            if m:
                title_hint = hc.strip_tags(m.group(1)).strip()
                if title_hint.lower() == "ver detalles":
                    title_hint = ""
            # si no hay título útil, usa slug
            if not title_hint:
                try:
                    slug = link.split("/")[-2]
                    title_hint = slug.replace("-", " ").strip()
                except Exception:
                    title_hint = ""
            # ponytail: filtra Portugal en listado para ahorrar detail budget (Loja = tienda PT)
            if "loja" in title_hint.lower() or "loja" in link.lower():
                continue
            out[link] = title_hint
        # si no hubo nuevas, cuenta como fallo parcial
        if len(links) == 0:
            fails += 1
            if fails >= 2:
                break
        else:
            fails = 0
        # early stop si página vacía distinta? Avature devuelve siempre 6, seguimos hasta pages
    return out


def _detail(url: str) -> dict:
    """Extrae título, provincia, salario mensual, texto."""
    html = hc.get(url, source=NAME).text
    # fallback title/province via avature fields custom--banner-title (primeros dos)
    # HTML: <div class="article__content__view__field custom--banner-title"><div class="...value"> Title </div>
    vals = re.findall(r'custom--banner-title[^>]*>.*?article__content__view__field__value[^>]*>\s*([^<]+?)\s*</div>', html, re.S)
    title = vals[0].strip() if len(vals) >= 1 else ""
    province = vals[1].strip() if len(vals) >= 2 else ""
    # si título genérico "Mercadona" o vacío, usa slug
    if not title or title.lower() == "mercadona":
        try:
            slug = url.split("/")[-2]
            title = slug.replace("-", " ").strip().title()
        except Exception:
            title = ""
    # city = province or primera municipalidad
    city = province
    # municipalidades: valor de icon-location
    m_muni = re.search(r'Municipios con vacante disponibles.*?article__content__view__field__value[^>]*>\s*([^<]+?)\s*</div>', html, re.S)
    if m_muni:
        munis = m_muni.group(1).strip()
        first_muni = munis.split(",")[0].strip().title()[:40]
        if first_muni and len(first_muni) > 2:
            # prefer first muni as city if province is genérica
            if not city or len(city) < 3:
                city = first_muni
        # si city es provincia amplia, keep province, but also keep city as muni for granularity
        # dejamos city como muni si province es larga? Mejor city = first_muni si existe
        # Para evitar perder provincia, province queda como province, city como muni
        if first_muni:
            city = first_muni
    # salario: busca Retribución mensual ... X€ a Y€ (avature tiene 40h,20h,15h)
    text = hc.strip_tags(html)
    # salary via parse_salary on whole text (fallback handle mensual)
    # Pero Mercadona lista 3 rangos; cogemos el primero (40h) que suele ser el mayor y más representativo
    # Estrategia: busca todos los rangos "X.XXX€ a Y.YYY€" y coge el primero con mensual cerca
    # Usamos parse_salary que ya prioriza mensual si encuentra mensual cerca
    hourly, salary_text = parse_salary(text)
    # Si no encontró, busca manualmente el primer rango mensual
    if not hourly:
        m = re.search(r'(\d{1,3}(?:\.\d{3})+)\s*€\s*a\s*(\d{1,3}(?:\.\d{3})+)\s*€', text)
        if m:
            # context 200 chars before for "mensual"
            ctx = text[max(0, m.start()-200): m.end()+200]
            if "mensual" in ctx.lower() or "Retribución" in ctx:
                from ..normalize import _num
                lo = _num(m.group(1))
                hi = _num(m.group(2))
                hourly = ((lo+hi)/2)/175
                salary_text = m.group(0).strip()
    sector = sector_of(title, text)
    housing, food = classify_text(text)
    return {"title": title, "province": province.title()[:40], "city": city.title()[:40],
            "hourly": hourly, "salary_text": salary_text, "text": text, "sector": sector,
            "housing": housing, "food": food}


@register("mercadona")
def run(con, *, pages: int = 25, detail_budget: int = 150, budget: int | None = None, opts: dict | None = None, **_) -> tuple[list[Job], dict]:
    if budget is not None:
        detail_budget = budget
    opts = opts or {}
    info = report.new_info()
    if opts.get("no_detail"):
        detail_budget = 0
    # ponytail: cli default 12 deja Mercadona incompleto (ES filtrado); si corrida completa, usa 25
    effective_pages = pages or 25
    if effective_pages == 12 and not opts.get("limit"):
        effective_pages = 25
    pages = effective_pages
    # listing
    try:
        listing = _listing(pages)
    except Exception:
        info["http_errors"] += 1
        return [], info
    info["listed"] = len(listing)
    if not listing:
        report.add_warning(info, "zero_cards")
        return [], info
    # stubs
    jobs: list[Job] = []
    for url, title_hint in listing.items():
        # title_hint may be empty, detail will refine
        jobs.append(Job(source=NAME, url=url, title=title_hint, company="Mercadona",
                        city="", province="", sector=sector_of(title_hint), direct=True))
    from ..db import known_ids
    seen = known_ids(con, {j.id for j in jobs})
    fresh = [j for j in jobs if j.id not in seen]
    info["new"] = len(fresh)
    # detail for fresh only (ahorra 50% requests)
    fetched = 0
    kept = 0
    to_fetch = fresh[:detail_budget]
    for j in to_fetch:
        if opts.get("no_detail"):
            break
        try:
            d = _detail(j.url)
        except Exception:
            info["http_errors"] += 1
            continue
        fetched += 1
        info["detail_fetched"] += 1
        # filtro España: descarta Portugal (texto portugués)
        txt = d["text"]
        if "Remuneração" in txt and "Retribución" not in txt:
            # Portugal — skip (no cuenta como kept)
            continue
        # si province vacío y city portugués, skip?
        # También filtra si province/city es distrito portugués conocido
        port_cities = {"faro","setúbal","setubal","aveiro","coimbra","lisboa","porto","braga","leiria","viseu","beja","évora","evora","guarda","portalegre","santarém","santarem","viana","vila real","bragança","braganca","castelo branco"}
        if d["city"].lower() in port_cities or d["province"].lower() in port_cities:
            continue
        j.title = d["title"] or j.title
        j.city = d["city"] or j.city
        j.province = d["province"] or j.province or j.city
        j.hourly = d["hourly"]
        j.salary_text = d["salary_text"] or ""
        j.sector = d["sector"] or j.sector
        j.housing, j.food = d["housing"], d["food"]
        j.text = txt[:1500]
        kept += 1
    # output: solo los que pasaron filtro Portugal + ya conocidos
    # Para los ya conocidos (seen), los mantenemos sin detail (ya en DB)
    # Pero para los fresh que filtramos por Portugal, no los devolvemos (evita meter Portugal en DB)
    # Así que out = seen jobs + kept fresh
    out_ids_kept = {j.id for j in to_fetch if j.hourly is not None or j.title}
    # Actually we need to filter the jobs list to exclude Portuguese fresh that we skipped
    # Determine which fresh were skipped: those where we continued without kept increment
    # Simplify: rebuild out as seen + those fresh where we did kept processing
    # For fresh that we skipped (Portugal), they won't be in kept, we exclude
    # So:
    fresh_kept_ids = set()
    # We tracked kept increment only when not skipped, but need ids
    # Instead, re-derive: after loop, collect ids of jobs that have hourly or title and not skipped?
    # Simpler: return only jobs where not Portuguese fresh skipped
    # We already mutated j for kept ones, but skipped ones still have empty city/title? We can filter:
    filtered = []
    for job in jobs:
        if job.id in seen:
            filtered.append(job)
        else:
            # fresh
            # if job was fetched and kept, it will have city set (we set) or hourly
            # if it was Portuguese skipped, it will have hourly None and not updated? Actually we continued before update, so job remains with title_hint and empty city
            # So we can include only if job.city (updated) not empty or hourly
            if job.city or job.hourly:
                # but need to ensure we didn't keep Portuguese where city is Portuguese - we already continued, so those remain empty
                filtered.append(job)
            else:
                # This fresh was either not fetched due to budget or was Portugal skipped with remaining empty
                # If not fetched due to budget limit (fresh beyond detail_budget), we still want to keep stub? For Mercadona we require detail for salary explicit, so without detail no hourly -> skip like iman
                # So skip those without hourly
                pass
    # For compatibility with report, info["listed"] already set, return filtered
    return filtered, info
