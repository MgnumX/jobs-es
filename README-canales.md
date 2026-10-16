# Canales manuales que complementan este scraper

El scraper cubre fuentes API-friendly. Estos canales NO son scrapeables
(hoy) pero conviene registrarte una vez en cada uno — ahí te buscan a TI:

## App (registro único, 15 min)

| Canal | Por qué |
|---|---|
| **JobToday** (app) | Probado como scraper y DESCARTADO (2026-08-26): el listado se lee, pero el detalle de cada oferta da 403 (WAF que fuerza la app) y sus salarios por hora vienen inflados en origen (80 €/h "ayudante"). Sigue valiendo como app manual: chat directo con reclutadores, ofertas caducan rápido. |
| **Randstad Flex** (app) | Turnos de logística/comercio/hostelería con contratación directa por la ETT desde la app. El listado web de randstad.es SÍ lo cubre el adaptador `randstad` del scraper; lo no scrapeable es el flujo interno de la app Flex. |
| **Eurofirms** | Mayor ETT española, proceso 100% digital, firman contrato online y arrancas en días (bloquea bots por TLS; humanos entran normal). |

## Vía descartada: bypass de apps móviles (InfoJobs, Randstad Flex, Eurofirms)

**Decisión 2026-08-25, presupuesto cero — NO reevaluar sin motivo nuevo.**
(Excluye la *vía del bypass*, no los portales: el adaptador `infojobs` usa la
API pública oficial y `randstad` cubre el listado web.)

- **Coste de incluirlos:** ingeniería inversa del cliente móvil + infraestructura
  de proxies residenciales rotativos ≈ **30–50 €/mes** y **6–8 h** de trabajo,
  más fragilidad permanente ante cada cambio de su API privada.
- **Beneficio esperado: BAJO.** El problema de InfoJobs no es técnico sino de
  dato: domina el volumen pero prolifera la oferta fantasma (puestos ya
  cubiertos que alimentan su funnel de CVs). Traería ruido, no señal.
- **Reevaluar solo si:** (a) hay presupuesto para proxies residenciales,
  o (b) se necesita cobertura administrativa/ofimática que las fuentes
  actuales (JobToday general, JT) no cubren.

## Muertas o trampa

- **CornerJob** — el dominio está en venta; proyecto absorbido/abandonado.
- **Adecco web** — redirige a un site global SPA sin API accesible; source
  desactivado (`_adecco_disabled.py`) hasta capturar el endpoint nuevo.
  Mejor entrar por la app o por oficina física.
- **Scrapeo masivo de InfoJobs / LinkedIn vía bypass** — ver bloque anterior.
  (El adaptador `infojobs` usa la API oficial con credenciales propias.)

## Tácticas anti-oferta-fantasma (aplicadas al scraper)

1. **Filtro ⏱ ≤72h** en el HTML: lo que lleva semanas abierto suele estar
   desatendido o ya cubierto.
2. **Chip 🚀 urgente**: "incorporación inmediata" = necesitan gente YA.
3. **Aplicar directo**: Amazon y cadenas hoteleras se aplican en su propia
   web (flag ⚡ directo), no a través del portal intermediario.
4. Si una oferta te interesa pero es vieja, busca el nombre del hotel/empresa
   + "trabaja con nosotros" — su base de datos propia siempre manda.
