-- Una sola tasa por día y moneda: si el archivo trae dos, no se sabe cuál usar.
SELECT fecha, moneda, count(*) AS veces FROM silver.tasas GROUP BY fecha, moneda HAVING count(*) > 1
