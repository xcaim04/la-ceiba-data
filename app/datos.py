"""Archivos de la empresa, catálogo maestro y recálculo del pipeline.

Todo cambio sigue el mismo camino: se guarda una copia del archivo anterior, se escribe el nuevo,
se recalcula en una base aparte y, si alguna prueba de calidad falla, se deshace el cambio.
El panel nunca ve una base a medio calcular: la nueva reemplaza a la anterior de un solo golpe.
"""

import csv
import io
import os
import re
import shutil
import threading
import unicodedata
from datetime import datetime
from pathlib import Path

import duckdb

from pipeline import ejecutar, pruebas_calidad

RAIZ = Path(__file__).parent.parent
CARPETA = Path(os.environ.get("LA_CEIBA_DATOS", RAIZ / "data"))
TAMANO_MAXIMO = 5 * 1024 * 1024
_candado = threading.Lock()

# tipo: (nombre del archivo en raw/, columnas exactas, descripción)
TIPOS = {
    "ventas_pos": ("ventas_pos_{mes}.csv", ["ticket", "linea", "fecha_hora", "producto", "cantidad", "precio_unitario", "moneda"],
                   "Ventas de la tienda (POS), un archivo por mes"),
    "pedidos_whatsapp": ("pedidos_whatsapp.csv", ["fecha_hora", "telefono", "cliente", "mensaje"], "Exportación de WhatsApp"),
    "salidas_almacen": ("salidas_almacen.csv", ["vale", "fecha", "cliente", "producto", "cantidad", "precio", "moneda"],
                        "Salidas del almacén"),
    "tasas": ("tasa_informal_diaria.csv", ["fecha", "moneda", "cup_por_unidad"], "Tasa informal diaria"),
    "compras": ("compras_proveedor.csv", ["fecha", "sku", "costo_unitario_usd", "cantidad"], "Compras al proveedor"),
}
COLUMNAS_PRODUCTOS = ["sku", "nombre", "unidad"]
COLUMNAS_ALIAS = ["alias", "sku"]


class ErrorDatos(ValueError):
    """Un archivo o un valor que no se puede aceptar; el mensaje es para mostrarlo tal cual."""


def rutas(carpeta: Path = None) -> dict[str, Path]:
    c = carpeta or CARPETA
    return {"raw": c / "raw", "maestros": c / "maestros", "historial": c / "historial", "base": c / "la_ceiba.duckdb"}


def preparar(carpeta: Path = None) -> None:
    r = rutas(carpeta)
    for clave in ("raw", "maestros", "historial"):
        r[clave].mkdir(parents=True, exist_ok=True)
    for semilla in ("catalogo_productos.csv", "alias_productos.csv"):
        if not (r["maestros"] / semilla).exists():
            shutil.copy(RAIZ / "seeds" / semilla, r["maestros"] / semilla)
    if not r["base"].exists() and any(r["raw"].glob("*.csv")):
        recalcular(carpeta)


def conexion(carpeta: Path = None):
    base = rutas(carpeta)["base"]
    return duckdb.connect(str(base), read_only=True) if base.exists() else None


def recalcular(carpeta: Path = None) -> dict[str, int]:
    """Corre el pipeline en una base nueva; solo reemplaza la vigente si pasan todas las pruebas."""
    r = rutas(carpeta)
    nueva = r["base"].with_name("la_ceiba.nueva.duckdb")
    nueva.unlink(missing_ok=True)
    try:
        con = ejecutar(r["raw"], nueva, r["maestros"])
        fallos = {k: v for k, v in pruebas_calidad(con).items() if v}
        con.close()
    except duckdb.Error as e:
        nueva.unlink(missing_ok=True)
        return {f"error del pipeline: {str(e).splitlines()[0]}": 1}
    if fallos:
        nueva.unlink(missing_ok=True)
        return fallos
    os.replace(nueva, r["base"])
    return {}


def _aplicar(ruta: Path, contenido: bytes, carpeta: Path = None) -> dict[str, int]:
    """Escribe el archivo y recalcula; si falla alguna prueba, deja todo como estaba."""
    with _candado:
        r = rutas(carpeta)
        copia = None
        if ruta.exists():
            copia = r["historial"] / f"{datetime.now():%Y%m%d-%H%M%S-%f}_{ruta.name}"
            shutil.copy2(ruta, copia)
        ruta.write_bytes(contenido)
        fallos = recalcular(carpeta)
        if fallos:
            if copia:
                shutil.copy2(copia, ruta)
            else:
                ruta.unlink()
        return fallos


def leer_csv(contenido: bytes, columnas: list[str]) -> list[dict]:
    if len(contenido) > TAMANO_MAXIMO:
        raise ErrorDatos("El archivo pasa de 5 MB.")
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ErrorDatos("El archivo no está en UTF-8. Guárdalo como «CSV UTF-8» y vuelve a subirlo.")
    lector = csv.DictReader(io.StringIO(texto))
    if lector.fieldnames != columnas:
        raise ErrorDatos(f"Las columnas deben ser exactamente: {', '.join(columnas)}. "
                         f"Llegaron: {', '.join(lector.fieldnames or ['ninguna'])}.")
    filas = list(lector)
    if not filas:
        raise ErrorDatos("El archivo no tiene filas.")
    return filas


