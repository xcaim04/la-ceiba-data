-- Cada línea de venta aparece una sola vez en silver.
SELECT id_venta, count(*) AS veces FROM silver.ventas GROUP BY id_venta HAVING count(*) > 1
