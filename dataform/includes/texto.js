// La misma normalización que la versión DuckDB: minúsculas, sin tildes y sin espacios repetidos.
function normalizar(columna) {
  return `LOWER(TRIM(REGEXP_REPLACE(REGEXP_REPLACE(NORMALIZE(${columna}, NFD), r'\\pM', ''), r'\\s+', ' ')))`;
}

// Un pedido de WhatsApp: "<cantidad> x <producto> @ <precio> <moneda>". Devuelve la parte pedida o NULL.
const PARTES = { cantidad: 0, producto: 1, precio: 2, moneda: 3 };
function parte_del_pedido(columna, parte) {
  const grupos = [String.raw`(\d+)`, String.raw`(.+?)`, String.raw`([\d.]+)`, String.raw`(\w+)`]
    .map((g, i) => (i === PARTES[parte] ? g : "(?:" + g.slice(1)));
  const patron = String.raw`^\s*${grupos[0]}\s*x\s*${grupos[1]}\s*@\s*${grupos[2]}\s*${grupos[3]}\s*$`;
  return `NULLIF(REGEXP_EXTRACT(${columna}, r'${patron}'), '')`;
}

module.exports = { normalizar, parte_del_pedido };
