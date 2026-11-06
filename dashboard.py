"""Genera dashboard/index.html a partir de las tablas gold. Sin servidor ni dependencias: se abre en el navegador.

Uso: uv run python dashboard.py [archivo.duckdb]
"""

import math
import sys
from html import escape
from pathlib import Path

import duckdb

RAIZ = Path(__file__).parent
MONEDAS = {"CUP": "CUP efectivo", "TRANSFERENCIA": "Transferencia", "USD": "USD", "MLC": "MLC"}
FUENTES = {"almacen": "Almacén", "pos": "Tienda (POS)", "whatsapp": "WhatsApp"}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def usd(x) -> str:
    return f"{x:,.0f}".replace(",", ".") + " USD"


def dona(partes: list[tuple[str, float]], titulo: str, centro: str) -> str:
    """Anillo SVG: un círculo por segmento, con 2 px de separación; JS anima stroke-dasharray de 0 a su largo."""
    r, ancho = 70, 26
    circ = 2 * math.pi * r
    partes = [(n, float(v)) for n, v in partes]
    total = sum(v for _, v in partes)
    segmentos, leyenda, inicio = [], [], 0.0
    for i, (nombre, valor) in enumerate(partes, 1):
        largo = valor / total * circ
        pct = 100 * valor / total
        tip = f"{nombre}: {usd(valor)} ({pct:.1f} %)"
        segmentos.append(
            f'<circle class="seg" r="{r}" cx="90" cy="90" stroke="var(--s{i})" stroke-width="{ancho}" '
            f'stroke-dasharray="0 {circ:.2f}" data-largo="{max(largo - 2, 0):.2f}" data-circ="{circ:.2f}" '
            f'stroke-dashoffset="{-inicio:.2f}" style="transition-delay:{0.15 * i:.2f}s" '
            f'tabindex="0" data-tip="{escape(tip)}"><title>{escape(tip)}</title></circle>'
        )
        leyenda.append(
            f'<li><i style="background:var(--s{i})"></i><span>{escape(nombre)}</span>'
            f"<b>{pct:.0f} %</b><small>{usd(valor)}</small></li>"
        )
        inicio += largo
    return f"""<figure class="tarjeta dona">
  <figcaption>{titulo}</figcaption>
  <div class="dona-cuerpo">
    <svg viewBox="0 0 180 180" role="img" aria-label="{escape(titulo)}"><g transform="rotate(-90 90 90)">{''.join(segmentos)}</g>
      <text x="90" y="86" class="centro-valor">{centro}</text><text x="90" y="106" class="centro-etiqueta">ingreso total</text></svg>
    <ul class="leyenda">{''.join(leyenda)}</ul>
  </div>
</figure>"""


