---
title: La Ceiba · margen real en USD
---

```sql totales
SELECT sum(ingreso_usd) AS ingreso, sum(margen_usd) AS margen,
       sum(margen_usd) / sum(ingreso_usd) AS margen_pct, sum(lineas_bajo_costo) AS ventas_bajo_costo
FROM la_ceiba.margen_producto_semana
```

```sql aceite
SELECT strftime(date_trunc('month', semana), '%Y-%m') AS mes, sum(margen_usd) / sum(ingreso_usd) AS margen_pct
FROM la_ceiba.margen_producto_semana
-- Como el panel del sitio: cada semana cuenta en el mes en que empieza, desde mayo.
WHERE sku = 'ACEITE-1L' AND semana >= DATE '2026-05-01'
GROUP BY 1 ORDER BY 1
```

Todo el ingreso convertido a USD con la tasa informal del día de cada venta. El aceite pasó de un margen de <Value data={aceite} column=margen_pct row=0 fmt=pct1 /> en <Value data={aceite} column=mes row=0 /> a <Value data={aceite} column=margen_pct row={aceite.length - 1} fmt=pct1 /> en <Value data={aceite} column=mes row={aceite.length - 1} />: su precio en CUP no se reajustó mientras la tasa subía.

<Grid cols=4>
  <BigValue data={totales} value=ingreso title="Ingreso" fmt=usd0 />
  <BigValue data={totales} value=margen title="Margen" fmt=usd0 />
  <BigValue data={totales} value=margen_pct title="Margen sobre ingreso" fmt=pct1 />
  <BigValue data={totales} value=ventas_bajo_costo title="Ventas por debajo del costo" />
</Grid>

## El aceite contra el resto

```sql margen_mensual
SELECT date_trunc('month', semana) AS mes,
       CASE WHEN sku = 'ACEITE-1L' THEN 'Aceite' ELSE 'Resto de productos' END AS grupo,
       sum(margen_usd) / sum(ingreso_usd) AS margen_pct
FROM la_ceiba.margen_producto_semana
WHERE semana >= DATE '2026-05-01'
GROUP BY ALL ORDER BY mes, grupo
```

<!-- Los mismos tonos que el panel del sitio: el aceite en naranja, el resto en gris. -->
<LineChart data={margen_mensual} x=mes y=margen_pct series=grupo yFmt=pct0 xFmt=mmm
           title="Margen mensual sobre el ingreso" markers=true colorPalette={['#d9601f', '#8e8e93']} />

## Por dónde entra la plata

```sql por_moneda
SELECT mes, moneda, sum(ingreso_usd) AS ingreso_usd FROM la_ceiba.ingreso_por_canal GROUP BY ALL ORDER BY 1
```

```sql por_canal
SELECT mes, fuente, sum(ingreso_usd) AS ingreso_usd FROM la_ceiba.ingreso_por_canal GROUP BY ALL ORDER BY 1
```

<BarChart data={por_moneda} x=mes y=ingreso_usd series=moneda yFmt=usd0 xFmt=mmm title="Ingreso por moneda de cobro" />

<BarChart data={por_canal} x=mes y=ingreso_usd series=fuente yFmt=usd0 xFmt=mmm title="Ingreso por canal de venta" />

## Margen por producto

```sql productos
SELECT nombre, sum(ingreso_usd) AS ingreso_usd, sum(margen_usd) / sum(ingreso_usd) AS margen_pct,
       sum(lineas_bajo_costo) AS ventas_bajo_costo
FROM la_ceiba.margen_producto_semana
GROUP BY nombre ORDER BY margen_pct
```

<BarChart data={productos} x=nombre y=margen_pct swapXY=true yFmt=pct1 title="Margen de mayo a octubre" />

<DataTable data={productos}>
  <Column id=nombre title="Producto" />
  <Column id=ingreso_usd title="Ingreso" fmt=usd0 />
  <Column id=margen_pct title="Margen" fmt=pct1 />
  <Column id=ventas_bajo_costo title="Ventas bajo costo" />
</DataTable>

## ¿Cuadra?

Cada fila que llegó en los archivos termina en un solo destino. Si la suma no da las filas de bronze, algo se perdió.

```sql conciliacion
SELECT * FROM la_ceiba.conciliacion ORDER BY fuente
```

<DataTable data={conciliacion}>
  <Column id=fuente title="Fuente" />
  <Column id=filas_bronze title="Filas en bronze" />
  <Column id=ventas title="Ventas" />
  <Column id=descartado title="Descartado" />
  <Column id=cuarentena title="Cuarentena" />
  <Column id=duplicado_exacto title="Dup. exacto" />
  <Column id=duplicado_cruzado title="Dup. cruzado" />
  <Column id=cuadra title="Cuadra" />
</DataTable>
