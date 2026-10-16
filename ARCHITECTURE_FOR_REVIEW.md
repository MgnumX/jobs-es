# ARCHITECTURE — jobs-es (para juicio externo)

**Objetivo:** scraper ofertas reales España (hostelería con alojamiento, logística €/h, comercio estable, sin InfoJobs). Output `jobs_es.html` filtrable offline. 1133 ofertas vivas.

## File tree (sin .venv/__pycache__)
```
jobs-es/
├── pyproject.toml          # httpx>=0.27 only, hatchling, jobs-es=cli:main
├── SPEC.md / README-canales.md / bonos_lmd*.md / decision_ccaa_jobandtalent.md
├── data/jobs.db            # 1133 rows, 19 cols, 580K
├── jobs_es.html            # 575K standalone #0B1F14
├── .github/workflows/scrape.yml # cron 17 */6, setup-uv, commit html
└── src/jobs_es/
    ├── __init__.py         # SOURCES={} + register(name)
    ├── models.py           # Job dataclass, id=sha1(source|url)[:16]
    ├── db.py               # sqlite upsert/known_ids
    ├── normalize.py        # parse_salary, classify_text, tier/CITY_RENT
    ├── httpclient.py       # httpx.Client UA 0.45s pause
    ├── cli.py              # arg `--only/--pages 12/--budget 200`
    ├── html.py             # build() median+convenio → JOBS json
    └── sources/__init__.py # 9 activos
        ├── amazon.py       # API search.json
        ├── barcelo.py      # Workday CXS POST
        ├── fuerte.py       # Bizneo SSR
        ├── iman.py         # Bizneo ETT solo pago explícito
        ├── jobandtalent.py # API job_opportunities
        ├── melia.py        # SuccessFactors SSR
        ├── palladium.py    # iCIMS SSR
        ├── riu.py          # Teamtailor jobs.json
        ├── turijobs.py     # SSR paginado
        └── _adecco_disabled.py # Phenom+Sitemap DESACTIVADO
```

## Data flow (5 pasos)
`cli.main() -> SOURCES[name](con,pages,budget) -> _listing() paginado -> known_ids -> detail fresh[:budget] via httpclient.get/strip_tags -> classify_text/parse_salary -> is_excluded/is_excluded_text -> upsert(row) -> all_rows -> html.build(median+convenio) -> jobs_es.html`

## Core — conciso con código clave

**models.py** `Job(source,url,title,company,city,province,sector,salary_text,hourly,housing,food,direct,urgent,posted_at,text)` `id=sha1(source|url)[:16]` `row()=asdict-text+id` `to_json()` trims.

**db.py** `DB_PATH=repo/data/jobs.db` `_COLS 19` `jobs(id PK,url UNIQUE,idx sector)` `connect()->executescript+ADD COLUMN urgent/hourly_est/est_src` `upsert(): SELECT id; INSERT first_seen=last_seen=now else merge truthy&&old empty; last_seen=now` `known_ids(ids): chunk 500 IN` `all_rows: ORDER first_seen DESC`

**httpclient.py**
```py
_client=httpx.Client(UA="jobs-es-scraper/0.1", Timeout 25s, follow)
PAUSE=0.45; _last=[0.0]
get(url, retries=1, params, headers): sleep PAUSE, _client.get, 200 else retry -> RuntimeError
post_json(url,payload): same PAUSE, _client.post(json=payload)
strip_tags: re <script|style>.*?</>, <[^>]+>->\n, &nbsp;->space
```

**normalize.py** `_NUM` miles es/coma, `_PAT_H|M|A|PAIR|RANGE`, `_UNIT_HOURS hora:1 semana:40 mes:175 año:2100` `_num(dot_decimal)` `_INC` ventana ±130 `classify_text(t[:8000])` `is_excluded(title)` prácticas/técnic/oficial/ingenier/sstt/manager/lead/senior/supervisor/jefe/director/gerente/encargad/inmobiliari `is_excluded_text(text[:4000])` fp|grado medio/superior|titulación|diplomatura|años experiencia `is_urgent` `sector_of` 4 regex `is_ett` 11 nombres `CITY_RENT 43` `rent_of` substring `tier_of cara>=450 media>=320` `quality=round(hourly/(rent/175),2)` `title_cluster` 12 regex `CONVENIO_EST 42` (9 roles×3 tiers +5 sectores×3)

