-- Bronze: el archivo tal cual llega, todo como texto, más de dónde y cuándo se cargó.
CREATE OR REPLACE TABLE bronze.ventas_pos AS
SELECT * EXCLUDE (filename), parse_filename(filename) AS _archivo_origen, current_timestamp AS _cargado_en
FROM read_csv('{{raw}}/ventas_pos_*.csv', all_varchar = true, filename = true);