def linea_margen(semanas: list[tuple]) -> str:
    """Margen % semanal del aceite contra el resto de productos. Un solo eje, con la línea del 0 marcada."""
    w, h, izq, der, arr, aba = 760, 260, 44, 16, 16, 30
    semanas = [(s, float(a), float(b)) for s, a, b in semanas]
    ys = [v for _, a, b in semanas for v in (a, b)]
    y_min, y_max = min(-15, math.floor(min(ys) / 5) * 5 - 5), max(25, math.ceil(max(ys) / 5) * 5)
    x = lambda i: izq + i * (w - izq - der) / (len(semanas) - 1)
    y = lambda v: arr + (y_max - v) * (h - arr - aba) / (y_max - y_min)
    grilla = "".join(
        f'<line x1="{izq}" x2="{w - der}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="{"cero" if v == 0 else "grilla"}"/>'
        f'<text x="{izq - 8}" y="{y(v) + 4:.1f}" class="eje" text-anchor="end">{v} %</text>'
        for v in range(y_min, y_max + 1, 10 if y_max - y_min > 40 else 5)
    )
    ticks, mes_previo = [], None
    for i, (s, _, _) in enumerate(semanas):
        if s.month != mes_previo:
            mes_previo = s.month
            if ticks and x(i) - ultimo_tick < 30:
                ticks.pop()  # la semana que empieza en el mes anterior no gana etiqueta propia
            ultimo_tick = x(i)
            ticks.append(f'<text x="{x(i):.1f}" y="{h - 8}" class="eje">{MESES[s.month - 1]}</text>')
    trazo = lambda k: "M" + " L".join(f"{x(i):.1f},{y(f[k]):.1f}" for i, f in enumerate(semanas))
    zona_roja = (f'<rect x="{izq}" y="{y(0):.1f}" width="{w - izq - der}" height="{y(y_min) - y(0):.1f}" class="zona-perdida"/>'
                 f'<text x="{w - der - 6}" y="{y(0) + 16:.1f}" class="eje perdida" text-anchor="end">vende bajo costo</text>')
    puntos = "".join(
        f'<g class="punto" tabindex="0" data-tip="Semana del {s.day} {MESES[s.month - 1]} · Aceite {a:.1f} % · Resto {b:.1f} %">'
        f'<rect x="{x(i) - 6:.1f}" y="{arr}" width="12" height="{h - arr - aba}" class="golpe"/>'
        f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{arr}" y2="{h - aba}" class="guia"/>'
        f'<circle cx="{x(i):.1f}" cy="{y(a):.1f}" r="4" class="p-aceite"/><circle cx="{x(i):.1f}" cy="{y(b):.1f}" r="4" class="p-resto"/></g>'
        for i, (s, a, b) in enumerate(semanas)
    )
    ult = len(semanas) - 1
    return f"""<svg viewBox="0 0 {w} {h}" class="linea" role="img" aria-label="Margen semanal del aceite contra el resto de productos">
  {zona_roja}{grilla}{''.join(ticks)}
  <path d="{trazo(2)}" class="l-resto" pathLength="1"/>
  <path d="{trazo(1)}" class="l-aceite" pathLength="1"/>
  <text x="{x(ult) - 6:.1f}" y="{y(semanas[ult][2]) - 10:.1f}" class="etiqueta-serie" text-anchor="end">Resto de productos</text>
  <text x="{x(ult) - 6:.1f}" y="{y(semanas[ult][1]) + 20:.1f}" class="etiqueta-serie aceite" text-anchor="end">Aceite</text>
  {puntos}
</svg>"""


