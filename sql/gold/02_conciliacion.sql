-- Por fuente: filas en bronze = ventas + descartados + cuarentena + duplicados. Si no cuadra, algo se perdió.
CREATE OR REPLACE TABLE gold.conciliacion AS
WITH bronze AS (
    SELECT 'pos' AS fuente, count(*) AS filas_bronze FROM bronze.ventas_pos
    UNION ALL SELECT 'whatsapp', count(*) FROM bronze.pedidos_whatsapp
    UNION ALL SELECT 'almacen', count(*) FROM bronze.salidas_almacen
),
silver AS (
    SELECT fuente,
           sum(CASE WHEN destino = 'venta' THEN 1 ELSE 0 END) AS ventas,
           sum(CASE WHEN destino = 'descartado' THEN 1 ELSE 0 END) AS descartado,
           sum(CASE WHEN destino = 'cuarentena' THEN 1 ELSE 0 END) AS cuarentena,
           sum(CASE WHEN destino = 'duplicado_exacto' THEN 1 ELSE 0 END) AS duplicado_exacto,
           sum(CASE WHEN destino = 'duplicado_cruzado' THEN 1 ELSE 0 END) AS duplicado_cruzado
    FROM silver.lineas_clasificadas
    GROUP BY fuente
)
SELECT b.fuente, b.filas_bronze, s.ventas, s.descartado, s.cuarentena, s.duplicado_exacto, s.duplicado_cruzado,
       b.filas_bronze = coalesce(s.ventas + s.descartado + s.cuarentena + s.duplicado_exacto + s.duplicado_cruzado, 0) AS cuadra
FROM bronze b LEFT JOIN silver s USING (fuente);
