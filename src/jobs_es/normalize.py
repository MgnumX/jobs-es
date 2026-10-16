"""Normalización: salario a €/h, clasificadores housing/food, ETTs, coste por ciudad."""
import re

_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "ref", "fb_")

def canonical_url(url: str) -> str:
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
    url = (url or "").strip()
    parts = urlsplit(url)
    host = parts.netloc.lower()
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.lower().startswith(_TRACKING_PREFIXES)]
    query.sort()
    return urlunsplit(("https", host, path, urlencode(query), ""))

# --- Salario -------------------------------------------------------------

_NUM = r"(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d{1,3}(?:\.\d{3})*[.,]\d{1,2}|\d{1,6})"
_PAT_H = re.compile(_NUM + r"\s*(?:EUR|€)?\s*(?:brutos?\s*)?(?:por\s*hora|/hora|/\s*h\b)", re.I)
_PAT_M = re.compile(_NUM + r"\s*(?:EUR|€)\s*(?:brutos?\s*)?(?:(?:/|al\s*|por\s*|al)\s*)?(?:mes|mensual(?:es)?)", re.I)
_PAT_A = re.compile(_NUM + r"\s*(?:EUR|€)\s*(?:brut[oa]s?\s*)?(?:/|al\s*|por\s*|año|ano\b|anual)", re.I)
# par estilo Bizneo: "25,000 € - 30,000 € Bruto/año"
_PAT_PAIR = re.compile(
    _NUM + r"\s*(?:EUR|€)[^€\n]{0,20}?" + _NUM +
    r"\s*(?:EUR|€)?\s*(?:brut[oa]s?\s*/?\s*)?(hora|semana|mes|mensual|año|ano|anual)", re.I)
_RANGE = re.compile(_NUM + r"\s*(?:[-–a]|y)\s*" + _NUM + r"\s*(?:EUR|€)", re.I)

_UNIT_HOURS = {"hora": 1, "h": 1, "semana": 40, "mes": 175, "mensual": 175,
               "año": 12 * 175, "ano": 12 * 175, "anual": 12 * 175}

# Techo €/h real de hostelería/logística/comercio en ES (bruto). Un cargo con
# 25+ €/h es siempre un parse fallido (bono, mezcla anual/mensual, comisión).
MAX_HOURLY = 25.0

# Palabras que delatan que el número € NO es salario sino complemento/bonificación
_PRICE_KILL = re.compile(
    r"plus\b|bono\b|bonus\b|dieta\b|incentivo\b|complemento\b|prorrata\b"
    r"|gratificaci[oó]n|compensaci[oó]n|indemnizaci[oó]n|comisi[oó]n\b|variable\b",
    re.I)


def period_hourly(amount, period: str) -> float | None:
    """Convierte importe+periodo a €/h. Si el periodo no es reconocible, None
    (no adivinar: un 'year' tratado como hora explota el ranking)."""
    p = (period or "").lower()
    hours = 1 if "hour" in p else 175 if "month" in p or "wage" in p \
        else 2100 if "year" in p else 40 if "week" in p else None
    if not hours:
        return None
    try:
        v = float(amount) / hours
    except (TypeError, ValueError):
        return None
    return v if 4.5 <= v <= MAX_HOURLY else None


def _num(s: str, *, dot_decimal: bool = False) -> float:
    """España: punto=miles, coma=decimales. En €/h el punto suele ser decimal.
    Estilo inglés '25,000' = miles con coma."""
    s = s.strip()
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?", s):
        return float(s.replace(",", ""))
    if "," in s:
        return float(s.replace(".", "").replace(",", "."))
    if dot_decimal or s.count(".") == 1 and len(s.split(".")[1]) <= 2:
        return float(s)
    return float(s.replace(".", ""))


