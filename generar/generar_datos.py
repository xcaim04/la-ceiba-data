"""Genera los archivos crudos (sintéticos) de La Ceiba, una mipyme mayorista ficticia.

Los errores son a propósito: nombres de producto escritos de mil formas, pedidos de
WhatsApp reenviados o anotados también en el almacén, días sin tasa publicada,
cantidades en cero y mensajes que no son pedidos.

Uso: uv run python generar/generar_datos.py [carpeta_salida]
"""

import csv
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

SEMILLA = 42
INICIO_COMPRAS = date(2026, 4, 25)
INICIO_VENTAS = date(2026, 5, 1)
FIN = date(2026, 10, 31)

# sku: (costo base en USD, formas en que lo escriben en caja, WhatsApp y almacén)
PRODUCTOS = {
    "POLLO-10LB": (14.0, ["Pollo caja 10 lb", "pollo 10lb", "CJ POLLO", "Caja de pollo"]),
    "ACEITE-1L": (2.6, ["Aceite vegetal 1 L", "aceite 1L", "Pomo de aceite"]),
    "ARROZ-1KG": (1.2, ["Arroz 1 kg", "arroz 1kg", "ARROZ 1KG"]),
    "FRIJOL-1KG": (1.8, ["Frijol negro 1 kg", "frijoles negros"]),
    "AZUCAR-1KG": (1.1, ["Azúcar 1 kg", "azucar", "AZÚCAR"]),
    "CAFE-250G": (3.0, ["Café molido 250 g", "cafe 250g", "Café  250g"]),
    "LECHE-1KG": (6.5, ["Leche en polvo 1 kg", "leche polvo"]),
    "PASTA-500G": (0.9, ["Espagueti 500 g", "espaguetis"]),
    "PURE-400G": (1.0, ["Puré de tomate 400 g", "pure tomate"]),
    "SALCHICHA-PQ": (2.2, ["Salchichas paquete", "paq salchicha"]),
}
# El aceite nunca se reajusta: su precio en CUP se queda atrás mientras sube la tasa.
SIN_REAJUSTE = {"ACEITE-1L"}
SIN_MAPEAR = "pollo de 10"  # forma que no está en el catálogo maestro

CLIENTES = [
    "Paladar El Patio", "Cafetería La Esquina", "Dulcería Mamá Inés", "Paladar Sabor Criollo",
    "Cafetería 23 y 12", "Mini Súper Los Pinos", "Pizzería Napoli", "Cafetería El Parque",
]
TELEFONOS = {c: f"+53 5{random.Random(c).randint(1000000, 9999999)}" for c in CLIENTES}
MONEDAS_POS = ["CUP"] * 55 + ["TRANSFERENCIA"] * 25 + ["USD"] * 12 + ["MLC"] * 8


def dias(desde, hasta):
    d = desde
    while d <= hasta:
        yield d
        d += timedelta(days=1)


