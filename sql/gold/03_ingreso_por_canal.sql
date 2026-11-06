-- Grano: mes, fuente y moneda. Responde: ¿por dónde entra la plata y en qué moneda?
CREATE OR REPLACE TABLE gold.ingreso_por_canal AS
SELECT CAST(date_trunc('month', fecha) AS DATE) AS mes, fuente, moneda,
       count(*) AS lineas,
       sum(ingreso_usd) AS ingreso_usd,
       sum(ingreso_usd) - sum(costo_usd) AS margen_usd
FROM silver.ventas
GROUP BY ALL;
