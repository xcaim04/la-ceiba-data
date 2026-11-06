-- Catálogo maestro: un SKU por producto y todas las formas en que la gente lo escribe.
CREATE OR REPLACE TABLE silver.catalogo_productos AS
SELECT sku, nombre, unidad FROM read_csv('{{seeds}}/catalogo_productos.csv', all_varchar = true);

CREATE OR REPLACE TABLE silver.alias_productos AS
SELECT alias, sku FROM read_csv('{{seeds}}/alias_productos.csv', all_varchar = true);

-- Tasas y costos tipados; una fila por fecha y moneda / por fecha y SKU.
CREATE OR REPLACE TABLE silver.tasas AS
SELECT CAST(fecha AS DATE) AS fecha, upper(trim(moneda)) AS moneda, CAST(cup_por_unidad AS DECIMAL(12, 2)) AS cup_por_unidad
FROM bronze.tasas;

CREATE OR REPLACE TABLE silver.costos AS
SELECT CAST(fecha AS DATE) AS fecha, sku, CAST(costo_unitario_usd AS DECIMAL(12, 2)) AS costo_unitario_usd
FROM bronze.compras;
