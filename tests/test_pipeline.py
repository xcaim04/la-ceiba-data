"""Pruebas de las reglas del pipeline con archivos chiquitos hechos a mano."""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "generar"))

from generar_datos import generar  # noqa: E402
from pipeline import ejecutar, pruebas_calidad  # noqa: E402

TASAS = "fecha,moneda,cup_por_unidad\n2026-05-01,USD,400\n2026-05-01,MLC,320\n2026-05-03,USD,500\n"
COMPRAS = "fecha,sku,costo_unitario_usd,cantidad\n2026-04-30,POLLO-10LB,14,100\n"
POS = "ticket,linea,fecha_hora,producto,cantidad,precio_unitario,moneda\n"
WHATSAPP = "fecha_hora,telefono,cliente,mensaje\n"
ALMACEN = "vale,fecha,cliente,producto,cantidad,precio,moneda\n"


def correr(tmp_path, pos=POS, whatsapp=WHATSAPP, almacen=ALMACEN, tasas=TASAS, compras=COMPRAS):
    archivos = {
        "ventas_pos_2026-05.csv": pos, "pedidos_whatsapp.csv": whatsapp, "salidas_almacen.csv": almacen,
        "tasa_informal_diaria.csv": tasas, "compras_proveedor.csv": compras,
    }
    for nombre, contenido in archivos.items():
        (tmp_path / nombre).write_text(contenido, encoding="utf-8")
    return ejecutar(tmp_path)


def destinos(con):
    return dict(con.execute("SELECT destino, count(*) FROM silver.lineas_clasificadas GROUP BY destino").fetchall())


def test_pedido_de_whatsapp_anotado_en_almacen_cuenta_una_vez(tmp_path):
    con = correr(
        tmp_path,
        whatsapp=WHATSAPP + "2026-05-01 10:00:00,+53 51111111,Paladar El Patio,10 x pollo 10lb @ 7000 CUP\n",
        almacen=ALMACEN + "1,2026-05-01,PALADAR EL PATIO  ,Caja de pollo,10,7000,cup\n",
    )
    assert destinos(con) == {"venta": 1, "duplicado_cruzado": 1}
    assert con.execute("SELECT fuente FROM silver.ventas").fetchall() == [("almacen",)]


def test_dos_pedidos_iguales_y_una_sola_salida_dejan_dos_ventas(tmp_path):
    pedido = ",+53 51111111,Paladar El Patio,10 x pollo 10lb @ 7000 CUP\n"
    con = correr(
        tmp_path,
        whatsapp=WHATSAPP + "2026-05-01 10:00:00" + pedido + "2026-05-01 15:00:00" + pedido,
        almacen=ALMACEN + "1,2026-05-01,Paladar El Patio,pollo 10lb,10,7000,cup\n",
    )
    assert destinos(con) == {"venta": 2, "duplicado_cruzado": 1}


def test_mensaje_reenviado_es_duplicado_exacto(tmp_path):
    fila = "2026-05-01 10:00:00,+53 51111111,Paladar El Patio,2 x CJ POLLO @ 17.5 USD\n"
    con = correr(tmp_path, whatsapp=WHATSAPP + fila + fila)
    assert destinos(con) == {"venta": 1, "duplicado_exacto": 1}


def test_pedidos_sin_telefono_cuentan_cada_uno(tmp_path):
    con = correr(
        tmp_path,
        whatsapp=WHATSAPP + "2026-05-01 10:00:00,,Paladar A,2 x pollo 10lb @ 7000 CUP\n"
                            "2026-05-01 11:00:00,,Cafeteria B,3 x pollo 10lb @ 7000 CUP\n",
    )
    assert destinos(con) == {"venta": 2}
    assert all(filas == 0 for filas in pruebas_calidad(con).values())