def construir(con: duckdb.DuckDBPyConnection) -> str:
    ingreso, margen, bajo_costo = con.execute(
        "SELECT sum(ingreso_usd), sum(margen_usd), sum(lineas_bajo_costo) FROM gold.margen_producto_semana"
    ).fetchone()
    productos = con.execute("""
        SELECT nombre, sum(ingreso_usd), 100 * sum(margen_usd) / sum(ingreso_usd), sum(lineas_bajo_costo)
        FROM gold.margen_producto_semana GROUP BY nombre ORDER BY 3
    """).fetchall()
    por_moneda = dict(con.execute("SELECT moneda, sum(ingreso_usd) FROM gold.ingreso_por_canal GROUP BY 1").fetchall())
    por_fuente = dict(con.execute("SELECT fuente, sum(ingreso_usd) FROM gold.ingreso_por_canal GROUP BY 1").fetchall())
    semanas = con.execute("""
        SELECT semana,
               100 * sum(margen_usd) FILTER (WHERE sku = 'ACEITE-1L') / sum(ingreso_usd) FILTER (WHERE sku = 'ACEITE-1L'),
               100 * sum(margen_usd) FILTER (WHERE sku <> 'ACEITE-1L') / sum(ingreso_usd) FILTER (WHERE sku <> 'ACEITE-1L')
        FROM gold.margen_producto_semana GROUP BY semana ORDER BY semana
    """).fetchall()
    meses = [m for (m,) in con.execute("""
        SELECT DISTINCT strftime(semana, '%Y-%m') FROM gold.margen_producto_semana WHERE semana >= DATE '2026-05-01' ORDER BY 1
    """).fetchall()]
    por_mes = {(n, m): p for n, m, p in con.execute("""
        SELECT nombre, strftime(semana, '%Y-%m'), 100 * sum(margen_usd) / sum(ingreso_usd)
        FROM gold.margen_producto_semana WHERE semana >= DATE '2026-05-01' GROUP BY ALL
    """).fetchall()}
    conciliacion = con.execute("SELECT * FROM gold.conciliacion ORDER BY fuente").fetchall()
    columnas_conc = [d[0].replace("_", " ") for d in con.execute("SELECT * FROM gold.conciliacion LIMIT 0").description]

    aceite_ultimo = por_mes[("Aceite vegetal 1 L", meses[-1])]
    aceite_primero = por_mes[("Aceite vegetal 1 L", meses[0])]
    tope = max(abs(p) for _, _, p, _ in productos)
    barras = "".join(
        f'<div class="fila" tabindex="0" data-tip="{escape(n)}: margen {p:.1f} % sobre {usd(i)}'
        f'{f" · {b} ventas bajo costo" if b else ""}"><span>{escape(n)}</span>'
        f'<div class="pista"><div class="barra{" alerta" if b else ""}" style="--w:{abs(p) / tope * 100:.1f}%;'
        f'animation-delay:{0.05 * k:.2f}s"></div></div><b>{p:.1f} %</b>'
        f'<small>{usd(i)}{f" · <em>▲ {b} ventas bajo costo</em>" if b else ""}</small></div>'
        for k, (n, i, p, b) in enumerate(productos)
    )

    def celda(p):
        if p is None:
            return "<td>–</td>"
        clase, icono = ("neg", "▼ ") if p < 0 else ("bajo", "") if p < 10 else ("", "")
        return f'<td class="{clase}">{icono}{p:.1f}</td>'

    calor = "".join(
        f"<tr><th>{escape(n)}</th>{''.join(celda(por_mes.get((n, m))) for m in meses)}</tr>" for n, *_ in productos
    )
    conc = "".join(
        "<tr>" + "".join(f"<td>{'✓ sí' if v is True else '✗ NO' if v is False else FUENTES.get(v, v)}</td>" for v in fila) + "</tr>"
        for fila in conciliacion
    )
    encabezado_meses = "".join(f"<th>{MESES[int(m[5:]) - 1]}</th>" for m in meses)

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>La Ceiba · Margen real</title>
<style>
:root {{
  color-scheme: light;
  --plano:#f9f9f7; --tarjeta:#fcfcfb; --tinta:#0b0b0b; --tinta-2:#52514e; --muda:#898781;
  --grilla:#e1e0d9; --eje:#c3c2b7; --borde:rgba(11,11,11,.10); --sombra:0 1px 2px rgba(11,11,11,.04), 0 8px 24px rgba(11,11,11,.06);
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100;
  --barra:#2a78d6; --critico:#d03b3b; --critico-fondo:#fbe4e2; --aviso-fondo:#fdf0d2; --bien:#006300;
  --heroe-a:#0d366b; --heroe-b:#2a78d6;
}}
@media (prefers-color-scheme: dark) {{
  :root:where(:not([data-theme="light"])) {{
    color-scheme: dark;
    --plano:#0d0d0d; --tarjeta:#1a1a19; --tinta:#f0efec; --tinta-2:#c3c2b7; --muda:#898781;
    --grilla:#2c2c2a; --eje:#383835; --borde:rgba(255,255,255,.10); --sombra:none;
    --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
    --barra:#3987e5; --critico-fondo:#3d1d1b; --aviso-fondo:#3a2f12; --bien:#0ca30c;
    --heroe-a:#0d366b; --heroe-b:#184f95;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --plano:#0d0d0d; --tarjeta:#1a1a19; --tinta:#f0efec; --tinta-2:#c3c2b7; --muda:#898781;
  --grilla:#2c2c2a; --eje:#383835; --borde:rgba(255,255,255,.10); --sombra:none;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
  --barra:#3987e5; --critico-fondo:#3d1d1b; --aviso-fondo:#3a2f12; --bien:#0ca30c;
  --heroe-a:#0d366b; --heroe-b:#184f95;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--plano); color:var(--tinta); font:15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width:1080px; margin:0 auto; padding:0 16px 56px; }}
.heroe {{ background:linear-gradient(135deg, var(--heroe-a), var(--heroe-b)); color:#fff; padding:40px 16px 88px; }}
.heroe > div {{ max-width:1080px; margin:0 auto; }}
.heroe small {{ letter-spacing:.08em; text-transform:uppercase; opacity:.75; font-size:12px; }}
.heroe h1 {{ margin:6px 0 8px; font-size:clamp(26px, 4vw, 38px); line-height:1.15; }}
.heroe p {{ margin:0; max-width:640px; opacity:.88; }}
.heroe strong {{ background:rgba(255,255,255,.16); padding:1px 6px; border-radius:4px; }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(160px, 1fr)); gap:14px; margin-top:-56px; }}
.tarjeta {{ background:var(--tarjeta); border:1px solid var(--borde); border-radius:14px; box-shadow:var(--sombra); padding:20px; margin:0; }}
.kpi span {{ color:var(--tinta-2); font-size:13px; }}
.kpi b {{ display:block; font-size:30px; line-height:1.2; margin-top:4px; }}
.kpi small {{ color:var(--muda); }}
.kpi.alerta b {{ color:var(--critico); }}
.rejilla {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(min(100%, 440px), 1fr)); gap:14px; margin-top:14px; }}
section.tarjeta {{ margin-top:14px; overflow-x:auto; }}
h2, figcaption {{ font-size:17px; font-weight:650; margin:0 0 2px; }}
.nota {{ color:var(--tinta-2); margin:0 0 14px; font-size:14px; }}
.dona-cuerpo {{ display:flex; align-items:center; gap:20px; flex-wrap:wrap; margin-top:12px; }}
.dona svg {{ width:180px; height:180px; flex:none; }}
.seg {{ fill:none; transition:stroke-dasharray 1.1s cubic-bezier(.2,.8,.2,1), opacity .2s; cursor:pointer; outline:none; }}
.dona svg:hover .seg {{ opacity:.45; }} .dona svg .seg:hover, .dona svg .seg:focus {{ opacity:1; }}
.centro-valor {{ font-size:22px; font-weight:700; text-anchor:middle; fill:var(--tinta); }}
.centro-etiqueta {{ font-size:11px; text-anchor:middle; fill:var(--muda); }}
.leyenda {{ list-style:none; margin:0; padding:0; flex:1; min-width:180px; }}
.leyenda li {{ display:grid; grid-template-columns:12px 1fr auto; gap:2px 10px; align-items:center; padding:7px 0; border-bottom:1px solid var(--grilla); }}
.leyenda li:last-child {{ border:0; }}
.leyenda i {{ width:12px; height:12px; border-radius:3px; }}
.leyenda b {{ font-variant-numeric:tabular-nums; }}
.leyenda small {{ grid-column:2 / 4; color:var(--muda); margin-top:-4px; }}
.linea {{ width:100%; min-width:560px; height:auto; display:block; }}
.grilla {{ stroke:var(--grilla); stroke-width:1; }} .cero {{ stroke:var(--eje); stroke-width:1.5; }}
.eje {{ fill:var(--muda); font-size:11px; font-variant-numeric:tabular-nums; }}
.eje.perdida {{ fill:var(--critico); font-weight:600; }}
.zona-perdida {{ fill:var(--critico-fondo); opacity:.6; }}
.l-aceite, .l-resto {{ fill:none; stroke-width:2.5; stroke-linejoin:round; stroke-linecap:round; stroke-dasharray:1; stroke-dashoffset:1; animation:dibujar 2s .3s ease-out forwards; }}
.l-aceite {{ stroke:var(--s2); }} .l-resto {{ stroke:var(--muda); stroke-width:2; animation-delay:.1s; }}
.etiqueta-serie {{ font-size:12px; font-weight:600; fill:var(--tinta-2); opacity:0; animation:aparecer .4s 2.1s forwards; }}
.etiqueta-serie.aceite {{ fill:var(--tinta); }}
.punto .golpe {{ fill:transparent; }} .punto .guia {{ stroke:var(--eje); stroke-width:1; opacity:0; }}
.punto circle {{ opacity:0; stroke:var(--tarjeta); stroke-width:2; }}
.p-aceite {{ fill:var(--s2); }} .p-resto {{ fill:var(--muda); }}
.punto:hover circle, .punto:focus circle, .punto:hover .guia, .punto:focus .guia {{ opacity:1; }}
.punto {{ outline:none; cursor:crosshair; }}
.leyenda-linea {{ display:flex; gap:18px; font-size:13px; color:var(--tinta-2); margin:-4px 0 8px; }}
.leyenda-linea i {{ display:inline-block; width:16px; height:3px; border-radius:2px; vertical-align:middle; margin-right:6px; }}
.fila {{ display:grid; grid-template-columns:180px 1fr 64px; gap:2px 12px; align-items:center; padding:6px 0; outline:none; border-radius:6px; }}
.fila:hover, .fila:focus {{ background:var(--plano); }}
.fila small {{ grid-column:2 / 4; color:var(--muda); }}
.fila em {{ color:var(--critico); font-style:normal; font-weight:600; }}
.pista {{ height:10px; }}
.barra {{ height:100%; width:0; background:var(--barra); border-radius:0 4px 4px 0; animation:crecer 1s cubic-bezier(.2,.8,.2,1) forwards; }}
.barra.alerta {{ background:var(--critico); }}
.fila b {{ text-align:right; font-variant-numeric:tabular-nums; }}
table {{ border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; font-size:14px; }}
th, td {{ padding:8px 10px; border-bottom:1px solid var(--grilla); text-align:right; white-space:nowrap; }}
th {{ color:var(--tinta-2); font-weight:600; }}
th:first-child, td:first-child {{ text-align:left; }}
tbody th {{ color:var(--tinta); font-weight:500; }}
td.bajo {{ background:var(--aviso-fondo); }}
td.neg {{ background:var(--critico-fondo); color:var(--critico); font-weight:700; }}
.aparece {{ opacity:0; transform:translateY(14px); transition:opacity .6s ease, transform .6s ease; }}
.aparece.visible {{ opacity:1; transform:none; }}
#tip {{ position:fixed; pointer-events:none; z-index:10; background:var(--tinta); color:var(--plano); font-size:13px; padding:6px 10px; border-radius:8px; opacity:0; transition:opacity .12s; max-width:280px; }}
@keyframes dibujar {{ to {{ stroke-dashoffset:0; }} }}
@keyframes crecer {{ to {{ width:var(--w); }} }}
@keyframes aparecer {{ to {{ opacity:1; }} }}
@media (max-width:560px) {{ .fila {{ grid-template-columns:110px 1fr 56px; }} .dona-cuerpo {{ justify-content:center; }} }}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ animation-duration:0s !important; animation-delay:0s !important; transition:none !important; }}
  .aparece {{ opacity:1; transform:none; }}
}}
</style></head><body>
<header class="heroe"><div>
  <small>La Ceiba · mayorista de alimentos · mayo a octubre 2026</small>
  <h1>El aceite pasó de ganar {aceite_primero:.0f} % a perder {abs(aceite_ultimo):.0f} %</h1>
  <p>Su precio en CUP no se reajustó mientras la tasa informal subía. Desde septiembre <strong>cada botella se vende por debajo de lo que costó</strong>. El resto del catálogo aguanta entre 15 y 18 %.</p>
