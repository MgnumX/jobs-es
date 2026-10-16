"""Genera jobs_es.html: un único archivo autónomo, filtrable offline."""
import datetime as dt
import json
from pathlib import Path

from .normalize import quality

OUT = Path(__file__).resolve().parents[2] / "jobs_es.html"
REPORT_PATH = Path(__file__).resolve().parents[2] / "data" / "report.json"

_CSS = """
/* =========================================================
   ESTETICAMAXXING - GLASSMORPHISM PREMIUM OFFLINE
   Dark base #0B1F14 - blur solo en fijas, cards fake glass
   ========================================================= */
:root {
  --bg-deep: #04100c;
  --bg-main: #071510;
  --bg-soft: #0b1f14;
  --ink: #eafff8;
  --muted: rgba(234, 255, 248, 0.68);
  --faint: rgba(234, 255, 248, 0.40);
  --line: rgba(255, 255, 255, 0.12);
  --line-strong: rgba(255, 255, 255, 0.18);
  --glass: rgba(255, 255, 255, 0.075);
  --glass-2: rgba(255, 255, 255, 0.045);
  --glass-dark: rgba(6, 17, 13, 0.58);
  --aqua: #2ee6c8;
  --lime: #99f26d;
  --gold: #ffd166;
  --blue: #67b7ff;
  --violet: #b79cff;
  --pink: #ff7a90;
  --radius-lg: 22px;
  --radius-md: 18px;
  --radius-sm: 14px;
  --shadow-md: 0 12px 34px rgba(0, 0, 0, 0.22);
  --shadow-lg: 0 24px 80px rgba(0, 0, 0, 0.38);
  --glow-aqua: rgba(46, 230, 200, 0.12);
  --glow-blue: rgba(103, 183, 255, 0.10);
  --glow-violet: rgba(183, 156, 255, 0.10);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;color:var(--ink);
  font:16px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;
  -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
  background:
    radial-gradient(1100px 700px at 12% 8%, rgba(46, 230, 200, 0.20), transparent 56%),
    radial-gradient(900px 650px at 88% 16%, rgba(103, 183, 255, 0.16), transparent 58%),
    radial-gradient(900px 700px at 74% 92%, rgba(183, 156, 255, 0.14), transparent 55%),
    radial-gradient(700px 500px at 28% 82%, rgba(153, 242, 109, 0.10), transparent 60%),
    linear-gradient(180deg, var(--bg-deep), var(--bg-main) 40%, var(--bg-soft) 100%);
  background-attachment:fixed; min-height:100vh;
}
body::before{
  content:""; position:fixed; inset:0; z-index:-2; pointer-events:none;
  background:
    radial-gradient(900px 600px at 70% 20%, var(--glow-aqua), transparent 60%),
    radial-gradient(700px 500px at 20% 70%, var(--glow-blue), transparent 60%),
    radial-gradient(800px 600px at 85% 75%, var(--glow-violet), transparent 62%);
  animation: estetica-aurora 24s ease-in-out infinite alternate; opacity:0.95;
}
@keyframes estetica-aurora{from{transform:translate3d(-1.5%,-1%,0) scale(1)}to{transform:translate3d(1.5%,1%,0) scale(1.03)}}
body::after{
  content:""; position:fixed; inset:0; z-index:-1; pointer-events:none; opacity:0.14; mix-blend-mode:soft-light;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.05'/%3E%3C/svg%3E");
  background-size:180px 180px;
}
::selection{background:rgba(46,230,200,0.28);color:white}
/* glass solo en fijas: status, filtros */
#status,.status,#bar,.filters,.toolbar,header.glass,.glass{
  background: linear-gradient(180deg, rgba(255,255,255,0.10), rgba(255,255,255,0.05)), linear-gradient(180deg, rgba(7,21,16,0.52), rgba(7,21,16,0.42));
  border:1px solid var(--line); border-radius:var(--radius-md);
  -webkit-backdrop-filter:blur(18px) saturate(155%); backdrop-filter:blur(18px) saturate(155%);
  box-shadow: var(--shadow-md), inset 0 1px 0 rgba(255,255,255,0.08);
}
#status,.status{position:sticky;top:12px;z-index:70;margin:14px auto 0;max-width:1440px;padding:12px 16px;font-size:13px;color:var(--muted);letter-spacing:0.15px}
#bar{position:sticky;top:72px;z-index:60;margin:12px auto 0;max-width:1440px;padding:12px;display:flex;flex-wrap:wrap;gap:10px;align-items:center}
main,.container,#app,.wrap{position:relative;z-index:1;max-width:1440px;margin:0 auto;padding:16px}
#list,.jobs,.cards,.results{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px;margin-top:16px}
.count{font-size:12px;color:var(--muted);margin:10px 0}
/* cards fake glass sin backdrop-filter masivo - ponytail: 1400 cards sin blur */
.card,.glass-card,.job-card,article.job,.offer{
  position:relative; overflow:hidden; border-radius:var(--radius-lg);
  border:1px solid rgba(255,255,255,0.10);
  background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.035)), linear-gradient(180deg, rgba(6,17,13,0.64), rgba(6,17,13,0.55));
  box-shadow:0 10px 26px rgba(0,0,0,0.16);
  transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
  padding:16px; min-height:120px;
}
.card::before,.glass-card::before{content:"";position:absolute;inset:0 0 auto 0;height:1px;background:linear-gradient(90deg, transparent, rgba(255,255,255,0.22), transparent);opacity:0.55;pointer-events:none}
.card:hover,.glass-card:hover{transform:translateY(-2px);border-color:rgba(46,230,200,0.28);box-shadow:0 18px 50px rgba(0,0,0,0.30), 0 0 0 1px rgba(46,230,200,0.08), 0 0 44px rgba(46,230,200,0.08)}
.card::after{content:"";position:absolute;inset:0;pointer-events:none;opacity:0;transition:opacity 0.18s ease;background:radial-gradient(280px 120px at 20% 0%, rgba(46,230,200,0.09), transparent 62%), radial-gradient(280px 120px at 85% 100%, rgba(103,183,255,0.06), transparent 60%)}
.card:hover::after{opacity:1}
.card b{font-size:15px}.meta{font-size:12px;color:var(--muted);margin-top:3px}
.sal{white-space:nowrap;font-weight:900;color:#f4fff9;font-size:13px;text-align:right;letter-spacing:0.2px;text-shadow:0 0 28px rgba(46,230,200,0.12)}
.score{font-size:11px;color:var(--gold);display:block}
.tag,.badge,.b{display:inline-flex;align-items:center;gap:6px;padding:4px 9px;border-radius:999px;border:1px solid rgba(255,255,255,0.14);background:linear-gradient(180deg, rgba(255,255,255,0.12), rgba(255,255,255,0.05));color:var(--ink);font-size:11px;font-weight:800;letter-spacing:0.25px;white-space:nowrap;box-shadow:inset 0 1px 0 rgba(255,255,255,0.08)}
.badge.new,.b.new{background:linear-gradient(180deg, #5df2d7, #19c8a9);color:#04221b;border-color:rgba(255,255,255,0.30);box-shadow:0 0 24px rgba(46,230,200,0.18)}
.tag.warn,.badge.urgent{background:rgba(255,122,144,0.12);border-color:rgba(255,122,144,0.22);color:#ffe4e9}
.tag.blue{background:rgba(103,183,255,0.12);border-color:rgba(103,183,255,0.22);color:#e5f1ff}
a{color:var(--aqua);text-decoration:none;transition:color 0.15s ease, text-shadow 0.15s ease}a:hover{color:#7df7e1;text-shadow:0 0 22px rgba(46,230,200,0.22)}
.empty{padding:30px;text-align:center;color:var(--muted)}
select{color-scheme:dark}
select option,select optgroup{color:#eafff8 !important;background:#0b1f14 !important}
select option:checked,select option:hover{background:#14342b !important;color:#eafff8 !important}
input,select{background:linear-gradient(180deg, rgba(255,255,255,0.09), rgba(255,255,255,0.05));border:1px solid rgba(255,255,255,0.14);border-radius:14px;padding:10px 12px;font:inherit;color:var(--ink);box-shadow:inset 0 1px 0 rgba(255,255,255,0.06)}
input:focus-visible,select:focus-visible{border-color:rgba(46,230,200,0.58);box-shadow:0 0 0 4px rgba(46,230,200,0.10), inset 0 1px 0 rgba(255,255,255,0.06)}
.chip{cursor:pointer;border-radius:999px;padding:4px 10px;font-size:12px;border:1px solid rgba(255,255,255,0.14);background:rgba(255,255,255,0.06)}
.chip.on{background:rgba(46,230,200,0.14);border-color:rgba(46,230,200,0.30);color:var(--aqua)}
@media (max-width:1000px){#bar{top:64px}#list{grid-template-columns:repeat(auto-fill,minmax(300px,1fr))}}
@media (max-width:720px){body{background-attachment:scroll}#status{top:8px;font-size:12px}#bar{top:58px;padding:10px}#list{grid-template-columns:1fr;gap:12px}.card{padding:14px}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}html{scroll-behavior:auto}}
/* titular neogotico centrado - fix obs truncado */
header{text-align:center;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:22px 20px 18px}
header h1{font-family:'Cinzel','UnifrakturCook','Old English Text MT',Georgia,serif;text-align:center;font-size:32px;font-weight:900;letter-spacing:0.16em;text-transform:uppercase;text-shadow:0 2px 0 #000, 0 0 22px rgba(46,230,200,0.35), 0 0 42px rgba(183,156,255,0.18);margin:0 auto;line-height:1.1;max-width:100%;overflow:visible;white-space:nowrap}
header .sub{text-align:center;margin:8px auto 0;max-width:820px}
@media(max-width:720px){header h1{font-size:22px;letter-spacing:0.10em;white-space:normal}}


/* titular neogotico centrado - fix obs truncado */
header{text-align:center;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:22px 20px 18px}
header h1{font-family:'Cinzel','UnifrakturCook','Old English Text MT',Georgia,serif;text-align:center;font-size:32px;font-weight:900;letter-spacing:0.16em;text-transform:uppercase;text-shadow:0 2px 0 #000, 0 0 22px rgba(46,230,200,0.35), 0 0 42px rgba(183,156,255,0.18);margin:0 auto;line-height:1.1;max-width:100%;overflow:visible;white-space:nowrap}
header .sub{text-align:center;margin:8px auto 0;max-width:820px}
@media(max-width:720px){header h1{font-size:22px;letter-spacing:0.10em;white-space:normal}}
"""