**html.py** `OUT=repo/jobs_es.html` `_CSS dark` `_JS filter q/sec/prov/hous/food/direct/urgent/fresh≤72h sort score|hourly|new` `build(rows): buckets[(cluster|sector,tier)]=median(hourly) ; _est(r): median→convenio sector→None ; eff=hourly or est ; score=quality(eff,city) ; jobs json hourly/est/eff/explicit/score/seen/posted ; write <!DOCTYPE>+style+body` `esc &<>\"` `</`→`<\/`

**cli.py** `argparse --only --pages 12 --budget 200 --build-only` `connect(); for name in SOURCES: jobs,info=SOURCES[name](con,..) -> kept=[not is_excluded and not is_excluded_text] -> urgent=is_urgent -> upsert -> print [ok] info → N nuevas (M descartadas) ; build(all_rows)`

## Sources — 9 activos (1 desactivado)

| File | ATS | URL | Pag | Detail |
|---|---|---|---|---|
| `amazon.py` | search.json | `GET search.json?country=ESP&offset` limit100 | hits→ceil/100 techo1000 | no |
| `jobandtalent.py` | API job_opportunities | `GET /job_opportunities?country_code=ES&provinces[]=X&page` + `X-Organization` | 25 prov×8 + meta.totalPages | no, payRate directo |
| `riu.py` | Teamtailor feed | `GET jobs.json` | 1 | no |
| `barcelo.py` | Workday CXS | `POST /wday/cxs/barcelo/Barcelo_Careers/jobs limit20 offset` | total→min(total,600) | **no** (ponytail sin detalle 0/363) |
| `melia.py` | SuccessFactors SSR | `GET /search/?locationsearch=españa&startrow=N*25` | 10×25 anchor `/job/` | fresh≤250 retry <3000 |
| `palladium.py` | iCIMS SSR | `GET /search-jobs` single | anchor `/job/` | fresh≤200 |
| `turijobs.py` | custom SSR | `GET /es/ofertas-trabajo?page` split `rounded-lg shadow-` | 12 | fresh≤200 `_CARD` href/h3 |
| `fuerte.py` | Bizneo SSR | `GET /jobs?page` | 25 fails2× | fresh≤250 len>5000 3 tries city `¡Aplica ahora!+1` |
| `iman.py` | Bizneo SSR | `GET empleo.imancorp.es/jobs?page` | 25 | fresh≤250 **solo `parse_salary`!=None** explicit_ids |
| `_adecco_disabled.py` | Phenom+Sitemap | `api/apply/v2/jobs`+sitemap 12 subs | — | no importado |

## DB schema
```sql
CREATE TABLE jobs (id PK, source, title, company, city, province, sector, url UNIQUE, salary_text, hourly REAL, housing/food/direct/urgent INT, posted_at, first_seen, last_seen, hourly_est REAL, est_src TEXT);
CREATE INDEX idx_jobs_sector ON jobs(sector);
```

## Deps
`httpx>=0.27` only (pyproject). stdlib `re/sqlite3/json/pathlib/hashlib/dataclasses/datetime/statistics/time`. Build `hatchling`.

## Deudas ponytail / decisiones
- `selectolax` muerto en pyproject (deuda #1) — usar regex hoy.
- `barcelo` sin detalle: `ponytail: re-añadir si housing>5%`.
- `iman` solo explícito: `ponytail: sin €/h no entra`.
- `db hourly_est` nunca escrito por `upsert`, solo `html.build` vista.
- `CITY_RENT` scan lineal O(30), `PAUSE` global, `known_ids` chunk 500.

## Verificación
```bash
uv run jobs-es --build-only
python3 -c "import sqlite3;print(list(sqlite3.connect('data/jobs.db').execute('SELECT source,count(*) FROM jobs GROUP BY source')))"
```

