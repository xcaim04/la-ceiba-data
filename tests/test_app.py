"""Pruebas del sitio: acceso privado, CSRF, carga de archivos y catálogo con vuelta atrás."""

import importlib
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "generar"))

from generar_datos import generar  # noqa: E402

CLAVE = "una-clave-larga-de-prueba"


@pytest.fixture(scope="module")
def entorno(tmp_path_factory, monkeypatch_module):
    carpeta = tmp_path_factory.mktemp("datos")
    generar(carpeta / "raw")
    monkeypatch_module.setenv("LA_CEIBA_DATOS", str(carpeta))
    monkeypatch_module.setenv("LA_CEIBA_HTTPS", "0")
    for modulo in ("app.datos", "app.main"):
        sys.modules.pop(modulo, None)
    main = importlib.import_module("app.main")
    from app import datos, seguridad
    seguridad.guardar_admin(carpeta / "admin.json", "admin", CLAVE)
    return main, datos, seguridad, carpeta


@pytest.fixture(scope="module")
def monkeypatch_module():
    with pytest.MonkeyPatch.context() as mp:
        yield mp


@pytest.fixture
def cliente(entorno):
    from fastapi.testclient import TestClient
    return TestClient(entorno[0].app, follow_redirects=False)


def csrf(respuesta) -> str:
    return re.search(r'name="csrf" value="([^"]+)"', respuesta.text).group(1)


def entrar(cliente):
    token = csrf(cliente.get("/entrar"))
    r = cliente.post("/entrar", data={"usuario": "admin", "clave": CLAVE, "csrf": token})
    assert r.headers["location"] == "/panel"
    return csrf(cliente.get("/admin"))


def test_inicio_es_publico_y_no_muestra_datos(cliente):
    r = cliente.get("/")
    assert r.status_code == 200 and "Entrar al panel" in r.text
    assert "Aceite vegetal" not in r.text and "152.905" not in r.text


@pytest.mark.parametrize("ruta", ["/panel", "/admin"])
def test_paginas_privadas_piden_entrar(cliente, ruta):
    r = cliente.get(ruta)
    assert r.status_code == 303 and r.headers["location"] == "/entrar"


def test_post_sin_sesion_no_cambia_nada(cliente, entorno):
    datos = entorno[1]
    antes = datos.alias()
    r = cliente.post("/admin/alias", data={"alias": "lo que sea", "sku": "ARROZ-1KG", "csrf": "x"})
    assert r.status_code == 303 and datos.alias() == antes


def test_entrar_y_ver_el_panel(cliente):
    entrar(cliente)
    r = cliente.get("/panel")
    assert r.status_code == 200 and "Aceite vegetal 1 L" in r.text and ">Salir<" in r.text
    assert r.headers["cache-control"] == "no-store"


def test_post_con_csrf_falso_se_rechaza(cliente):
    entrar(cliente)
    assert cliente.post("/admin/alias", data={"alias": "x", "sku": "ARROZ-1KG", "csrf": "falso"}).status_code == 403


def test_asignar_forma_saca_las_ventas_de_cuarentena(cliente, entorno):
    datos = entorno[1]
    token = entrar(cliente)
    with datos.conexion() as con:
        assert ("pollo de 10", 18) in datos.sin_mapear(con)
        ventas_antes = con.execute("SELECT count(*) FROM silver.ventas").fetchone()[0]
    cliente.post("/admin/alias", data={"alias": "Pollo  de 10", "sku": "POLLO-10LB", "csrf": token})
    with datos.conexion() as con:
        assert datos.sin_mapear(con) == []
        assert con.execute("SELECT count(*) FROM silver.ventas").fetchone()[0] == ventas_antes + 18


def test_columnas_equivocadas_no_cambian_nada(cliente, entorno):
    carpeta = entorno[3]
    token = entrar(cliente)
    antes = (carpeta / "raw" / "tasa_informal_diaria.csv").read_bytes()
    cliente.post("/admin/cargar", data={"tipo": "tasas", "csrf": token},
                 files={"archivo": ("t.csv", b"dia,valor\n2026-05-01,400\n", "text/csv")})
    assert "Las columnas deben ser" in cliente.get("/admin").text
    assert (carpeta / "raw" / "tasa_informal_diaria.csv").read_bytes() == antes


def test_carga_que_rompe_la_calidad_se_deshace(cliente, entorno):
    carpeta = entorno[3]
    token = entrar(cliente)
    antes = (carpeta / "raw" / "tasa_informal_diaria.csv").read_bytes()
    # Solo tasas de octubre: las ventas de mayo a septiembre se quedarían sin convertir.
    malo = b"fecha,moneda,cup_por_unidad\n2026-10-01,USD,470\n2026-10-01,MLC,385\n"
    cliente.post("/admin/cargar", data={"tipo": "tasas", "csrf": token}, files={"archivo": ("t.csv", malo, "text/csv")})
    pagina = cliente.get("/admin").text
    assert "No se aplicó el cambio" in pagina and "ventas_con_tasa_y_costo" in pagina
    assert (carpeta / "raw" / "tasa_informal_diaria.csv").read_bytes() == antes


def test_carga_valida_reemplaza_y_guarda_el_anterior(cliente, entorno):
    carpeta = entorno[3]
    token = entrar(cliente)
    ruta = carpeta / "raw" / "tasa_informal_diaria.csv"
    nuevo = ruta.read_bytes() + b"2026-11-01,USD,480\n2026-11-01,MLC,394\n"
    cliente.post("/admin/cargar", data={"tipo": "tasas", "csrf": token}, files={"archivo": ("t.csv", nuevo, "text/csv")})
    pagina = cliente.get("/admin").text
    assert "Archivo cargado" in pagina, re.search(r"aviso [^>]*>(.{0,400})", pagina, re.S).group(1)
    assert ruta.read_bytes() == nuevo.replace(b"\r\n", b"\n")
    assert any(carpeta.glob("historial/*_tasa_informal_diaria.csv"))
    assert {p.stem for p in carpeta.glob("gold/*.parquet")} == {"margen_producto_semana", "conciliacion", "ingreso_por_canal"}


def test_usuario_y_csrf_con_tildes_no_rompen_la_entrada(cliente, entorno):
    seguridad, carpeta = entorno[2], entorno[3]
    admin = carpeta / "admin_jose.json"
    seguridad.guardar_admin(admin, "José Peña", CLAVE)
    assert seguridad.verificar(admin, "José Peña", CLAVE)
    assert not seguridad.verificar(admin, "Jose Pena", CLAVE)
    r = cliente.post("/entrar", data={"usuario": "ñandú", "clave": "x", "csrf": "ñ"})
    assert r.status_code == 200 and "caducó" in r.text
    token = csrf(cliente.get("/entrar"))
    r = cliente.post("/entrar", data={"usuario": "ñandú", "clave": "mala", "csrf": token})
    assert r.status_code == 200 and "incorrectos" in r.text
    seguridad.limpiar_fallos("testclient")


def test_demasiados_intentos_bloquean_el_acceso(cliente, entorno):
    seguridad = entorno[2]
    for _ in range(seguridad.INTENTOS_MAXIMOS):
        token = csrf(cliente.get("/entrar"))
        assert "incorrectos" in cliente.post("/entrar", data={"usuario": "admin", "clave": "mala", "csrf": token}).text
    token = csrf(cliente.get("/entrar"))
    r = cliente.post("/entrar", data={"usuario": "admin", "clave": CLAVE, "csrf": token})
    assert "Demasiados intentos" in r.text
    seguridad.limpiar_fallos("testclient")
