-- El ingreso por canal suma lo mismo que silver.
SELECT g.total AS gold, s.total AS silver
FROM (SELECT sum(ingreso_usd) AS total FROM gold.ingreso_por_canal) g,
     (SELECT sum(ingreso_usd) AS total FROM silver.ventas) s
WHERE g.total IS DISTINCT FROM s.total
