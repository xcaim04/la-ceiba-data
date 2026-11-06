"""Corre el pipeline completo: bronze -> silver -> gold -> pruebas de calidad.

Uso: uv run python pipeline.py [carpeta_raw] [archivo.duckdb]
Sale con código 1 si alguna prueba de calidad falla.
"""

import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).parent
CAPAS = ("bronze", "silver", "gold")


def ejecutar(raw: Path, db: Path | str = ":memory:", seeds: Path = RAIZ / "seeds") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(db))
    for capa in CAPAS:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {capa}")
        for archivo in sorted((RAIZ / "sql" / capa).glob("*.sql")):
            con.execute(archivo.read_text().replace("{{raw}}", str(raw)).replace("{{seeds}}", str(seeds)))
    return con


def pruebas_calidad(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Cada archivo de sql/calidad devuelve las filas que rompen la regla: 0 filas = pasa."""
    return {
        archivo.stem: len(con.execute(archivo.read_text()).fetchall())
        for archivo in sorted((RAIZ / "sql" / "calidad").glob("*.sql"))
    }


if __name__ == "__main__":
    raw = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "data" / "raw"
    db = Path(sys.argv[2]) if len(sys.argv) > 2 else RAIZ / "la_ceiba.duckdb"
    con = ejecutar(raw, db)
    fallos = 0
    for prueba, filas in pruebas_calidad(con).items():
        print(f"{'OK   ' if filas == 0 else 'FALLA'} {prueba} ({filas} filas)")
        fallos += filas > 0
    print(con.sql("SELECT * FROM gold.conciliacion ORDER BY fuente"))
    sys.exit(1 if fallos else 0)