def cargar_archivo(tipo: str, contenido: bytes, mes: str = "", carpeta: Path = None) -> tuple[int, dict[str, int]]:
    if tipo not in TIPOS:
        raise ErrorDatos("Tipo de archivo desconocido.")
    plantilla, columnas, _ = TIPOS[tipo]
    if "{mes}" in plantilla and not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", mes):
        raise ErrorDatos("Indica el mes de las ventas (AAAA-MM).")
    filas = leer_csv(contenido, columnas)
    # El nombre lo decide el servidor, nunca el archivo subido.
    ruta = rutas(carpeta)["raw"] / plantilla.format(mes=mes)
    # Excel mezcla finales de línea; se guarda siempre con \n y sin BOM.
    texto = contenido.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    return len(filas), _aplicar(ruta, texto.encode("utf-8"), carpeta)


def normalizar(texto: str) -> str:
    """La misma normalización que silver: minúsculas, sin tildes y sin espacios repetidos."""
    sin_tildes = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin_tildes.lower()).strip()


def _leer_maestro(nombre: str, carpeta: Path = None) -> list[dict]:
    with (rutas(carpeta)["maestros"] / nombre).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _escribir_maestro(nombre: str, columnas: list[str], filas: list[dict], carpeta: Path = None) -> dict[str, int]:
    salida = io.StringIO()
    w = csv.DictWriter(salida, columnas, lineterminator="\n")
    w.writeheader()
    w.writerows(filas)
    return _aplicar(rutas(carpeta)["maestros"] / nombre, salida.getvalue().encode("utf-8"), carpeta)


def productos(carpeta: Path = None) -> list[dict]:
    return _leer_maestro("catalogo_productos.csv", carpeta)


def alias(carpeta: Path = None) -> list[dict]:
    return sorted(_leer_maestro("alias_productos.csv", carpeta), key=lambda a: (a["sku"], a["alias"]))


def guardar_producto(sku: str, nombre: str, unidad: str, carpeta: Path = None) -> dict[str, int]:
    sku, nombre, unidad = sku.strip().upper(), nombre.strip(), unidad.strip().lower()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{1,29}", sku):
        raise ErrorDatos("El SKU solo admite mayúsculas, números y guiones (2 a 30 caracteres).")
    if not 1 <= len(nombre) <= 80 or not 1 <= len(unidad) <= 20:
        raise ErrorDatos("Escribe el nombre (hasta 80 caracteres) y la unidad (hasta 20).")
    filas = [p for p in productos(carpeta) if p["sku"] != sku] + [{"sku": sku, "nombre": nombre, "unidad": unidad}]
    fallos = _escribir_maestro("catalogo_productos.csv", COLUMNAS_PRODUCTOS, sorted(filas, key=lambda p: p["sku"]), carpeta)
    # Su nombre oficial también es una forma válida de escribirlo.
    if not fallos and normalizar(nombre) not in {a["alias"] for a in alias(carpeta)}:
        fallos = guardar_alias(nombre, sku, carpeta)
    return fallos


def guardar_alias(texto: str, sku: str, carpeta: Path = None) -> dict[str, int]:
    forma = normalizar(texto)
    if not 1 <= len(forma) <= 80:
        raise ErrorDatos("Escribe cómo aparece el producto (hasta 80 caracteres).")
    if sku not in {p["sku"] for p in productos(carpeta)}:
        raise ErrorDatos("Ese SKU no está en el catálogo.")
    filas = [a for a in alias(carpeta) if a["alias"] != forma] + [{"alias": forma, "sku": sku}]
    return _escribir_maestro("alias_productos.csv", COLUMNAS_ALIAS, filas, carpeta)


def borrar_alias(texto: str, carpeta: Path = None) -> dict[str, int]:
    filas = [a for a in alias(carpeta) if a["alias"] != texto]
    return _escribir_maestro("alias_productos.csv", COLUMNAS_ALIAS, filas, carpeta)


def sin_mapear(con) -> list[tuple[str, int]]:
    """Formas de escribir productos que mandaron líneas a cuarentena, de la más frecuente a la menos."""
    if con is None:
        return []
    return con.execute("""
        SELECT producto_original, count(*) FROM silver.lineas_clasificadas
        WHERE motivo_cuarentena = 'producto_sin_mapear' GROUP BY 1 ORDER BY 2 DESC, 1
    """).fetchall()


def archivos(carpeta: Path = None) -> list[dict]:
    r = rutas(carpeta)
    return [
        {"nombre": a.name, "kb": max(1, a.stat().st_size // 1024),
         "modificado": datetime.fromtimestamp(a.stat().st_mtime).strftime("%d/%m/%Y %H:%M")}
        for a in sorted(r["raw"].glob("*.csv"))
    ]
