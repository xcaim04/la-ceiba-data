// Bronze: cargar_bigquery.py carga cada archivo tal cual, todo como texto, con _archivo_origen y _cargado_en.
[
  "ventas_pos", "pedidos_whatsapp", "salidas_almacen", "tasas", "compras",
  "maestro_productos", "maestro_alias",
].forEach((name) => declare({ schema: "bronze", name }));