def test_charla_se_descarta_y_producto_desconocido_va_a_cuarentena(tmp_path):
    con = correr(
        tmp_path,
        whatsapp=WHATSAPP + "2026-05-01 09:00:00,+53 51111111,Paladar El Patio,hola tienen pollo?\n",
        pos=POS + "1,1,2026-05-01 10:00:00,pollo de 10,1,7000,CUP\n1,2,2026-05-01 10:00:00,pollo 10lb,0,7000,CUP\n",
    )
    motivos = con.execute("SELECT motivo_cuarentena FROM silver.lineas_clasificadas ORDER BY 1").fetchall()
    assert motivos == [("cantidad_invalida",), ("mensaje_no_es_pedido",), ("producto_sin_mapear",)]
    assert destinos(con) == {"descartado": 1, "cuarentena": 2}


def test_dia_sin_tasa_usa_la_ultima_publicada(tmp_path):
    # El 2 de mayo no hay tasa: vale la del 1 (400 CUP/USD).
    con = correr(tmp_path, pos=POS + "1,1,2026-05-02 10:00:00,pollo 10lb,2,8000,CUP\n")
    assert con.execute("SELECT fecha_tasa, ingreso_usd, costo_usd FROM silver.ventas").fetchone() == (
        date(2026, 5, 1), 40, 28)


def test_mlc_se_convierte_con_su_tasa_y_la_del_usd(tmp_path):
    # 1 MLC = 320 CUP y 1 USD = 400 CUP, así que 25 MLC = 20 USD.
    con = correr(tmp_path, pos=POS + "1,1,2026-05-01 10:00:00,pollo 10lb,1,25,MLC\n")
    assert con.execute("SELECT ingreso_usd FROM silver.ventas").fetchone() == (20,)


def test_sin_tasa_anterior_falla_la_prueba_de_calidad(tmp_path):
    con = correr(tmp_path, pos=POS + "1,1,2026-04-30 10:00:00,pollo 10lb,1,7000,CUP\n")
    assert pruebas_calidad(con)["ventas_con_tasa_y_costo"] == 1


def test_transferencia_vale_lo_mismo_que_el_cup(tmp_path):
    con = correr(tmp_path, pos=POS + "1,1,2026-05-01 10:00:00,pollo 10lb,1,8000,transf\n")
    assert con.execute("SELECT moneda, ingreso_usd FROM silver.ventas").fetchone() == ("TRANSFERENCIA", 20)


def test_precio_en_cero_o_ilegible_va_a_cuarentena(tmp_path):
    con = correr(tmp_path, pos=POS + "1,1,2026-05-01 10:00:00,pollo 10lb,1,0,CUP\n"
                                     "1,2,2026-05-01 10:00:00,pollo 10lb,1,siete mil,CUP\n")
    motivos = con.execute("SELECT motivo_cuarentena FROM silver.lineas_clasificadas").fetchall()
    assert motivos == [("precio_invalido",), ("precio_invalido",)]


def test_dos_compras_el_mismo_dia_dan_el_costo_medio(tmp_path):
    # 100 cajas a 10 USD y 300 a 16 USD: (1000 + 4800) / 400 = 14,50 USD por caja.
    compras = "fecha,sku,costo_unitario_usd,cantidad\n2026-05-01,POLLO-10LB,10,100\n2026-05-01,POLLO-10LB,16,300\n"
    con = correr(tmp_path, pos=POS + "1,1,2026-05-01 10:00:00,pollo 10lb,2,8000,CUP\n", compras=compras)
    assert con.execute("SELECT costo_unitario_usd, costo_usd FROM silver.ventas").fetchone() == (14.5, 29)


def test_dos_tasas_el_mismo_dia_paran_la_carga(tmp_path):
    con = correr(tmp_path, tasas=TASAS + "2026-05-01,USD,410\n", pos=POS + "1,1,2026-05-01 10:00:00,pollo 10lb,1,8000,CUP\n")
    assert pruebas_calidad(con)["tasa_unica_por_dia"] == 1


@pytest.mark.parametrize("semilla", [1, 42])
def test_datos_generados_pasan_todas_las_pruebas(tmp_path, semilla):
    generar(tmp_path, semilla)
    assert all(filas == 0 for filas in pruebas_calidad(ejecutar(tmp_path)).values())
