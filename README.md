# jobs-es

Scraper de ofertas reales de empleo en España — hostelería con alojamiento, logística con €/h explícito, comercio estable. Los adaptadores que requieren credenciales propias degradan con un motivo declarado en vez de fallar; el bypass de apps móviles está rechazado por coste/beneficio (ver Decisiones). Salida: un HTML autónomo filtrable offline (`jobs_es.html`) + SQLite (`data/jobs.db`).

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Tests](https://github.com/MgnumX/jobs-es/actions/workflows/tests.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue)

## Ejecutar

```bash
uv sync --locked
uv run jobs-es --only turijobs,melia --pages 12 --budget 200
uv run pytest -v   # sin red: guardarraíles de salario + parsers con fixture
```

## Fuentes (16 activas + 1 desactivada)

| Fuente | Método |
|---|---|
| turijobs | listado SSR (hostelería/temporada) |
| jobandtalent | API `job_opportunities` (€/h nativo) |
| amazon.jobs | API `search.json` con paginación |
| barceló | Workday CXS (`POST /wday/cxs/`) |
| meliá | SuccessFactors SSR (`&startrow`) |
| palladium | iCIMS SSR (`/search-jobs`) |
| riu | feed JSON (Teamtailor) |
| correos, día, lidl, mercadona, fuerte, imán, jobeka, randstad | adaptadores SSR/API por fuente |
| infojobs | API pública oficial (`api.infojobs.net`, HTTP Basic con credenciales propias). Sin credenciales el adaptador se declara inerte: `sin credenciales INFOJOBS_CLIENT_ID/SECRET` |

Cada fuente es un módulo independiente en `src/jobs_es/sources/` con la misma interfaz (`SOURCES[name]`). Añadir una fuente = 1 archivo.

## Decisiones documentadas (con fecha y coste)

- **InfoJobs: API oficial sí, bypass de la app no (2026-08-25):** el adaptador usa la API pública oficial con credenciales propias y degrada con motivo declarado si faltan. Lo que está excluido es el bypass del cliente móvil (ingeniería inversa + proxies residenciales ≈ 30–50 €/mes y 6–8 h): domina el volumen pero prolifera la oferta fantasma. NO reevaluar sin presupuesto o necesidad de cobertura nueva.
- **JobToday descartado (2026-08-26):** el detalle de cada oferta devuelve 403 (fuerza la app) y sus salarios/hora vienen inflados en origen (80 €/h "ayudante").
- **Adecco desactivado:** endpoint muerto tras rediseño; módulo conservado como `_adecco_disabled.py` hasta capturar el endpoint nuevo.

Ver `README-canales.md`, `SPEC.md` y `ARCHITECTURE_FOR_REVIEW.md`.

## Casos límite que el parser ya cubre

Los tests cubren guardarraíles de salario y parsers con fixture (`turijobs`, `meliá`); el resto de los adaptadores se verifica por ejecución, no por tests unitarios.

`tests/test_salary_guards.py` — regresiones reales que antes rompían el ranking de €/h:

- `"12,90€/h (SBA: 22.700€ / 2.070€ brutos/mes)"` → **12,9**, no 70,8
- `"2.092,80 €/mes. 13,08 €/hora"` → **13,08**, no 52,9
- `"Horario: … Plus: 75 € por servicio"` → **None** (no es salario)
- `"6.000€ brutos/mes más comisiones"` → **None** (supera el máximo verosímil)

## Estructura

```
src/jobs_es/
  cli.py          # --only/--pages/--budget
  models.py       # Job dataclass, id=sha1(source|url)[:16]
  db.py           # SQLite upsert por id
  normalize.py    # parse_salary, clasificación, tiers por ciudad
  httpclient.py   # httpx con pausa entre peticiones
  html.py         # construye el HTML filtrable offline
  sources/        # un adaptador por fuente
```

## Automatización

`.github/workflows/scrape.yml` — ejecución **manual** (`workflow_dispatch`): corre el scraper y commitea el HTML regenerado. Sin cron: el historial queda limpio.
