-- Ingresos y costos siempre mayores que cero.
SELECT id_venta, ingreso_usd, costo_usd FROM silver.ventas WHERE ingreso_usd <= 0 OR costo_usd <= 0
