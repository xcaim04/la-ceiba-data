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
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
ACEITE = "Aceite vegetal 1 L"


def usd(x) -> str:
    return f"{x:,.0f}".replace(",", ".") + " USD"


def pct(x, signo=False) -> str:
    texto = f"{abs(x):.1f}".replace(".", ",") + " %"
    return ("−" if x < 0 else "+" if signo else "") + texto


def entero(x) -> str:
    return f"{x:,.0f}".replace(",", ".")


def dona(partes: list[tuple[str, float]], titulo: str, resumen: str) -> str:
    """Anillo SVG: un círculo por segmento, con 2 px de separación; se dibuja una vez al entrar en pantalla."""
    partes = [(n, float(v)) for n, v in partes]
    r, ancho = 64, 18
    circ = 2 * math.pi * r
    total = sum(v for _, v in partes)
    segmentos, filas, inicio = [], [], 0.0
    for i, (nombre, valor) in enumerate(partes, 1):
        largo = valor / total * circ
        porcentaje = 100 * valor / total
        tip = f"{nombre}: {usd(valor)}, {pct(porcentaje)} del ingreso"
        segmentos.append(
            f'<circle class="seg" r="{r}" cx="80" cy="80" stroke="var(--s{i})" stroke-width="{ancho}" '
            f'stroke-dasharray="0 {circ:.2f}" data-largo="{max(largo - 2, 0):.2f}" data-circ="{circ:.2f}" '
            f'stroke-dashoffset="{-inicio:.2f}" style="transition-delay:{0.08 * i:.2f}s" data-tip="{escape(tip)}"/>'
        )
        filas.append(
            f'<tr tabindex="0" data-tip="{escape(tip)}"><th scope="row"><i style="background:var(--s{i})"></i>{escape(nombre)}</th>'
            f"<td>{usd(valor)}</td><td><b>{pct(porcentaje)}</b></td></tr>"
        )
        inicio += largo
    return f"""<article class="tarjeta dona">
  <h3>{titulo}</h3>
  <p class="resumen">{resumen}</p>
  <div class="dona-cuerpo">
    <svg viewBox="0 0 160 160" aria-hidden="true"><g transform="rotate(-90 80 80)">{''.join(segmentos)}</g></svg>
    <table class="leyenda"><caption class="oculto">{titulo}</caption><tbody>{''.join(filas)}</tbody></table>
  </div>
</article>"""