_BODY = """
<header><h1>Jobs España · ofertas reales</h1>
<div class="sub">Generado {gen} · fuentes directas y nicho · 💰x = €/h ÷ €/h de habitación en esa ciudad (&gt;3 = buen chollo)</div>
<div id="status" class="glass">{status_line}</div>
<div id="bar" class="glass">
<input id="q" placeholder="Puesto o ciudad..." size="22">
<select id="sec"><option value="todos">todos los sectores</option>{sec_opts}</select>
<select id="prov"><option value="todas">todas las provincias</option>{prov_opts}</select>
<label><input type="checkbox" id="hous">🏠 alojamiento</label>
<label><input type="checkbox" id="food">🍽 comida</label>
<label><input type="checkbox" id="direct">⚡ directo</label>
<label><input type="checkbox" id="urgent">🚀 urgente</label>
<label><input type="checkbox" id="fresh">⏱ ≤72h</label>
<label><input type="checkbox" id="fnew"> solo nuevas</label>
<select id="sort"><option value="score">💰 calidad-precio</option>
<option value="hourly">€/h ↓</option><option value="new">más nuevas</option></select>
<span style="flex:1"></span>{chips}
</div></header>
<main><div class="count" id="count"></div><div id="list"></div></main>
<script>const JOBS={jobs};const STATUS={status_json};{js}</script>
"""