def generar(salida: Path, semilla: int = SEMILLA) -> None:
    rnd = random.Random(semilla)
    salida.mkdir(parents=True, exist_ok=True)

    # Tasa informal: paseo aleatorio con tendencia al alza; ~8 % de días sin publicar.
    tasa_real, tasa = {}, 395.0
    for d in dias(INICIO_COMPRAS, FIN):
        tasa = max(350.0, tasa + rnd.gauss(0.45, 2.5))
        tasa_real[d] = round(tasa)
    filas = []
    for d, t in tasa_real.items():
        if d != INICIO_COMPRAS and rnd.random() < 0.08:
            continue
        filas += [[d.isoformat(), "USD", t], [d.isoformat(), "MLC", round(t * 0.82)]]
    escribir(salida / "tasa_informal_diaria.csv", ["fecha", "moneda", "cup_por_unidad"], filas)

    # Compras semanales al proveedor, en USD.
    filas = []
    for d in dias(INICIO_COMPRAS, FIN):
        if d.weekday() == 4 or d == INICIO_COMPRAS:
            for sku, (costo, _) in PRODUCTOS.items():
                filas.append([d.isoformat(), sku, round(costo * rnd.uniform(0.95, 1.08), 2), rnd.randint(40, 200)])
    escribir(salida / "compras_proveedor.csv", ["fecha", "sku", "costo_unitario_usd", "cantidad"], filas)

    # Precio de lista en CUP: se fija el día 1 de cada mes con un 25 % sobre el costo.
    precio_cup = {}
    for d in dias(INICIO_VENTAS, FIN):
        if d.day == 1:
            for sku, (costo, _) in PRODUCTOS.items():
                if sku in SIN_REAJUSTE and sku in precio_cup:
                    continue
                precio_cup[sku] = int(round(costo * 1.25 * tasa_real[d], -1))
        for sku in PRODUCTOS:
            precio_cup[(sku, d)] = precio_cup[sku]

    def precio_en(sku, d, moneda):
        cup = precio_cup[(sku, d)]
        if moneda == "USD":
            return round(cup / tasa_real[d], 2)
        if moneda == "MLC":
            return round(cup / (tasa_real[d] * 0.82), 2)
        return cup

    def nombre(sku):
        if sku == "POLLO-10LB" and rnd.random() < 0.03:
            return SIN_MAPEAR
        return rnd.choice(PRODUCTOS[sku][1])

    # Punto de venta de la tienda: un archivo por mes.
    pos_por_mes, ticket = {}, 1000
    for d in dias(INICIO_VENTAS, FIN):
        for _ in range(rnd.randint(6, 14)):
            ticket += 1
            moneda = rnd.choice(MONEDAS_POS)
            hora = datetime(d.year, d.month, d.day, rnd.randint(8, 18), rnd.randint(0, 59))
            for linea, sku in enumerate(rnd.sample(list(PRODUCTOS), rnd.randint(1, 3)), 1):
                cantidad = rnd.randint(1, 6) if rnd.random() > 0.004 else rnd.choice([0, -1])
                pos_por_mes.setdefault(d.strftime("%Y-%m"), []).append(
                    [ticket, linea, hora.isoformat(sep=" "), nombre(sku), cantidad, precio_en(sku, d, moneda), moneda]
                )
    for mes, filas in pos_por_mes.items():
        escribir(salida / f"ventas_pos_{mes}.csv",
                 ["ticket", "linea", "fecha_hora", "producto", "cantidad", "precio_unitario", "moneda"], filas)

    # Pedidos por WhatsApp y salidas del almacén.
    whatsapp, almacen, vale = [], [], 5000
    for d in dias(INICIO_VENTAS, FIN):
        for _ in range(rnd.randint(2, 7)):
            cliente = rnd.choice(CLIENTES)
            sku = rnd.choice(list(PRODUCTOS))
            moneda = rnd.choice(["CUP", "TRANSF", "USD"])
            cantidad = rnd.randint(2, 30)
            hora = datetime(d.year, d.month, d.day, rnd.randint(7, 20), rnd.randint(0, 59))
            msg = f"{cantidad} x {nombre(sku)} @ {precio_en(sku, d, 'CUP' if moneda == 'TRANSF' else moneda)} {moneda}"
            fila = [hora.isoformat(sep=" "), TELEFONOS[cliente], cliente, msg]
            whatsapp.append(fila)
            if rnd.random() < 0.03:  # mensaje reenviado
                whatsapp.append(list(fila))
            if rnd.random() < 0.30:  # el almacenero también lo anota
                vale += 1
                almacen.append([vale, d.isoformat(), cliente.upper() + "  ", nombre(sku), cantidad,
                                precio_en(sku, d, "CUP" if moneda == "TRANSF" else moneda),
                                "transferencia" if moneda == "TRANSF" else moneda.lower()])
        if rnd.random() < 0.15:
            cliente = rnd.choice(CLIENTES)
            whatsapp.append([f"{d} 09:{rnd.randint(10, 59)}:00", TELEFONOS[cliente], cliente,
                             rnd.choice(["hola, ¿tienen pollo hoy?", "ok gracias", "¿a qué hora abren?"])])
        for _ in range(rnd.randint(1, 4)):  # ventas que solo pasan por el almacén
            vale += 1
            sku, moneda = rnd.choice(list(PRODUCTOS)), rnd.choice(["cup", "usd"])
            almacen.append([vale, d.isoformat(), rnd.choice(CLIENTES), nombre(sku), rnd.randint(5, 40),
                            precio_en(sku, d, moneda.upper()), moneda])
    escribir(salida / "pedidos_whatsapp.csv", ["fecha_hora", "telefono", "cliente", "mensaje"], whatsapp)
    escribir(salida / "salidas_almacen.csv",
             ["vale", "fecha", "cliente", "producto", "cantidad", "precio", "moneda"], almacen)


def escribir(ruta: Path, encabezado, filas) -> None:
    with ruta.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(encabezado)
        w.writerows(filas)


if __name__ == "__main__":
    generar(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent / "data" / "raw")