</div></header>
<main>
<div class="kpis">
  <div class="tarjeta kpi"><span>Ingreso en USD</span><b data-contar="{ingreso:.0f}" data-sufijo=" USD">0</b><small>todas las monedas a tasa del día</small></div>
  <div class="tarjeta kpi"><span>Margen en USD</span><b data-contar="{margen:.0f}" data-sufijo=" USD">0</b><small>ingreso menos último costo de compra</small></div>
  <div class="tarjeta kpi"><span>Margen sobre ingreso</span><b data-contar="{100 * margen / ingreso:.1f}" data-decimales="1" data-sufijo=" %">0</b><small>promedio del catálogo</small></div>
  <div class="tarjeta kpi alerta"><span>▲ Ventas bajo costo</span><b data-contar="{bajo_costo}">0</b><small>todas de aceite</small></div>
</div>

<div class="rejilla">
  {dona([(MONEDAS[m], por_moneda[m]) for m in MONEDAS if m in por_moneda], "¿En qué moneda entra la plata?", f"{ingreso / 1000:.0f} k")}
  {dona([(FUENTES[f], por_fuente[f]) for f in FUENTES if f in por_fuente], "¿Por qué canal se vende?", f"{ingreso / 1000:.0f} k")}
</div>

<section class="tarjeta aparece">
  <h2>Margen semanal: aceite contra el resto</h2>
  <p class="nota">Pasa el cursor por la gráfica para ver cada semana.</p>
  <div class="leyenda-linea"><span><i style="background:var(--s2)"></i>Aceite vegetal 1 L</span><span><i style="background:var(--muda)"></i>Resto de productos</span></div>
  {linea_margen(semanas)}
