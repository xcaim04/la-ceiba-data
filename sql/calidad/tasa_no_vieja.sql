-- La tasa usada no puede tener más de 5 días: si pasa, falta cargar tasas.
SELECT id_venta, fecha, fecha_tasa FROM silver.ventas WHERE fecha - fecha_tasa > 5
