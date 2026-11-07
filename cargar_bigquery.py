"""Carga los archivos crudos a la capa bronze de BigQuery, tal cual llegan y todo como texto.

Uso: uv run python cargar_bigquery.py --proyecto <id> [--bucket <nombre>] [--mostrar]

Con --bucket, cada archivo sube primero a gs://<bucket>/bronze/ y BigQuery lo carga desde ahí: es el camino
de producción. Sin --bucket, se carga desde este equipo, que es lo que permite el sandbox gratis (no tiene
Cloud Storage). Necesita gcloud y bq con la sesión iniciada; --mostrar solo imprime los comandos.
Después: cd dataform && npx dataform run . (o desde la consola de Dataform).
"""

import argparse
import csv
import shlex
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.datos import CARPETA, COLUMNAS_ALIAS, COLUMNAS_PRODUCTOS, TIPOS, rutas

# tabla de bronze: (carpeta dentro de los datos, patrón de archivo, columnas)
TABLAS = {tipo: ("raw", plantilla.format(mes="*"), columnas) for tipo, (plantilla, columnas, _) in TIPOS.items()} | {
    "maestro_productos": ("maestros", "catalogo_productos.csv", COLUMNAS_PRODUCTOS),
    "maestro_alias": ("maestros", "alias_productos.csv", COLUMNAS_ALIAS),
}


def preparar_archivos(carpeta: Path, destino: Path) -> dict[str, Path]:
    """Un CSV por tabla, con todas sus filas y dos columnas más: de qué archivo vino y cuándo se cargó."""
    r = rutas(carpeta)
    cargado_en = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00:00")
    salida = {}
    for tabla, (subcarpeta, patron, columnas) in TABLAS.items():
        archivos = sorted(r[subcarpeta].glob(patron))
        if not archivos:
            raise SystemExit(f"No hay archivos {patron} en {r[subcarpeta]}")
        salida[tabla] = destino / f"{tabla}.csv"
        with salida[tabla].open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(columnas + ["_archivo_origen", "_cargado_en"])
            for archivo in archivos:
                with archivo.open(encoding="utf-8-sig", newline="") as origen:
                    for fila in csv.DictReader(origen):
                        w.writerow([fila[c] for c in columnas] + [archivo.name, cargado_en])
    return salida


def comandos(proyecto: str, archivos: dict[str, Path], bucket: str = "", ubicacion: str = "US") -> list[list[str]]:
    bq = ["bq", f"--project_id={proyecto}", f"--location={ubicacion}"]
    lista = [bq + ["mk", "--force", "--dataset", f"{proyecto}:bronze"]]
    for tabla, archivo in archivos.items():
        origen = str(archivo)
        if bucket:
            origen = f"gs://{bucket}/bronze/{archivo.name}"
            lista.append(["gcloud", "storage", "cp", str(archivo), origen, f"--project={proyecto}"])
        esquema = ",".join(f"{c}:STRING" for c in TABLAS[tabla][2]) + ",_archivo_origen:STRING,_cargado_en:TIMESTAMP"
        lista.append(bq + ["load", "--replace", "--source_format=CSV", "--skip_leading_rows=1",
                           "--allow_quoted_newlines", f"{proyecto}:bronze.{tabla}", origen, esquema])
    return lista


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--proyecto", required=True, help="ID del proyecto de Google Cloud")
    p.add_argument("--bucket", default="", help="bucket de Cloud Storage; sin él, se carga desde este equipo")
    p.add_argument("--ubicacion", default="US")
    p.add_argument("--datos", type=Path, default=CARPETA, help="carpeta con raw/ y maestros/")
    p.add_argument("--mostrar", action="store_true", help="solo imprimir los comandos")
    args = p.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        for comando in comandos(args.proyecto, preparar_archivos(args.datos, Path(tmp)), args.bucket, args.ubicacion):
            print("$", shlex.join(comando))
            if not args.mostrar:
                subprocess.run(comando, check=True)
