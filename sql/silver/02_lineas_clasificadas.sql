-- Una fila por cada fila de bronze (mismo conteo), con su destino:
-- 'venta', 'descartado' (charla de WhatsApp), 'cuarentena', 'duplicado_exacto' o 'duplicado_cruzado'.
CREATE OR REPLACE TABLE silver.lineas_clasificadas AS
WITH pos AS (
    SELECT 'pos' AS fuente, ticket || '-' || linea AS id_origen, CAST(fecha_hora AS TIMESTAMP) AS fecha_hora,
           'mostrador' AS cliente, producto, cantidad, precio_unitario AS precio, moneda, _archivo_origen
    FROM bronze.ventas_pos
),
whatsapp AS (
    -- Formato de pedido: "<cantidad> x <producto> @ <precio> <moneda>". Lo demás es charla.
    SELECT 'whatsapp' AS fuente, md5(telefono || fecha_hora || mensaje) AS id_origen,
           CAST(fecha_hora AS TIMESTAMP) AS fecha_hora, cliente,
           nullif(regexp_extract(mensaje, '^\s*(\d+)\s*x\s*(.+?)\s*@\s*([\d.]+)\s*(\w+)\s*$', 2), '') AS producto,
           nullif(regexp_extract(mensaje, '^\s*(\d+)\s*x\s*(.+?)\s*@\s*([\d.]+)\s*(\w+)\s*$', 1), '') AS cantidad,
           nullif(regexp_extract(mensaje, '^\s*(\d+)\s*x\s*(.+?)\s*@\s*([\d.]+)\s*(\w+)\s*$', 3), '') AS precio,
           nullif(regexp_extract(mensaje, '^\s*(\d+)\s*x\s*(.+?)\s*@\s*([\d.]+)\s*(\w+)\s*$', 4), '') AS moneda,
           _archivo_origen
    FROM bronze.pedidos_whatsapp
),
almacen AS (
    SELECT 'almacen' AS fuente, vale AS id_origen, CAST(fecha AS TIMESTAMP) AS fecha_hora,
           cliente, producto, cantidad, precio, moneda, _archivo_origen
    FROM bronze.salidas_almacen
),
unidas AS (
    SELECT * FROM pos UNION ALL SELECT * FROM whatsapp UNION ALL SELECT * FROM almacen
),
normalizadas AS (
    SELECT u.fuente || ':' || u.id_origen AS id_venta, u.fuente, u.id_origen, u._archivo_origen,
           CAST(u.fecha_hora AS DATE) AS fecha,
           lower(trim(regexp_replace(strip_accents(u.cliente), '\s+', ' ', 'g'))) AS cliente,
           u.producto AS producto_original, a.sku,
           TRY_CAST(u.cantidad AS INTEGER) AS cantidad,
           TRY_CAST(u.precio AS DECIMAL(12, 2)) AS precio_unitario,
           CASE upper(trim(u.moneda)) WHEN 'TRANSF' THEN 'TRANSFERENCIA' ELSE upper(trim(u.moneda)) END AS moneda
    FROM unidas u
    LEFT JOIN silver.alias_productos a
        ON a.alias = lower(trim(regexp_replace(strip_accents(u.producto), '\s+', ' ', 'g')))
),
con_motivo AS (
    SELECT *,
           CASE
               WHEN producto_original IS NULL THEN 'mensaje_no_es_pedido'
               WHEN sku IS NULL THEN 'producto_sin_mapear'
               WHEN cantidad IS NULL OR cantidad <= 0 THEN 'cantidad_invalida'
               WHEN precio_unitario IS NULL OR precio_unitario <= 0 THEN 'precio_invalido'
               WHEN moneda NOT IN ('CUP', 'TRANSFERENCIA', 'USD', 'MLC') THEN 'moneda_desconocida'
           END AS motivo_cuarentena,
           -- Mensajes reenviados: misma llave de origen.
           ROW_NUMBER() OVER (PARTITION BY id_venta ORDER BY id_venta) AS n_copia
    FROM normalizadas
),
validas_unicas AS (
    SELECT *,
           -- Un pedido de WhatsApp anotado también en almacén: emparejo uno a uno por cliente, día, producto y cantidad.
           ROW_NUMBER() OVER (PARTITION BY fuente, cliente, fecha, sku, cantidad ORDER BY id_origen) AS n_en_fuente,
           SUM(CASE WHEN fuente = 'almacen' THEN 1 ELSE 0 END)
               OVER (PARTITION BY cliente, fecha, sku, cantidad) AS n_en_almacen
    FROM con_motivo
    WHERE motivo_cuarentena IS NULL AND n_copia = 1
)
SELECT c.id_venta, c.fuente, c.id_origen, c._archivo_origen, c.fecha, c.cliente, c.producto_original, c.sku,
       c.cantidad, c.precio_unitario, c.moneda, c.motivo_cuarentena,
       CASE
           WHEN c.motivo_cuarentena = 'mensaje_no_es_pedido' THEN 'descartado'
           WHEN c.motivo_cuarentena IS NOT NULL THEN 'cuarentena'
           WHEN c.n_copia > 1 THEN 'duplicado_exacto'
           WHEN v.fuente = 'whatsapp' AND v.n_en_fuente <= v.n_en_almacen THEN 'duplicado_cruzado'
           ELSE 'venta'
       END AS destino
FROM con_motivo c
LEFT JOIN validas_unicas v ON v.id_venta = c.id_venta AND c.n_copia = 1;
