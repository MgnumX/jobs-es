# SPEC.md — jobs-es

Scraper de ofertas reales de empleo en España (sin InfoJobs/generalistas):
hostelería con alojamiento incluido, logística con buena €/h, comercio estable.
Output: un HTML autónomo filtrable offline (`jobs_es.html`).

## Fuentes

| Fuente | Qué aporta | Método |
|---|---|---|
| turijobs | hostelería/temporada, cadenas publican directo, a veces 🏠 | listado SSR |
| jobandtalent | logística sin experiencia, €/h nativo | API `job_opportunities` |
| amazon.jobs | logística directa, <1 semana | API `search.json` paginación `hits` |
| fuerte | Bizneo HR, 🏠 | SSR `jobs?page` |
| iman | ETT Bizneo, solo con pago explícito | SSR `empleo.imancorp.es/jobs` |
| riu | Teamtailor `jobs.json` | feed JSON filtrado ES |
| barcelo | Workday CXS 517 puestos | `POST /wday/cxs/` paginado |
| melia | SuccessFactors SSR | `&startrow` paginado |
| palladium | iCIMS SSR | `/search-jobs` |

> JobToday: descartado definitivo (2026-08-26) — detalle con WAF 403 y
> salarios/hora irreales en origen. Ver README-canales.md.
> Adecco: desactivado (`_adecco_disabled.py`) — endpoint muerto tras rediseño web.

## Criterios de aceptación

1. `uv run jobs-es` corre todas las fuentes; **una fuente caída no tira el resto**.
2. Primera corrida ≥150 ofertas reales persistidas en `data/jobs.db`.
3. Dedup estable: segunda corrida seguida reporta ~0 nuevas.
4. Cada oferta tiene: título, empresa, ciudad/provincia, URL, fuente, sector,
   €/h si existe (nunca inventado salvo estimación marcada), flags 🏠/🍽/directo.
5. `jobs_es.html` funciona abriéndolo con file:// sin red: filtros texto,
   sector, provincia, 🏠, 🍽, ⚡directo; orden por calidad-precio / €/h / fecha.
6. Score calidad-precio = €/h ÷ (alquiler habitación ciudad ÷ 175h). Tabla
   editable en `normalize.CITY_RENT`. >3 = buen chollo.

## Convenciones

- Salario: €/h directo; mensual÷175; anual÷12÷175; rango→mediana.
- `direct=True` = aplica al empleador final (Amazon, cadenas hoteleras), no a ETT.
- Amazon sin salario publicado → constante `AMAZON_HOURLY_EST` marcada "(est.)".
- Cortesía: 0,45s entre peticiones, UA identificable, presupuesto de detalles
  por corrida (`--budget`).
- Cron: GitHub Actions cada 6h commitea `jobs_es.html` regenerado.

## Fuera de alcance v0

Telegram push · Meliá/Lidl/Mercadona · Hosteleo/Turiempleo/esquí · Playwright
(agregar solo si alguna fuente bloquea httpx).