def parse_salary(text: str) -> tuple[float | None, str]:
    """Devuelve (€/h o None, texto original del match). Mes=175h, año=12 meses."""
    pm = _PAT_PAIR.search(text[:4000])
    if pm:
        hours = _UNIT_HOURS.get(pm.group(3).lower(), 175)
        lo, hi = _num(pm.group(1)), _num(pm.group(2))
        # mezcla de periodos ("22.700€ anual / 2.070€ mes", "2.092€ mes. 13,08 h"):
        # ratio >3 delata dos unidades distintas → cae a los patrones de una unidad
        if lo > 0 and hi > 0 and max(lo, hi) / min(lo, hi) <= 3.0:
            v = (lo if lo == hi else (lo + hi) / 2) / hours
            if 4.5 <= v <= MAX_HOURLY:
                return v, pm.group(0).strip()
    for pat, hours in ((_PAT_H, 1), (_PAT_M, 175), (_PAT_A, 12 * 175)):
        m = pat.search(text)
        if m:
            v = _num(m.group(1), dot_decimal=(hours == 1)) / hours
            if v < 4.5 or v > MAX_HOURLY:
                return None, ""
            # un rango "X-Y €" con unidad de mes/año: usa mediana
            rm = _RANGE.search(text[max(0, m.start() - 12):m.end()])
            if rm:
                lo, hi = _num(rm.group(1), dot_decimal=(hours == 1)), _num(rm.group(2), dot_decimal=(hours == 1))
                if hi > lo:
                    v2 = ((lo + hi) / 2) / hours
                    if 4.5 <= v2 <= MAX_HOURLY:
                        v = v2
            return v, m.group(0).strip()
    # Fallback: rango X€ a/hasta Y€ con unidad cerca (±120 chars) — Mercadona/Lidl
    m = re.search(_NUM + r"\s*€\s*(?:a|hasta|[-–])\s*" + _NUM + r"\s*€", text[:6000], re.I)
    if m:
        ctx = text[max(0, m.start() - 120): m.end() + 120].lower()
        hours = None
        if "mensual" in ctx or " al mes" in ctx or "/mes" in ctx:
            hours = 175
        elif "anual" in ctx or "año" in ctx or "ano" in ctx:
            hours = 2100
        elif "hora" in ctx:
            hours = 1
        elif "semana" in ctx:
            hours = 40
        if hours:
            lo, hi = _num(m.group(1)), _num(m.group(2))
            v = ((lo + hi) / 2) / hours if hi != lo else lo / hours
            if 4.5 <= v <= MAX_HOURLY:
                return v, m.group(0).strip()
    # Fallback single: "Retribución mensual ... 1.734€" — unit antes del valor
    for m2 in re.finditer(_NUM + r"\s*€", text[:6000]):
        pre = text[max(0, m2.start() - 60): m2.start()]
        if _PRICE_KILL.search(pre):  # "Plus: 75 €" no es salario
            continue
        ctx = text[max(0, m2.start() - 140): m2.end() + 40].lower()
        hours = None
        if "mensual" in ctx or " al mes" in ctx or "/mes" in ctx:
            hours = 175
        elif "anual" in ctx or "año" in ctx or "ano" in ctx:
            hours = 2100
        elif "hora" in ctx:
            hours = 1
        elif "semana" in ctx:
            hours = 40
        if hours:
            v = _num(m2.group(1)) / hours
            if 4.5 <= v <= MAX_HOURLY:
                return v, m2.group(0).strip()
    return None, ""


# --- Alojamiento / comida ------------------------------------------------

_KW_HOUSING = re.compile(
    r"(alojamiento|vivienda|habitaci[oó]n(?:\s+(?:doble|individual))?|housing|internos?\b|pensión completa)",
    re.I)
_INC = re.compile(
    r"(incluid\w*|gratuit\w*|gratis|ofrec\w*|disponibl\w*|facilitad\w*|corresponde\w*|a\s+cargo\s+de\s+la\s+empresa|provided|free)",
    re.I)
_KW_FOOD = re.compile(
    r"(comidas?\s+incluidas?|manutenci[oó]n|media\s+pensi[oó]n|pensión completa|board\s+included|almuerzo\s+incluido)",
    re.I)


