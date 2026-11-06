"""Genera dashboard/index.html a partir de las tablas gold. Sin servidor: se abre en el navegador.

Uso: uv run python dashboard.py [archivo.duckdb]
"""

import sys
from html import escape
from pathlib import Path

import duckdb

RAIZ = Path(__file__).parent


def usd(x) -> str:
    return f"{x:,.0f} USD".replace(",", " ")


def construir(con: duckdb.DuckDBPyConnection) -> str:
    ingreso, margen = con.execute("SELECT sum(ingreso_usd), sum(margen_usd) FROM gold.margen_producto_semana").fetchone()
    productos = con.execute("""
        SELECT nombre, sum(ingreso_usd), 100 * sum(margen_usd) / sum(ingreso_usd), sum(lineas_bajo_costo)
        FROM gold.margen_producto_semana GROUP BY nombre ORDER BY 3
    """).fetchall()
    meses = [m for (m,) in con.execute("""
        SELECT DISTINCT strftime(semana, '%Y-%m') FROM gold.margen_producto_semana WHERE semana >= DATE '2026-05-01' ORDER BY 1
    """).fetchall()]
    por_mes = {(n, m): p for n, m, p in con.execute("""
        SELECT nombre, strftime(semana, '%Y-%m'), 100 * sum(margen_usd) / sum(ingreso_usd)
        FROM gold.margen_producto_semana WHERE semana >= DATE '2026-05-01' GROUP BY ALL
    """).fetchall()}
    conciliacion = con.execute("SELECT * FROM gold.conciliacion ORDER BY fuente").fetchall()
    columnas_conc = [d[0] for d in con.execute("SELECT * FROM gold.conciliacion LIMIT 0").description]

    tope = max(abs(p) for _, _, p, _ in productos)
    barras = "".join(
        f'<div class="fila"><span>{escape(n)}</span><div class="pista"><div class="barra{" neg" if p < 0 else ""}" '
        f'style="width:{abs(p) / tope * 100:.1f}%"></div></div><b>{p:.1f} %</b>'
        f'<small>{usd(i)}{f" · {b} ventas bajo costo" if b else ""}</small></div>'
        for n, i, p, b in productos
    )
    celda = lambda p: "<td>–</td>" if p is None else f'<td class="{"neg" if p < 0 else "bajo" if p < 10 else ""}">{p:.1f}</td>'
    calor = "".join(
        f"<tr><th>{escape(n)}</th>{''.join(celda(por_mes.get((n, m))) for m in meses)}</tr>" for n, *_ in productos
    )
    conc = "".join("<tr>" + "".join(f"<td>{'sí' if v is True else 'NO' if v is False else v}</td>" for v in fila) + "</tr>"
                   for fila in conciliacion)

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>La Ceiba · Margen real</title>
<style>
:root {{ --fondo:#f7f7f4; --tarjeta:#fff; --texto:#1d1d1b; --suave:#6b6b66; --linea:#e3e3de; --verde:#2f7d5b; --rojo:#c2412d; --ambar:#f3e2b8; --rojo-claro:#f6d5cf; }}
@media (prefers-color-scheme: dark) {{ :root {{ --fondo:#161615; --tarjeta:#21211f; --texto:#ededea; --suave:#a3a39d; --linea:#34342f; --verde:#4fae84; --rojo:#e3674f; --ambar:#5a4a1f; --rojo-claro:#5c2a22; }} }}
body {{ margin:0; background:var(--fondo); color:var(--texto); font:15px/1.45 system-ui, sans-serif; }}
main {{ max-width:980px; margin:0 auto; padding:24px 16px 48px; }}
h1 {{ margin:0 0 4px; font-size:24px; }} h2 {{ font-size:17px; margin:0 0 4px; }}
p.nota {{ color:var(--suave); margin:0 0 16px; }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:12px; margin:20px 0; }}
.kpi, section {{ background:var(--tarjeta); border:1px solid var(--linea); border-radius:10px; padding:16px; }}
section {{ margin-bottom:16px; overflow-x:auto; }}
.kpi span {{ color:var(--suave); font-size:13px; }} .kpi b {{ display:block; font-size:24px; font-variant-numeric:tabular-nums; }}
.fila {{ display:grid; grid-template-columns:170px 1fr 64px; gap:4px 10px; align-items:center; margin:8px 0; }}
.fila small {{ grid-column:2 / 4; color:var(--suave); margin-top:-4px; }}
.pista {{ background:var(--linea); border-radius:4px; height:12px; }}
.barra {{ background:var(--verde); height:100%; border-radius:4px; }} .barra.neg {{ background:var(--rojo); }}
.fila b {{ text-align:right; font-variant-numeric:tabular-nums; }}
table {{ border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; font-size:14px; }}
th, td {{ padding:6px 8px; border-bottom:1px solid var(--linea); text-align:right; white-space:nowrap; }}
th:first-child, td:first-child {{ text-align:left; }}
td.bajo {{ background:var(--ambar); }} td.neg {{ background:var(--rojo-claro); color:var(--rojo); font-weight:600; }}
@media (max-width:560px) {{ .fila {{ grid-template-columns:110px 1fr 56px; }} }}
</style></head><body><main>
<h1>La Ceiba · margen real en USD</h1>
<p class="nota">Mayo–octubre 2026. Todo convertido a USD con la tasa informal del día de la venta. Datos sintéticos.</p>
<div class="kpis">
  <div class="kpi"><span>Ingreso</span><b>{usd(ingreso)}</b></div>
  <div class="kpi"><span>Margen</span><b>{usd(margen)}</b></div>
  <div class="kpi"><span>Margen sobre ingreso</span><b>{100 * margen / ingreso:.1f} %</b></div>
</div>
<section><h2>Margen por producto</h2><p class="nota">Ordenado de peor a mejor.</p>{barras}</section>
<section><h2>Margen % por mes</h2><p class="nota">Ámbar: menos de 10 %. Rojo: se vende por debajo del costo.</p>
<table><tr><th>Producto</th>{''.join(f'<th>{m}</th>' for m in meses)}</tr>{calor}</table></section>
<section><h2>Conciliación: ¿cuadra con los archivos?</h2><p class="nota">Cada fila de bronze termina en exactamente un destino.</p>
<table><tr>{''.join(f'<th>{c}</th>' for c in columnas_conc)}</tr>{conc}</table></section>
</main></body></html>
"""


if __name__ == "__main__":
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "la_ceiba.duckdb"
    salida = RAIZ / "dashboard" / "index.html"
    salida.write_text(construir(duckdb.connect(str(db), read_only=True)), encoding="utf-8")
    print(f"Dashboard en {salida}")
