-- El total de gold es exactamente el de silver.
SELECT g.total AS gold, s.total AS silver
FROM (SELECT sum(ingreso_usd) AS total FROM gold.margen_producto_semana) g,
     (SELECT sum(ingreso_usd) AS total FROM silver.ventas) s
WHERE g.total IS DISTINCT FROM s.total