_JS = r"""
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const SEC_ES={hosteleria:'hostelería',logistica:'logística',comercio:'comercio',temporada:'temporada',otros:'otros'};
try{ const s=document.getElementById('status'); if(s && typeof STATUS==='string') s.textContent=STATUS; }catch(e){}
let state={q:'',sec:'todos',prov:'todas',hous:false,food:false,direct:false,urgent:false,fresh:false,fnew:false,sort:'score'};
function render(){
  const cut=Date.now()-72*3600*1000;
  let rows=JOBS.filter(j=>{
    if(state.hous&&!j.housing)return false;
    if(state.food&&!j.food)return false;
    if(state.direct&&!j.direct)return false;
    if(state.urgent&&!j.urgent)return false;
    if(state.fnew&&!j.new)return false;
    if(state.fresh){const t=Date.parse(j.posted||'')||Date.parse(j.seen||'')||0;
      if(t&&t<cut)return false;}
    if(state.sec!=='todos'&&j.sector!==state.sec)return false;
    if(state.prov!=='todas'&&j.province!==state.prov)return false;
    if(state.q){const s=(j.title+' '+j.company+' '+j.city).toLowerCase();
      if(!s.includes(state.q))return false;}
    return true;});
  const eff=j=>j.eff!=null?j.eff:-1;
  rows.sort({score:(a,b)=>((b.score??-1)-(a.score??-1))||((b.explicit?1:0)-(a.explicit?1:0)),
             hourly:(a,b)=>(eff(b)-eff(a))||((b.explicit?1:0)-(a.explicit?1:0)),
             new:(a,b)=>(b.posted||'').localeCompare(a.posted||'')}[state.sort]);
  $('count').textContent=rows.length+' de '+JOBS.length+' ofertas';
  $('list').innerHTML=rows.map(j=>{
    const hous=j.housing||j.hous; const food=j.food; const direct=j.direct; const urgent=j.urgent;
    const badges=[];
    if(j.new) badges.push('<span class="badge new">NUEVA</span>');
    if(j.explicit) badges.push('<span class="badge salary">€/h REAL</span>');
    else if(j.est) badges.push('<span class="badge est">ESTIMADO</span>');
    if(hous) badges.push('<span class="badge housing">ALOJAMIENTO</span>');
    if(food) badges.push('<span class="badge food">COMIDA</span>');
    if(direct) badges.push('<span class="badge direct">DIRECTA</span>'); else badges.push('<span class="badge ett">ETT</span>');
    if(urgent) badges.push('<span class="badge urgent">URGENTE</span>');
    return `<article class="card glass-card">
    <div><b><a href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a></b> ${badges.join(' ')}
      <div class="meta">${esc(j.company||'-')} · ${esc(j.city||j.province||'España')}
        <span class="badge blue">${esc(j.source)}</span>
        <span class="badge">${SEC_ES[j.sector]||esc(j.sector)}</span>
        ${j.posted?'· '+esc(j.posted):''}</div></div>
    <div class="sal">${j.hourly?j.hourly.toFixed(2)+' €/h'
      :j.est?`<span style="color:#93c5fd;cursor:help" title="Estimación.${j.est_src==='mediana'?' Mediana observada en este rol/ciudad.':' Convenio colectivo.'} No la vio en la oferta.">~${j.est.toFixed(2)} €/h</span>`
      :'<span style=color:#9db8aa>n/d</span>'}
      ${j.score?`<span class="score">💰 x${j.score}</span>`:''}
      ${j.est&&!j.hourly?`<span class="score" style="color:#93c5fd">${j.est_src}</span>`:''}</div>
  </article>`}).join('')||'<div class="empty">Sin resultados con estos filtros.</div>';
}
for(const[id,key,type]of[['q','q'],['sec','sec'],['prov','prov'],['sort','sort'],
    ['hous','hous','c'],['food','food','c'],['direct','direct','c'],
    ['urgent','urgent','c'],['fresh','fresh','c'],['fnew','fnew','c']])
  $(id).addEventListener('input',e=>{state[key]=type==='c'?e.target.checked:e.target.value;render();});
document.querySelectorAll('.chip[data-sec]').forEach(c=>c.addEventListener('click',()=>{
  document.querySelectorAll('.chip[data-sec]').forEach(x=>x.classList.remove('on'));
  c.classList.add('on');state.sec=c.dataset.sec;$('sec').value=c.dataset.sec;render();}));
render();
"""


