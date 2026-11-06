# La Ceiba · margen real en varias monedas

**La Ceiba** es una mipyme mayorista ficticia de La Habana que vende alimentos a paladares y cafeterías. Cobra en CUP, por transferencia, en USD y en MLC, y compra al proveedor en USD. El dueño quiere saber **qué productos le dejan ganancia de verdad** cuando todo se convierte a USD con la tasa informal de cada día.

Los pedidos llegan por tres vías que nadie concilia: el punto de venta de la tienda, WhatsApp y el cuaderno (Excel) del almacén. Muchos pedidos de WhatsApp los anota también el almacenero, cada uno escribe los productos a su manera y hay días sin tasa publicada.

> **Hallazgo:** el aceite pasó de 17 % de margen en mayo a **–10 % en octubre**. Su precio en CUP nunca se reajustó mientras la tasa subía, y desde septiembre se vende por debajo del costo (190 ventas).

Todos los datos son **sintéticos**: los genera [`generar/generar_datos.py`](generar/generar_datos.py) con errores puestos a propósito.

## Cómo correrlo

```bash
uv sync
uv run python generar/generar_datos.py   # archivos crudos en data/raw/
uv run python pipeline.py                # bronze → silver → gold + pruebas de calidad
uv run python dashboard.py               # dashboard/index.html
uv run pytest
```

`pipeline.py` termina con código 1 si alguna prueba de calidad falla, así que en CI corta el despliegue.

## Capas

| Capa | Tabla | Grano | Qué hace |
|---|---|---|---|
| bronze | `ventas_pos`, `pedidos_whatsapp`, `salidas_almacen`, `tasas`, `compras` | una fila del archivo | El archivo tal cual, todo como texto, más `_archivo_origen` y `_cargado_en`. |
| silver | `catalogo_productos`, `alias_productos` | un SKU / un alias | Catálogo maestro: todas las formas de escribir un producto apuntan a un SKU. |
| silver | `lineas_clasificadas` | una fila de bronze | Une las tres fuentes, normaliza y le asigna a cada fila **un destino**. |
| silver | `ventas` | una línea de venta real | Solo las ventas válidas y únicas, valoradas en USD con su tasa y su costo. |
| gold | `margen_producto_semana` | producto × semana | Ingreso, costo y margen en USD; líneas vendidas por debajo del costo. |
| gold | `conciliacion` | fuente | Filas de bronze contra destinos en silver: comprueba que cuadra. |

## Reglas (una frase cada una)

1. **Producto:** el nombre se pasa a minúsculas y se le quitan las tildes y los espacios dobles; si no está en `seeds/alias_productos.csv`, la línea va a cuarentena.
2. **Pedido de WhatsApp:** solo cuenta un mensaje con la forma `<cantidad> x <producto> @ <precio> <moneda>`; lo demás es charla y se descarta.
3. **Mensaje reenviado:** el mismo teléfono, a la misma hora y con el mismo texto es un duplicado exacto y cuenta una vez.
4. **WhatsApp y almacén:** un pedido de WhatsApp y una salida de almacén con el mismo cliente, día, producto y cantidad son la misma venta, y se queda el registro del almacén porque confirma la entrega.
5. **Emparejamiento uno a uno:** si hay dos pedidos iguales en WhatsApp y una sola salida en almacén, solo uno se toma como duplicado.
6. **Cantidad y precio:** una cantidad o un precio en cero, negativo o ilegible manda la línea a cuarentena.
7. **Tasa:** se usa la tasa informal del día de la venta y, si ese día no se publicó, la última anterior.
8. **Transferencia:** el CUP por transferencia vale lo mismo que el CUP en efectivo.
9. **MLC:** se pasa a CUP con su tasa y luego a USD con la tasa del dólar.
10. **Costo:** el costo de una venta es el de la última compra de ese producto hecha ese día o antes.

## Pruebas de calidad

Cada archivo de [`sql/calidad/`](sql/calidad) devuelve las filas que rompen una regla; **cero filas significa que pasa** (es el mismo patrón que las *assertions* de Dataform).

| Prueba | Qué protege |
|---|---|
| `ventas_llave_unica` | Que ninguna venta aparezca dos veces en silver. |
| `ventas_con_tasa_y_costo` | Que ninguna venta se quede sin convertir a USD. |
| `tasa_no_vieja` | Que no se use una tasa de hace más de 5 días; si pasa, falta cargar tasas. |
| `montos_positivos` | Que no haya ingresos ni costos en cero o negativos. |
| `conciliacion_cuadra` | Que ninguna fila de bronze se pierda entre capas. |
| `gold_cuadra_con_silver` | Que el total de gold sea exactamente el de silver. |
| `cuarentena_bajo_umbral` | Que, si más del 3 % de una fuente cae en cuarentena, se pare: el archivo viene roto. |

Los tests de [`tests/`](tests) prueban cada regla con archivos de 1 o 2 filas hechos a mano, y además corren el pipeline completo con dos semillas distintas.

## Conciliación (semilla 42)

| fuente | bronze | ventas | descartado | cuarentena | dup. exacto | dup. cruzado |
|---|---:|---:|---:|---:|---:|---:|
| almacen | 680 | 679 | 0 | 1 | 0 | 0 |
| pos | 3775 | 3748 | 0 | 27 | 0 | 0 |
| whatsapp | 850 | 544 | 23 | 1 | 34 | 248 |

## Ramas

- `main`: producción; solo recibe fusiones desde `staging`, y cada una lleva su etiqueta de versión.
- `staging`: pruebas; aquí se fusionan las ramas `feature/*` con `--no-ff`, igual que un merge request.

## Decisiones y límites conocidos

- **DuckDB en lugar de BigQuery** para que corra en cualquier laptop. El SQL usa CTEs, `QUALIFY` y funciones de ventana que existen en los dos. Lo que cambia al migrar es `read_csv` (en BigQuery sería una tabla externa sobre el bucket), `strip_accents` y `regexp_extract` con número de grupo.
- **Dashboard en HTML estático** generado desde gold. En la empresa sería una página de Looker Studio sobre las mismas tablas.
- **Duplicado cruzado:** si el almacén anota el pedido al día siguiente, no se detecta. Se podría ampliar la ventana a ±1 día a cambio de más falsos positivos.
- **Transferencia = efectivo:** en la calle el CUP por transferencia a veces vale menos. Si el negocio lo pide, se añade una tasa propia.

## Cómo usé Claude Code

Lo construí con Claude Code como asistente. Lo que se comprobó contra el dato, en lugar de dar por buena la respuesta:

- **Totales de gold contra silver:** la primera versión no cuadraba por unos centavos. La conversión daba números de punto flotante y, al sumarlos en otro orden, salía otro total. La prueba `gold_cuadra_con_silver` lo detectó, y se corrigió fijando `DECIMAL(14, 2)` en silver.
- **Charla de WhatsApp:** al principio contaba como cuarentena y casi hacía saltar el umbral del 3 %. Se separó como destino `descartado`, porque no es un error del archivo.
- **Cada regla de la lista** tiene un test con un caso mínimo escrito a mano, para no dar por bueno que el pipeline simplemente corra.