def linea_margen(semanas: list[tuple]) -> str:
    """Margen % semanal del aceite contra el resto. Un solo eje, la línea del 0 marcada y tres anotaciones."""
    semanas = [(s, float(a), float(b)) for s, a, b in semanas]
    w, h, izq, der, arr, aba = 820, 320, 48, 24, 28, 34
    ys = [v for _, a, b in semanas for v in (a, b)]
    y_min, y_max = min(-15, math.floor(min(ys) / 5) * 5 - 5), max(25, math.ceil(max(ys) / 5) * 5)
    x = lambda i: izq + i * (w - izq - der) / (len(semanas) - 1)
    y = lambda v: arr + (y_max - v) * (h - arr - aba) / (y_max - y_min)
    grilla = "".join(
        f'<line x1="{izq}" x2="{w - der}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="{"cero" if v == 0 else "grilla"}"/>'
        f'<text x="{izq - 10}" y="{y(v) + 4:.1f}" class="eje" text-anchor="end">{v} %</text>'
        for v in range(y_min, y_max + 1, 10)
    )
    ticks, mes_previo, ultimo_tick = [], None, -99.0
    for i, (s, _, _) in enumerate(semanas):
        if s.month != mes_previo:
            mes_previo = s.month
            if ticks and x(i) - ultimo_tick < 30:
                ticks.pop()  # la semana que empieza en el mes anterior no gana etiqueta propia
            ultimo_tick = x(i)
            ticks.append(f'<text x="{x(i):.1f}" y="{h - 10}" class="eje">{MESES[s.month - 1][:3]}</text>')
    trazo = lambda k: "M" + " L".join(f"{x(i):.1f},{y(f[k]):.1f}" for i, f in enumerate(semanas))

    # Anotaciones: primera semana, la semana en que cruza el 0 y la última.
    cruce = next(i for i, (_, a, _) in enumerate(semanas) if a < 0)
    ult = len(semanas) - 1
    notas = ""
    for i, ancla, dx, dy in ((0, "start", 0, -16), (cruce, "start", 12, -12), (ult, "end", 0, 26)):
        s, a, _ = semanas[i]
        texto = f"Cruza el 0 · {s.day} {MESES[s.month - 1][:3]}" if i == cruce else pct(a)
        notas += (f'<circle cx="{x(i):.1f}" cy="{y(a):.1f}" r="5" class="nota-punto"/>'
                  f'<text x="{x(i) + dx:.1f}" y="{y(a) + dy:.1f}" text-anchor="{ancla}" class="nota-texto">{texto}</text>')
    puntos = "".join(
        f'<g class="punto" data-tip="Semana del {s.day} de {MESES[s.month - 1]}: aceite {pct(a)}, resto {pct(b)}">'
        f'<rect x="{x(i) - 8:.1f}" y="{arr}" width="16" height="{h - arr - aba}" class="golpe"/>'
        f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{arr}" y2="{h - aba}" class="guia"/>'
        f'<circle cx="{x(i):.1f}" cy="{y(b):.1f}" r="4" class="p-resto"/><circle cx="{x(i):.1f}" cy="{y(a):.1f}" r="4" class="p-aceite"/></g>'
        for i, (s, a, b) in enumerate(semanas)
    )
    resto = [b for _, _, b in semanas]
    descripcion = (f"Margen semanal del aceite: {pct(semanas[0][1])} la semana del {semanas[0][0].day} de "
                   f"{MESES[semanas[0][0].month - 1]}, bajo cero desde la semana del {semanas[cruce][0].day} de "
                   f"{MESES[semanas[cruce][0].month - 1]} y {pct(semanas[ult][1])} la última semana. "
                   f"El resto de productos se mantiene entre {pct(min(resto))} y {pct(max(resto))}.")
    return f"""<svg viewBox="0 0 {w} {h}" class="linea" role="img" aria-label="{escape(descripcion)}">
  <rect x="{izq}" y="{y(0):.1f}" width="{w - izq - der}" height="{y(y_min) - y(0):.1f}" class="zona-perdida"/>
  <g aria-hidden="true">{grilla}{''.join(ticks)}
  <text x="{w - der - 8}" y="{y(0) + 20:.1f}" class="eje perdida" text-anchor="end">Bajo costo</text></g>
  <path d="{trazo(2)}" class="l-resto" pathLength="1"/>
  <path d="{trazo(1)}" class="l-aceite" pathLength="1"/>
  <g class="notas" aria-hidden="true">{notas}</g>
  <g aria-hidden="true">{puntos}</g>
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
    por_mes = {(n, m): float(p) for n, m, p in con.execute("""
        SELECT nombre, strftime(semana, '%Y-%m'), 100 * sum(margen_usd) / sum(ingreso_usd)
        FROM gold.margen_producto_semana WHERE semana >= DATE '2026-05-01' GROUP BY ALL
    """).fetchall()}
    conciliacion = con.execute("SELECT * FROM gold.conciliacion ORDER BY fuente").fetchall()
    columnas_conc = ["Fuente", "Filas recibidas", "Ventas", "Descartadas", "Cuarentena", "Duplicado exacto",
                     "Duplicado cruzado", "Cuadra"]
    filas_recibidas = sum(f[1] for f in conciliacion)
    todo_cuadra = all(f[-1] for f in conciliacion)

    aceite_primero, aceite_ultimo = por_mes[(ACEITE, meses[0])], por_mes[(ACEITE, meses[-1])]
    resto = [float(p) for n, _, p, _ in productos if n != ACEITE]
    pct_moneda = {m: 100 * float(v) / float(ingreso) for m, v in por_moneda.items()}
    pct_fuente = {f: 100 * float(v) / float(ingreso) for f, v in por_fuente.items()}

    tope = max(abs(float(p)) for _, _, p, _ in productos)
    barras = "".join(
        f'<li tabindex="0" data-tip="{escape(n)}: margen {pct(p)} sobre {usd(i)}'
        f'{f", {b} ventas bajo costo" if b else ""}" class="{"alerta" if b else ""}">'
        f'<span class="nombre">{escape(n)}</span>'
        f'<span class="pista"><span class="barra" style="--w:{abs(float(p)) / tope * 100:.1f}%"></span></span>'
        f'<b>{pct(p)}</b>'
        f'<small>{usd(i)}{f" · <em>{b} ventas bajo costo</em>" if b else ""}</small></li>'
        for n, i, p, b in productos
    )

    def celda(p):
        if p is None:
            return '<td>–</td>'
        if p < 0:
            return f'<td class="neg"><span aria-hidden="true">▼ </span>{pct(p)}</td>'
        return f'<td class="{"bajo" if p < 10 else ""}">{pct(p)}</td>'

    calor = "".join(
        f'<tr><th scope="row">{escape(n)}</th>{"".join(celda(por_mes.get((n, m))) for m in meses)}</tr>'
        for n, *_ in productos
    )
    conc = "".join(
        f'<tr><th scope="row">{FUENTES[f[0]]}</th>'
        + "".join(f"<td>{entero(v)}</td>" for v in f[1:-1])
        + f'<td>{"Sí" if f[-1] else "<b class=\"no\">No</b>"}</td></tr>'
        for f in conciliacion
    )
    encabezado_meses = "".join(f'<th scope="col">{MESES[int(m[5:]) - 1][:3]}</th>' for m in meses)

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>La Ceiba · Margen real</title>
<style>
:root {{
  --fondo:#f5f5f7; --tarjeta:#ffffff; --tinta:#1d1d1f; --tinta-2:#6e6e73; --separador:rgba(0,0,0,.08);
  --acento:#0066cc; --senal:#bf4a12; --critico:#c4321f; --critico-fondo:#fdecea; --aviso-fondo:#fff4d6; --bien:#1a7f37;
  --material:rgba(245,245,247,.72); --sombra:0 1px 2px rgba(0,0,0,.04), 0 4px 16px rgba(0,0,0,.04);
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100;
}}
@media (prefers-color-scheme: dark) {{
  :root:where(:not([data-theme="light"])) {{
    --fondo:#000000; --tarjeta:#1c1c1e; --tinta:#f5f5f7; --tinta-2:#a1a1a6; --separador:rgba(255,255,255,.10);
    --acento:#4da3ff; --senal:#f08a4b; --critico:#ff6b5e; --critico-fondo:#3a1c1a; --aviso-fondo:#3a2f12; --bien:#3fb950;
    --material:rgba(22,22,23,.72); --sombra:none;
    --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
  }}
}}
:root[data-theme="dark"] {{
  --fondo:#000000; --tarjeta:#1c1c1e; --tinta:#f5f5f7; --tinta-2:#a1a1a6; --separador:rgba(255,255,255,.10);
  --acento:#4da3ff; --senal:#f08a4b; --critico:#ff6b5e; --critico-fondo:#3a1c1a; --aviso-fondo:#3a2f12; --bien:#3fb950;
  --material:rgba(22,22,23,.72); --sombra:none;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
}}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:smooth; scroll-padding-top:72px; -webkit-text-size-adjust:100%; }}
body {{ margin:0; background:var(--fondo); color:var(--tinta);
  font:400 1.0625rem/1.47 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", system-ui, sans-serif;
  -webkit-font-smoothing:antialiased; letter-spacing:-.01em; }}
.oculto {{ position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); }}
:focus-visible {{ outline:3px solid var(--acento); outline-offset:3px; border-radius:6px; }}

/* Capa funcional: barra flotante translúcida; el contenido pasa por debajo. */
.navegacion {{ position:sticky; top:0; z-index:5; background:var(--material); border-bottom:1px solid var(--separador);
  backdrop-filter:saturate(180%) blur(20px); -webkit-backdrop-filter:saturate(180%) blur(20px); }}
.navegacion > div {{ max-width:1080px; margin:0 auto; padding:10px 16px; display:flex; align-items:center; gap:16px; }}
.marca {{ font-weight:600; font-size:1.0625rem; margin-right:auto; white-space:nowrap; }}
.segmentos {{ display:flex; gap:2px; padding:2px; border-radius:9px; background:var(--separador); overflow-x:auto; scrollbar-width:none; }}
.segmentos a {{ color:var(--tinta); text-decoration:none; font-size:.8125rem; font-weight:500; padding:6px 12px; border-radius:7px; white-space:nowrap; min-height:28px; transition:background .2s; }}
.segmentos a[aria-current="true"] {{ background:var(--tarjeta); box-shadow:0 1px 3px rgba(0,0,0,.12); }}
@media (prefers-reduced-transparency: reduce) {{ .navegacion {{ background:var(--fondo); backdrop-filter:none; -webkit-backdrop-filter:none; }} }}

main {{ max-width:1080px; margin:0 auto; padding:0 16px 64px; }}
section {{ padding-top:56px; }}
.cabecera {{ padding:48px 0 8px; }}
.ceja {{ color:var(--senal); font-size:.9375rem; font-weight:600; margin:0 0 8px; }}
h1 {{ font:700 clamp(2rem, 5vw, 3rem)/1.08 -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", system-ui, sans-serif;
  letter-spacing:-.025em; margin:0; max-width:22ch; text-wrap:balance; }}
.cabecera p {{ color:var(--tinta-2); font-size:1.1875rem; max-width:40em; margin:14px 0 0; text-wrap:pretty; }}
h2 {{ font-size:1.75rem; line-height:1.15; letter-spacing:-.02em; margin:0 0 6px; }}
h3 {{ font-size:1.0625rem; margin:0; }}
.intro {{ color:var(--tinta-2); margin:0 0 20px; max-width:44em; }}
.tarjeta {{ background:var(--tarjeta); border-radius:18px; box-shadow:var(--sombra); padding:24px; }}

/* Firma: la historia del aceite. */
.historia {{ margin-top:28px; padding:24px 24px 16px; overflow-x:auto; }}
.historia-cabeza {{ display:flex; flex-wrap:wrap; justify-content:space-between; gap:12px 24px; align-items:flex-end; margin-bottom:8px; }}
.leyenda-linea {{ display:flex; gap:20px; font-size:.8125rem; color:var(--tinta-2); margin:0; padding:0; list-style:none; }}
.leyenda-linea i {{ display:inline-block; width:18px; height:3px; border-radius:2px; vertical-align:middle; margin-right:8px; }}
.linea {{ width:100%; min-width:600px; height:auto; display:block; font-family:inherit; }}
.grilla {{ stroke:var(--separador); }} .cero {{ stroke:var(--tinta-2); stroke-width:1; opacity:.5; }}
.eje {{ fill:var(--tinta-2); font-size:12px; }}
.eje.perdida {{ fill:var(--critico); font-weight:600; }}
.zona-perdida {{ fill:var(--critico-fondo); }}
.l-aceite, .l-resto {{ fill:none; stroke-linejoin:round; stroke-linecap:round; stroke-dasharray:1; stroke-dashoffset:1; }}
.l-aceite {{ stroke:var(--senal); stroke-width:3; }}
.l-resto {{ stroke:var(--tinta-2); stroke-width:2; opacity:.55; }}
.notas {{ opacity:0; }}
.nota-punto {{ fill:var(--senal); stroke:var(--tarjeta); stroke-width:2.5; }}
.nota-texto {{ font-size:13px; font-weight:600; fill:var(--tinta); }}
.listo .l-aceite, .listo .l-resto {{ animation:dibujar 1.2s cubic-bezier(.33,1,.68,1) forwards; }}
.listo .l-resto {{ animation-duration:.9s; }}
.listo .notas {{ animation:aparecer .35s 1.15s forwards; }}
.punto .golpe {{ fill:transparent; }} .punto .guia {{ stroke:var(--tinta-2); opacity:0; }}
.punto circle {{ opacity:0; stroke:var(--tarjeta); stroke-width:2; }}
.p-aceite {{ fill:var(--senal); }} .p-resto {{ fill:var(--tinta-2); }}
.punto:hover circle, .punto:hover .guia {{ opacity:1; }}
.punto:hover .guia {{ opacity:.35; }}

/* Resumen en una sola tarjeta agrupada. */
.cifras {{ display:grid; grid-template-columns:repeat(4, 1fr); margin-top:16px; padding:0; }}
.cifras div {{ padding:20px 24px; border-left:1px solid var(--separador); }}
.cifras div:first-child {{ border-left:0; }}
.cifras dt {{ color:var(--tinta-2); font-size:.8125rem; font-weight:500; }}
.cifras dd {{ margin:4px 0 0; font-size:1.75rem; font-weight:600; letter-spacing:-.02em; line-height:1.15; }}
.cifras dd.critico {{ color:var(--critico); }}
.cifras small {{ display:block; color:var(--tinta-2); font-size:.8125rem; margin-top:2px; }}
@media (max-width:760px) {{
  .cifras {{ grid-template-columns:1fr 1fr; }}
  .cifras div:nth-child(3) {{ border-left:0; }}
  .cifras div:nth-child(n+3) {{ border-top:1px solid var(--separador); }}
}}

.par {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(min(100%, 420px), 1fr)); gap:16px; }}
.resumen {{ color:var(--tinta-2); font-size:.9375rem; margin:4px 0 0; }}
.dona-cuerpo {{ display:flex; align-items:center; gap:24px; flex-wrap:wrap; margin-top:16px; }}
.dona svg {{ width:148px; height:148px; flex:none; }}
.seg {{ fill:none; transition:stroke-dasharray .8s cubic-bezier(.33,1,.68,1), opacity .2s; }}
.leyenda {{ flex:1; min-width:200px; border-collapse:collapse; font-size:.9375rem; }}
.leyenda th, .leyenda td {{ padding:8px 0; border-bottom:1px solid var(--separador); font-weight:400; text-align:left; }}
.leyenda td {{ text-align:right; color:var(--tinta-2); padding-left:12px; white-space:nowrap; }}
.leyenda td b {{ color:var(--tinta); font-weight:600; }}
.leyenda tr:last-child th, .leyenda tr:last-child td {{ border-bottom:0; }}
.leyenda i {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:10px; vertical-align:baseline; }}
.leyenda tr {{ cursor:default; }}

.barras {{ list-style:none; margin:0; padding:8px 24px; }}
.barras li {{ display:grid; grid-template-columns:minmax(120px, 190px) 1fr 72px; gap:2px 16px; align-items:center;
  padding:12px 0; border-bottom:1px solid var(--separador); }}
.barras li:last-child {{ border-bottom:0; }}
.barras small {{ grid-column:2 / 4; color:var(--tinta-2); font-size:.8125rem; }}
.barras em {{ color:var(--critico); font-style:normal; font-weight:600; }}
.barras b {{ text-align:right; font-weight:600; font-variant-numeric:tabular-nums; }}
.barras .alerta b {{ color:var(--critico); }}
.pista {{ height:8px; border-radius:4px; background:var(--separador); overflow:hidden; }}
.barra {{ display:block; height:100%; width:var(--w); background:var(--acento); border-radius:4px; transform-origin:left; }}
.barras .alerta .barra {{ background:var(--critico); }}
.crece .barra {{ transform:scaleX(0); }}
.crece.visible .barra {{ transform:none; transition:transform .7s cubic-bezier(.33,1,.68,1); }}

.tabla {{ margin-top:16px; padding:8px 0; overflow-x:auto; }}
table.datos {{ border-collapse:collapse; width:100%; font-size:.9375rem; font-variant-numeric:tabular-nums; }}
.datos th, .datos td {{ padding:10px 16px; text-align:right; white-space:nowrap; border-bottom:1px solid var(--separador); }}
.datos thead th {{ color:var(--tinta-2); font-weight:500; font-size:.8125rem; }}
.datos th:first-child {{ text-align:left; padding-left:24px; }} .datos td:last-child, .datos th:last-child {{ padding-right:24px; }}
.datos tbody th {{ font-weight:500; }}
.datos tbody tr:last-child th, .datos tbody tr:last-child td {{ border-bottom:0; }}
.datos td.bajo {{ background:var(--aviso-fondo); }}
.datos td.neg {{ background:var(--critico-fondo); color:var(--critico); font-weight:600; }}
.no {{ color:var(--critico); }}

.estado {{ display:flex; gap:16px; align-items:center; }}
.estado-icono {{ flex:none; width:44px; height:44px; border-radius:50%; display:grid; place-items:center; background:var(--bien); color:#fff; font-size:1.25rem; font-weight:700; }}
.estado-icono.mal {{ background:var(--critico); }}
.estado p {{ margin:2px 0 0; color:var(--tinta-2); font-size:.9375rem; }}
footer {{ color:var(--tinta-2); font-size:.8125rem; padding:40px 0 0; border-top:1px solid var(--separador); margin-top:56px; }}

#tip {{ position:fixed; pointer-events:none; z-index:10; background:var(--tinta); color:var(--fondo); font-size:.8125rem;
  font-weight:500; padding:8px 12px; border-radius:10px; opacity:0; transition:opacity .15s; max-width:300px; box-shadow:0 8px 24px rgba(0,0,0,.18); }}
@keyframes dibujar {{ to {{ stroke-dashoffset:0; }} }}
@keyframes aparecer {{ to {{ opacity:1; }} }}
@media (max-width:480px) {{ .marca {{ display:none; }} .segmentos {{ margin:0 auto; }} }}
@media (max-width:560px) {{ .barras li {{ grid-template-columns:1fr 64px; }} .barras .pista {{ grid-column:1 / 3; grid-row:2; }} .barras small {{ grid-column:1 / 3; }} }}
@media (prefers-reduced-motion: reduce) {{
  html {{ scroll-behavior:auto; }}
  *, *::before, *::after {{ animation-duration:0s !important; animation-delay:0s !important; transition-duration:0s !important; }}
  .crece .barra {{ transform:none; }}
}}
</style></head><body>
<nav class="navegacion" aria-label="Secciones"><div>
  <span class="marca">La Ceiba</span>
  <div class="segmentos">
    <a href="#resumen" aria-current="true">Resumen</a><a href="#ingresos">Ingresos</a><a href="#productos">Productos</a><a href="#calidad">Calidad</a>
  </div>
</div></nav>
<main>
<section id="resumen" class="cabecera">
  <p class="ceja">Informe de margen · mayo a octubre de 2026</p>
  <h1>El aceite pasó de ganar {pct(aceite_primero)} en mayo a perder {pct(abs(aceite_ultimo))} en octubre.</h1>
  <p>Su precio en CUP no se reajustó mientras subía la tasa informal. Desde septiembre cada botella se vende por debajo de lo que costó. El resto del catálogo se mantiene entre {pct(min(resto))} y {pct(max(resto))}.</p>

  <figure class="tarjeta historia" id="historia" style="margin-left:0;margin-right:0">
    <div class="historia-cabeza">
      <figcaption><h3>Margen semanal sobre el ingreso</h3></figcaption>
      <ul class="leyenda-linea"><li><i style="background:var(--senal)"></i>Aceite vegetal 1 L</li><li><i style="background:var(--tinta-2);opacity:.55"></i>Resto de productos</li></ul>
    </div>
    {linea_margen(semanas)}
  </figure>

  <dl class="tarjeta cifras">
    <div><dt>Ingreso</dt><dd>{usd(ingreso)}</dd><small>a tasa informal del día</small></div>
    <div><dt>Margen</dt><dd>{usd(margen)}</dd><small>ingreso menos último costo</small></div>
    <div><dt>Margen sobre ingreso</dt><dd>{pct(100 * margen / ingreso)}</dd><small>promedio del catálogo</small></div>
    <div><dt>Ventas bajo costo</dt><dd class="critico">{entero(bajo_costo)}</dd><small>todas de aceite</small></div>
  </dl>
</section>

<section id="ingresos">
  <h2>De dónde entra el dinero</h2>
  <p class="intro">Todo convertido a USD con la tasa del día de cada venta.</p>
  <div class="par">
    {dona([(MONEDAS[m], por_moneda[m]) for m in MONEDAS if m in por_moneda], "Por moneda de cobro",
          f"Más de la mitad entra en pesos: {pct(pct_moneda.get('CUP', 0) + pct_moneda.get('TRANSFERENCIA', 0))} entre efectivo y transferencia.")}
    {dona([(FUENTES[f], por_fuente[f]) for f in FUENTES if f in por_fuente], "Por canal de venta",
          f"El almacén mueve {pct(pct_fuente.get('almacen', 0))}; WhatsApp, {pct(pct_fuente.get('whatsapp', 0))}.")}
  </div>
</section>

<section id="productos">
  <h2>Margen por producto</h2>
  <p class="intro">De peor a mejor margen sobre el ingreso de los seis meses.</p>
  <ul class="tarjeta barras crece">{barras}</ul>
  <div class="tarjeta tabla">
    <table class="datos"><caption class="oculto">Margen por producto y mes</caption>
      <thead><tr><th scope="col">Margen por mes</th>{encabezado_meses}</tr></thead><tbody>{calor}</tbody></table>
  </div>
</section>

<section id="calidad">
  <h2>Calidad del dato</h2>
  <p class="intro">Cada fila recibida en los archivos termina en exactamente un destino.</p>
  <div class="tarjeta estado">
    <span class="estado-icono{'' if todo_cuadra else ' mal'}" aria-hidden="true">{'✓' if todo_cuadra else '!'}</span>
    <div><h3>{'Todo cuadra' if todo_cuadra else 'Hay filas sin destino'}</h3>
    <p>{entero(filas_recibidas)} filas recibidas de tres fuentes, cada una clasificada como venta, descartada, cuarentena o duplicado.</p></div>
  </div>
  <div class="tarjeta tabla">
    <table class="datos"><caption class="oculto">Conciliación por fuente</caption>
      <thead><tr>{''.join(f'<th scope="col">{c}</th>' for c in columnas_conc)}</tr></thead><tbody>{conc}</tbody></table>
  </div>
</section>

<footer>La Ceiba es una empresa ficticia y los datos son sintéticos. Generado desde las tablas gold del pipeline.</footer>
</main>
<div id="tip" role="tooltip"></div>
<script>
// Un único momento orquestado: la línea del aceite se dibuja y aparecen sus tres anotaciones.
requestAnimationFrame(() => document.getElementById("historia").classList.add("listo"));

const alVer = (sel, fn) => {{
  const obs = new IntersectionObserver(es => es.forEach(e => {{ if (e.isIntersecting) {{ fn(e.target); obs.unobserve(e.target); }} }}), {{ threshold: .25 }});
  document.querySelectorAll(sel).forEach(el => obs.observe(el));
}};
alVer(".dona", el => el.querySelectorAll(".seg").forEach(s => s.setAttribute("stroke-dasharray", `${{s.dataset.largo}} ${{s.dataset.circ}}`)));
alVer(".crece", el => el.classList.add("visible"));

// Segmento activo según la sección visible.
const enlaces = [...document.querySelectorAll(".segmentos a")];
const secciones = enlaces.map(a => document.querySelector(a.getAttribute("href")));
const marcar = () => {{
  let actual = 0;
  secciones.forEach((s, i) => {{ if (s.getBoundingClientRect().top < innerHeight * .4) actual = i; }});
  if (innerHeight + scrollY >= document.body.scrollHeight - 4) actual = secciones.length - 1;
  enlaces.forEach((a, i) => a.setAttribute("aria-current", i === actual));
}};
addEventListener("scroll", marcar, {{ passive: true }}); marcar();

const tip = document.getElementById("tip");
const mostrar = (el, x, y) => {{
  tip.textContent = el.dataset.tip; tip.style.opacity = 1;
  tip.style.left = Math.min(x + 14, innerWidth - tip.offsetWidth - 8) + "px"; tip.style.top = (y + 16) + "px";
}};
const ocultar = () => tip.style.opacity = 0;
addEventListener("scroll", ocultar, {{ passive: true }});
document.querySelectorAll("[data-tip]").forEach(el => {{
  el.addEventListener("mousemove", ev => mostrar(el, ev.clientX, ev.clientY));
  el.addEventListener("mouseleave", ocultar);
  el.addEventListener("focus", () => {{ const r = el.getBoundingClientRect(); mostrar(el, r.left, r.bottom - 8); }});
  el.addEventListener("blur", ocultar);
}});
</script>
</body></html>
"""


if __name__ == "__main__":
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "la_ceiba.duckdb"
    salida = RAIZ / "dashboard" / "index.html"
    salida.write_text(construir(duckdb.connect(str(db), read_only=True)), encoding="utf-8")
    print(f"Dashboard en {salida}")
