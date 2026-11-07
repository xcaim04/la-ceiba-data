"""La versión BigQuery (Dataform) compila, es SQL válido de BigQuery y da los mismos números que DuckDB.

No hace falta cuenta de Google: se compila con la CLI de Dataform, se traduce a DuckDB con sqlglot
y se ejecuta sobre el mismo bronze que usa la versión local.
"""

import csv
import datetime
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest
import sqlglot

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "generar"))

from generar_datos import generar  # noqa: E402
from pipeline import ejecutar  # noqa: E402

CLI = RAIZ / "dataform" / "node_modules" / ".bin" / "dataform"


@pytest.fixture(scope="module")
def compilado():
    if not CLI.exists() or not shutil.which("node"):
        pytest.skip("Falta la CLI de Dataform: cd dataform && npm install")
    salida = subprocess.run([str(CLI), "compile", str(RAIZ / "dataform"), "--json"],
                            capture_output=True, text=True, check=True).stdout
    return json.loads(salida)


def a_duckdb(consulta: str) -> str:
    # `proyecto.dataset.tabla` -> `dataset.tabla`: en DuckDB el dataset es el esquema.
    sql = sqlglot.transpile(re.sub(r"`[\w-]+\.(\w+\.\w+)`", r"`\1`", consulta), read="bigquery", write="duckdb")[0]
    # sqlglot no traduce NORMALIZE(x, NFD); quitarle las marcas después es lo mismo que strip_accents.
    return re.sub(r"NORMALIZE\(([^,()]+), NFD\)", r"strip_accents(\1)", sql)


def test_compila_sin_errores_y_es_sql_de_bigquery(compilado):
    assert not compilado.get("graphErrors")
    for accion in compilado["tables"] + compilado["assertions"]:
        sqlglot.parse_one(accion["query"], read="bigquery")


def test_mismas_tablas_y_pruebas_que_duckdb(compilado):
    tablas = {f'{t["target"]["schema"]}.{t["target"]["name"]}' for t in compilado["tables"]}
    locales = {f"{capa}.{n}" for capa in ("silver", "gold") for archivo in (RAIZ / "sql" / capa).glob("*.sql")
               for n in re.findall(rf"CREATE OR REPLACE TABLE {capa}\.(\w+)", archivo.read_text())}
    assert tablas == locales
    pruebas = {a["target"]["name"] for a in compilado["assertions"]}
    assert pruebas == {f.stem for f in (RAIZ / "sql" / "calidad").glob("*.sql")}


def test_da_los_mismos_numeros_que_duckdb(compilado, tmp_path):
    generar(tmp_path)
    ejecutar(tmp_path, tmp_path / "local.duckdb").close()
    con = duckdb.connect()
    con.execute(f"ATTACH '{tmp_path / 'local.duckdb'}' AS local (READ_ONLY)")
    for capa in ("bronze", "silver", "gold"):
        con.execute(f"CREATE SCHEMA {capa}")
    for (tabla,) in con.execute("SELECT table_name FROM information_schema.tables "
                                "WHERE table_catalog = 'local' AND table_schema = 'bronze'").fetchall():
        con.execute(f"CREATE TABLE bronze.{tabla} AS SELECT * FROM local.bronze.{tabla}")
    for tabla, semilla in (("maestro_productos", "catalogo_productos"), ("maestro_alias", "alias_productos")):
        con.execute(f"CREATE TABLE bronze.{tabla} AS SELECT * FROM read_csv('{RAIZ / 'seeds' / semilla}.csv', all_varchar = true)")

    # Cada tabla se crea cuando ya existen las que lee.
    pendientes = {f'{t["target"]["schema"]}.{t["target"]["name"]}': t for t in compilado["tables"]}
    while pendientes:
        listas = [n for n, t in pendientes.items()
                  if all(f'{d["schema"]}.{d["name"]}' not in pendientes for d in t.get("dependencyTargets", []))]
        assert listas, "dependencias circulares"
        for nombre in listas:
            con.execute(f"CREATE TABLE {nombre} AS {a_duckdb(pendientes.pop(nombre)['query'])}")

    def filas(consulta):
        # En DuckDB, DATE_TRUNC devuelve un timestamp; en BigQuery, una fecha.
        return [tuple(v.date() if isinstance(v, datetime.datetime) else v for v in f)
                for f in con.execute(consulta).fetchall()]

    for tabla in ("margen_producto_semana", "conciliacion", "ingreso_por_canal"):
        assert filas(f"SELECT * FROM gold.{tabla} ORDER BY ALL") == filas(f"SELECT * FROM local.gold.{tabla} ORDER BY ALL")
    for prueba in compilado["assertions"]:
        assert con.execute(a_duckdb(prueba["query"])).fetchall() == [], prueba["target"]["name"]


def test_el_cargador_junta_cada_fuente_y_anota_su_archivo(tmp_path):
    import cargar_bigquery
    from app import datos

    generar(tmp_path / "raw")
    datos.preparar(tmp_path)
    archivos = cargar_bigquery.preparar_archivos(tmp_path, tmp_path)
    assert set(archivos) == set(cargar_bigquery.TABLAS)
    with archivos["ventas_pos"].open(encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    meses = sorted((tmp_path / "raw").glob("ventas_pos_*.csv"))
    assert len(filas) == sum(len(m.read_text(encoding="utf-8").splitlines()) - 1 for m in meses)
    assert {f["_archivo_origen"] for f in filas} == {m.name for m in meses}

    con_bucket = cargar_bigquery.comandos("p", archivos, bucket="b")
    assert ["gcloud", "storage", "cp", str(archivos["tasas"]), "gs://b/bronze/tasas.csv", "--project=p"] in con_bucket
    assert all("gs://" not in " ".join(c) for c in cargar_bigquery.comandos("p", archivos))