</section>

<section class="tarjeta aparece">
  <h2>Margen por producto</h2>
  <p class="nota">Ordenado de peor a mejor. En rojo, productos con ventas por debajo del costo.</p>
  {barras}
</section>

<section class="tarjeta aparece">
  <h2>Margen % por mes</h2>
  <p class="nota">Ámbar: menos de 10 %. Rojo con ▼: se vende por debajo del costo.</p>
  <table><thead><tr><th>Producto</th>{encabezado_meses}</tr></thead><tbody>{calor}</tbody></table>
</section>

<section class="tarjeta aparece">
  <h2>¿Cuadra con los archivos?</h2>
  <p class="nota">Cada fila que llegó en los archivos termina en exactamente un destino. Datos sintéticos.</p>
  <table><thead><tr>{''.join(f'<th>{c}</th>' for c in columnas_conc)}</tr></thead><tbody>{conc}</tbody></table>
</section>
</main>
<div id="tip" role="tooltip"></div>
<script>
const quieto = matchMedia("(prefers-reduced-motion: reduce)").matches;
const formato = (v, d) => v.toLocaleString("es", {{ minimumFractionDigits: d, maximumFractionDigits: d }});
document.querySelectorAll("[data-contar]").forEach(el => {{
  const fin = +el.dataset.contar, d = +(el.dataset.decimales || 0), suf = el.dataset.sufijo || "";
  if (quieto) {{ el.textContent = formato(fin, d) + suf; return; }}
  const t0 = performance.now(), dur = 1400;
  const paso = t => {{
    const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
    el.textContent = formato(fin * e, d) + suf;
    if (k < 1) requestAnimationFrame(paso);
  }};
  requestAnimationFrame(paso);
}});
requestAnimationFrame(() => requestAnimationFrame(() =>
  document.querySelectorAll(".seg").forEach(s => s.setAttribute("stroke-dasharray", `${{s.dataset.largo}} ${{s.dataset.circ}}`))
));
const obs = new IntersectionObserver(es => es.forEach(e => {{
  if (e.isIntersecting) {{ e.target.classList.add("visible"); obs.unobserve(e.target); }}
}}), {{ threshold: 0.12 }});
document.querySelectorAll(".aparece").forEach(el => obs.observe(el));
const tip = document.getElementById("tip");
const mostrar = (el, x, y) => {{
  tip.textContent = el.dataset.tip; tip.style.opacity = 1;
  const w = tip.offsetWidth;
  tip.style.left = Math.min(x + 14, innerWidth - w - 8) + "px"; tip.style.top = (y + 14) + "px";
}};
addEventListener("scroll", () => tip.style.opacity = 0, {{ passive: true }});
document.querySelectorAll("[data-tip]").forEach(el => {{
  el.addEventListener("mousemove", ev => mostrar(el, ev.clientX, ev.clientY));
  el.addEventListener("mouseleave", () => tip.style.opacity = 0);
  el.addEventListener("focus", () => {{ const r = el.getBoundingClientRect(); mostrar(el, r.left, r.top); }});
  el.addEventListener("blur", () => tip.style.opacity = 0);
}});
</script>
</body></html>
"""


if __name__ == "__main__":
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "la_ceiba.duckdb"
    salida = RAIZ / "dashboard" / "index.html"
    salida.write_text(construir(duckdb.connect(str(db), read_only=True)), encoding="utf-8")
    print(f"Dashboard en {salida}")