def classify_text(text: str) -> tuple[bool, bool]:
    """(housing, food). Housing exige palabra de inclusión en ±130 chars."""
    t = text[:8000]
    food = bool(_KW_FOOD.search(t))
    housing = False
    for m in _KW_HOUSING.finditer(t):
        window = t[max(0, m.start() - 100):m.end() + 130]
        if _INC.search(window):
            housing = True
            break
    return housing, food


# --- Exclusión (sin título ni experiencia) y urgencia --------------------

# ponytail: exclusión por título; un hipotético "auxiliar técnico" se pierde (<1%)
_EXCLUDE = re.compile(
    r"pr[áa]cticas|internship|\bintern\b|trainee|becari|\bbeca\b"
    r"|t[eé]cnic|oficial de|\boficial\b|ingenier|\bsstt\b|frigorista|gestor"
    r"|\bmanager\b|\blead\b|senior|\bsr\.|supervisor|responsable|jefe|director"
    r"|gerente|coordinador|encargad"
    # comisionistas que inflan el ranking de €/h
    r"|inmobiliari|captador|aut[oó]nom|\bfreelance\b", re.I)

_URGENT = re.compile(
    r"incorporaci[oó]n\s+(?:inmediata|urgente)|contrataci[oó]n\s+inmediata"
    r"|\burgente\b|immediate\s+start|alta\s+inmediata", re.I)


def is_excluded(title: str) -> bool:
    return bool(_EXCLUDE.search(title))


# piden FP/titulación/experiencia en la DESCRIPCIÓN (no visible en el título)
# ponytail: factcheck Lidl/Mercadona 2026-08-31 pillaba técnico con "titulación requerida" y "CFGS"
_EXCLUDE_TXT = re.compile(
    r"\bfp\b(?:\s+(?:de\s+)?grado)?|formaci[oó]n\s+(?:profesional|universitaria)|ciclo formativo|cfgs|cfcm|m[oó]dulo\s+profesional"
    r"|grado\s+(?:medio|superior)\b|titulaci[oó]n\s+(?:requerida|universitaria|de\s+grado)|titulaci[oó]n\s+requerida"
    r"|grado\s+en\s+[a-záéíóú]+(?:\s+[a-záéíóú]+){0,2}|carrera\s+universitaria|licenciatura|diplomatura|m[aá]ster"
    r"|ingenier[íi]a|arquitectura|t[eé]cnico(?:\s+de\s+instalaciones|\s+frigorista)?|estudios\s+como\s+t[eé]cnico"
    r"|[ei]ngres?ar\s+a\s+la\s+universidad"
    r"|experiencia\s+m[ií]nima\s+de\s+\d+\s+a[ñn]o|\d+\s+a[ñn]os\s+de\s+experiencia|experiencia\s+previa\s+(?:en\s+puesto\s+similar\s+de\s+)?\d+\s+a[ñn]os", re.I)


def is_excluded_text(text: str) -> bool:
    """True si la descripción exige título (FP/grado/universidad) o años de
    experiencia. 'No es necesaria experiencia previa' NO matchea ✓"""
    return bool(_EXCLUDE_TXT.search(text[:4000]))


def is_urgent(title: str, text: str = "") -> bool:
    return bool(_URGENT.search(f"{title} {text[:2500]}"))


# --- Sector y ETTs -------------------------------------------------------

_SECTORS = [
    ("logistica", r"(almac[eé]n|mozo|carretiller|log[ií]stic|repartid|conductor|paletiz|picking|packing|mercanc[ií]a|ch[oó]fer)"),
    ("hosteleria", r"(camarer|cocin|cocina|gobernanta|gobernante|pisos|maitre|maître|bartender|barra|recepcionista|mucama|steward|f&b|desayunos?|hotel|resort|restaurante|pastel|bufet|fregador|banquet|recepci[óo]n|reservas|marmit|commis|barista|lavavajill|office\b|jefe/a de sector|sala\b)"),
    ("comercio", r"(dependient|reponedor|cajer|tienda|supermercado)"),
    ("temporada", r"(temporada|verano|invierno|camping|socorrista|animaci[oó]n|esqu[ií])"),
]

_ETTS = ("adecco", "randstad", "eurofirms", "manpower", "synergie",
         "grupo iman", "imán temporing", "alta gestión", "alta gestion",
         "nortempo", "temporing", "start people")