def _load_report() -> dict:
    try:
        return json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build(rows: list[dict]) -> Path:
    from collections import defaultdict
    import statistics
    from .normalize import CONVENIO_EST, quality, tier_of, title_cluster

    buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in rows:
        if r.get("hourly"):
            buckets[(title_cluster(r["title"]) or r["sector"], tier_of(r["city"]))].append(float(r["hourly"]))
    medians = {k: statistics.median(v) for k, v in buckets.items() if v}

    def _est(r: dict) -> tuple[float | None, str]:
        if r.get("hourly"):
            return None, ""
        cl = title_cluster(r["title"]) or r["sector"]
        tier = tier_of(r["city"])
        if (cl, tier) in medians:
            return round(medians[(cl, tier)], 2), "mediana"
        if (cl, tier) in CONVENIO_EST:
            return CONVENIO_EST[(cl, tier)], "convenio"
        if (r["sector"], tier) in CONVENIO_EST:
            return CONVENIO_EST[(r["sector"], tier)], "convenio"
        return None, ""

    report = _load_report()
    now = dt.datetime.now()
    today = now.strftime("%Y-%m-%d")
    sources = report.get("sources", {})
    ok_sources = sum(1 for s in sources.values() if s.get("ok"))
    total_sources = len(sources) or 9
    warn_sources = [name for name, s in sources.items() if not s.get("ok") or s.get("warnings")]
    new_today = 0

    def _title_fallback(r: dict) -> str:
        t = (r.get("title") or "").strip()
        if t:
            return t
        # ponytail: nunca link invisible si parser falla — slug legible
        try:
            from urllib.parse import unquote
            slug = unquote((r.get("url") or "").rstrip("/").split("/")[-2])
            if slug and len(slug) > 3:
                return slug.replace("-", " ").title()[:80]
        except Exception:
            pass
        return r.get("url") or "Oferta sin título"

    jobs = []
    for r in rows:
        if r.get("score") is not None and r.get("eff_hourly") is not None:
            has = bool(r["hourly"])
            est = r.get("hourly_est") if not has else None
            eff = r.get("eff_hourly")
            score = r.get("score")
            est_src = r.get("score_src") or r.get("est_src") or ""
        else:
            eff, est_src = _est(r)
            has = bool(r["hourly"])
            est = eff if not has else None
            score = quality(r["hourly"] if has else (eff or 0), r["city"]) if (has or eff) else None
            eff = round(r["hourly"], 2) if has else eff
        is_new = (r.get("first_seen") or "")[:10] == today
        if is_new:
            new_today += 1
        j = {
            "title": _title_fallback(r), "url": r["url"], "company": r["company"] or "",
            "city": r["city"] or "", "province": r["province"] or "",
            "sector": r["sector"] or "otros", "source": r["source"],
            "housing": bool(r["housing"]), "food": bool(r["food"]),
            "direct": bool(r["direct"]), "urgent": bool(r["urgent"]),
            "seen": (r["first_seen"] or "")[:10],
            "hourly": round(r["hourly"], 2) if has else None,
            "est": est if not has else None, "est_src": est_src if est else "",
            "eff": eff if has or est else None,
            "explicit": has,
            "score": score,
            "posted": (r["posted_at"] or "")[:10],
            "new": 1 if is_new else 0,
        }
        jobs.append(j)

    status_bits = [
        f"Generado {now.strftime('%Y-%m-%d %H:%M')}",
        f"{len(rows)} activas",
        f"{report.get('total_jobs', len(rows))} totales",
        f"{new_today} nuevas hoy",
        f"fuentes {ok_sources}/{total_sources} OK",
    ]
    if warn_sources:
        status_bits.append("⚠ " + ", ".join(warn_sources))
    status_line = " · ".join(status_bits)
    status_json = json.dumps(status_line, ensure_ascii=False)

    sectors = sorted({j["sector"] for j in jobs})
    provs = sorted({(j["province"] or j["city"]).title() for j in jobs
                    if (j["province"] or j["city"])})
    chips = '<span class="chip on" data-sec="todos">todo</span>' + "".join(
        f'<span class="chip" data-sec="{s}">{_sec_name(s)}</span>'
        for s in sectors if s in ("hosteleria", "logistica", "comercio", "temporada"))
    html = _BODY.format(
        gen=dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        status_line=status_line,
        status_json=status_json,
        sec_opts="".join(f'<option value="{s}">{s}</option>' for s in sectors),
        prov_opts="".join(f'<option value="{p}">{p}</option>' for p in provs),
        chips=chips,
        jobs=json.dumps(jobs, ensure_ascii=False).replace("</", "<\\/"),
        js=_JS,
    )
    OUT.write_text("<!DOCTYPE html>\n<html lang=\"es\"><head>"
                   "<meta charset=\"utf-8\"><title>Jobs España</title>"
                   "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
                   f"<style>{_CSS}</style></head><body>{html}</body></html>",
                   encoding="utf-8")
    return OUT


def _sec_name(s: str) -> str:
    return {"hosteleria": "🏨 hostelería", "logistica": "📦 logística",
            "comercio": "🛒 comercio", "temporada": "⛺ temporada"}.get(s, s)
