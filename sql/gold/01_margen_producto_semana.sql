-- Grano: producto y semana (lunes). Responde: ¿qué productos me dejan plata de verdad?
CREATE OR REPLACE TABLE gold.margen_producto_semana AS
SELECT CAST(date_trunc('week', v.fecha) AS DATE) AS semana, v.sku, p.nombre,
       sum(v.cantidad) AS unidades,
       sum(v.ingreso_usd) AS ingreso_usd,
       sum(v.costo_usd) AS costo_usd,
       sum(v.ingreso_usd) - sum(v.costo_usd) AS margen_usd,
       sum(CASE WHEN v.ingreso_usd < v.costo_usd THEN 1 ELSE 0 END) AS lineas_bajo_costo
FROM silver.ventas v
JOIN silver.catalogo_productos p USING (sku)
GROUP BY ALL;