def sector_of(title: str, text: str = "") -> str:
    blob = f"{title} {text[:600]}".lower()
    for name, pat in _SECTORS:
        if re.search(pat, blob):
            return name
    return "otros"


def is_ett(company: str) -> bool:
    c = company.lower()
    return any(k in c for k in _ETTS)


# --- Clústeres de títulos (para medianas) + convenio fallback ---------------

# ponytail: ~25 roles normalizados; añadir otro solo si una oferta limpia cae en None
_CLUSTERS = [
    ("pisos",      r"gobernant|camarer.*pisos|pisos|limpiador"),
    ("camarero",   r"camarer|barman|bartender|barista|hostess"),
    ("ayudante_cocina", r"ayudante de cocina|marmit|commis"),
    ("cocinero",   r"cociner.*l[ií]nea|cociner(?!.*ayudante)|ayudante de.*partida"),
    ("lavaplatos", r"fregador|office\b|steward|lavavajill|plonge"),
    ("mozo_almacen", r"mozo.*almac[eé]n|auxiliar.*almac[eé]n|reponedor"),
    ("carretillero", r"carretiller"),
    ("recepcionista", r"recepcionista|ayudante de recepci[oó]n"),
    ("botones",    r"botones|maletero|valet|bellboy"),
    ("dependiente",r"dependient|cajero|tienda|supermercado"),
    ("repartidor", r"repartidor|conductor|ch[oó]fer\b|chofer"),
    ("mantenimiento", r"auxiliar de mantenimiento|oficial de mantenimiento"),
]

# ponytail: tablas enero 2026, revisar cada año con convenios provinciales publicados
# (€/h bruto, tier cara ≥450, media 320-449, barata <320 de CITY_RENT)
CONVENIO_EST = {
    ("pisos", "cara"):      10.6, ("pisos", "media"): 9.8, ("pisos", "barata"): 9.2,
    ("camarero", "cara"):   11.0, ("camarero", "media"): 10.0, ("camarero", "barata"): 9.5,
    ("ayudante_cocina", "cara"): 10.2, ("ayudante_cocina", "media"): 9.6, ("ayudante_cocina", "barata"): 9.2,
    ("cocinero", "cara"):   11.5, ("cocinero", "media"): 10.6, ("cocinero", "barata"): 10.0,
    ("lavaplatos", "cara"): 10.0, ("lavaplatos", "media"): 9.5, ("lavaplatos", "barata"): 9.1,
    ("mozo_almacen", "cara"): 11.8, ("mozo_almacen", "media"): 10.8, ("mozo_almacen", "barata"): 10.3,
    ("carretillero", "cara"):12.2, ("carretillero", "media"):11.2, ("carretillero", "barata"):10.7,
    ("recepcionista","cara"):11.2, ("recepcionista","media"):10.4, ("recepcionista","barata"):9.8,
    ("dependiente","cara"): 10.2, ("dependiente","media"):9.6,  ("dependiente","barata"):9.2,
    ("repartidor","cara"):  11.4, ("repartidor","media"):10.6,  ("repartidor","barata"):10.0,
    # fallback sector+nivel cuando el título no clusteriza
    ("hosteleria","cara"): 10.4, ("hosteleria","media"):9.8, ("hosteleria","barata"):9.3,
    ("logistica","cara"): 11.6, ("logistica","media"):10.7, ("logistica","barata"):10.2,
    ("comercio","cara"): 10.2,  ("comercio","media"):9.6,   ("comercio","barata"):9.2,
    ("temporada","cara"):10.4,  ("temporada","media"):9.8,  ("temporada","barata"):9.3,
    ("otros","cara"):10.0,      ("otros","media"):9.5,      ("otros","barata"):9.0,
}


def tier_of(city: str) -> str:
    r = rent_of(city)
    return "cara" if r >= 450 else "media" if r >= 320 else "barata"


def title_cluster(title: str) -> str | None:
    """Rol canónico normalizado (sin acentos/minúsculas) para medianas."""
    blob = "".join(
        c for c in title.lower().replace("á","a").replace("é","e")
        .replace("í","i").replace("ó","o").replace("ú","u") if c
    )
    for name, pat in _CLUSTERS:
        if re.search(pat, blob):
            return name
    return None


# --- Coste vivienda por ciudad (habitación €/mes aprox. — EDITAR A GUSTO) --

CITY_RENT = {
    "madrid": 550, "barcelona": 500, "palma": 520, "ibiza": 700,
    "las palmas": 400, "tenerife": 380, "santa cruz de tenerife": 380,
    "valencia": 420, "sevilla": 330, "malaga": 430, "málaga": 430,
    "murcia": 280, "zaragoza": 320, "bilbao": 460, "a coruña": 300,
    "coruna": 300, "la coruña": 300, "valladolid": 280, "alicante": 350,
    "guadalajara": 320, "toledo": 310, "girona": 400, "gerona": 400,
    "cadiz": 300, "cádiz": 300, "santander": 340, "oviedo": 290,
    "pamplona": 350, "logrono": 300, "logroño": 300, "huesca": 280,
    "lleida": 300, "lérida": 300, "tarragona": 330, "castellon": 280,
    "castellón": 280, "almeria": 290, "almería": 290, "huelva": 270,
    "badajoz": 250, "caceres": 250, "cáceres": 250, "salamanca": 300,
    "burgos": 300, "leon": 280, "león": 280, "vitoria": 380,
    "san sebastian": 500, "san sebastián": 500, "menorca": 450,
    "mahon": 450, "maó": 450, "eivissa": 700,
}
DEFAULT_RENT = 350


def rent_of(city: str) -> int:
    c = (city or "").lower().strip()
    for k, v in CITY_RENT.items():
        if k in c or c in k:
            return v
    return DEFAULT_RENT


def quality(hourly: float, city: str) -> float:
    """Ratio €/h trabajado ÷ €/h de habitación. >3 = buena calidad-precio."""
    rent_hourly = rent_of(city) / 175
    return round(hourly / rent_hourly, 2)


def build_salary_buckets(rows: list[dict]):
    from collections import defaultdict
    from statistics import median
    buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in rows:
        hourly = r.get("hourly")
        if not hourly:
            continue
        cluster = r.get("title_cluster") or title_cluster(r.get("title") or "") or r.get("sector") or ""
        city = r.get("city") or ""
        tier = tier_of(city)
        buckets[(cluster, tier)].append(float(hourly))
    return {k: median(v) for k, v in buckets.items() if len(v) >= 3}


def estimate_hourly(r: dict, buckets: dict):
    cluster = r.get("title_cluster") or title_cluster(r.get("title") or "") or r.get("sector") or ""
    city = r.get("city") or ""
    tier = tier_of(city)
    key = (cluster, tier)
    if key in buckets:
        return buckets[key], "median", 0.75
    sector = r.get("sector")
    convenio = CONVENIO_EST.get((sector, tier))
    if convenio:
        return convenio, "convenio", 0.55
    return None, None, 0.0


def eff_score(r: dict, buckets: dict):
    hourly = r.get("hourly")
    if hourly:
        eff = float(hourly)
        est_src, est_conf, hourly_est = "explicit", 1.0, None
    else:
        eff, est_src, est_conf = estimate_hourly(r, buckets)
        hourly_est = eff
        if not eff:
            return {"hourly_est": None, "eff_hourly": None, "est_src": None, "est_conf": 0.0, "score": None, "hours_to_rent": None}
    city = r.get("city") or ""
    rent = rent_of(city)
    score = None
    hours_to_rent = None
    if eff and rent:
        base = eff / (rent / 175)
        # confidence weighting
        conf = est_conf if not hourly else 1.0
        # ponytail: housing/food/direct bonuses are applied in html, not here for DB score simplicity
        score = round(base * conf, 2)
        hours_to_rent = round(rent / eff, 1)
    return {"hourly_est": hourly_est, "eff_hourly": eff, "est_src": est_src, "est_conf": est_conf, "score": score, "hours_to_rent": hours_to_rent}
