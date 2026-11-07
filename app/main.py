"""Sitio de La Ceiba: presentación pública, panel privado y administración de datos.

Uso: uv run uvicorn app.main:app --port 8000
Antes, una vez: uv run python -m app.crear_admin <usuario>
"""

import os
from pathlib import Path

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import dashboard
from app import datos, seguridad

RAIZ = Path(__file__).parent.parent
CARPETA = datos.CARPETA
plantillas = Jinja2Templates(directory=Path(__file__).parent / "plantillas")
# La versión de la hoja de estilos cambia con el archivo, así el navegador no usa una copia vieja.
plantillas.env.globals["version_css"] = int((RAIZ / "diseno" / "base.css").stat().st_mtime)

datos.preparar()
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=seguridad.secreto_de_sesion(CARPETA / ".secreto"),
    session_cookie="la_ceiba",
    max_age=8 * 3600,
    same_site="strict",
    # En producción va detrás de HTTPS; para probar en local se puede desactivar con LA_CEIBA_HTTPS=0.
    https_only=os.environ.get("LA_CEIBA_HTTPS", "1") != "0",
)
app.mount("/diseno", StaticFiles(directory=RAIZ / "diseno"), name="diseno")


@app.middleware("http")
async def cabeceras_seguras(request: Request, siguiente):
    respuesta = await siguiente(request)
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith(("/panel", "/admin")):
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


def es_admin(request: Request) -> bool:
    return bool(request.session.get("admin"))


def pagina(request: Request, nombre: str, **contexto) -> HTMLResponse:
    contexto |= {"csrf": seguridad.token_csrf(request.session), "admin": es_admin(request)}
    return plantillas.TemplateResponse(request, nombre, contexto)


def a_entrar() -> RedirectResponse:
    return RedirectResponse("/entrar", status_code=303)


def resultado(request: Request, fallos: dict[str, int], exito: str) -> None:
    """Deja el aviso para la siguiente página (patrón POST → redirección → GET)."""
    if fallos:
        request.session["aviso"] = {"tipo": "error", "texto": "No se aplicó el cambio: rompía estas pruebas de calidad.",
                                    "detalle": [f"{k} ({v} filas)" for k, v in fallos.items()]}
    else:
        request.session["aviso"] = {"tipo": "bien", "texto": exito, "detalle": []}


@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    return pagina(request, "inicio.html")


@app.get("/entrar", response_class=HTMLResponse)
def entrar(request: Request):
    if es_admin(request):
        return RedirectResponse("/panel", status_code=303)
    return pagina(request, "entrar.html", error="")


@app.post("/entrar")
def entrar_post(request: Request, usuario: str = Form(""), clave: str = Form(""), csrf: str = Form("")):
    ip = request.client.host if request.client else "?"
    if not seguridad.csrf_valido(request.session, csrf):
        return pagina(request, "entrar.html", error="La sesión caducó. Vuelve a intentarlo.")
    if seguridad.bloqueado(ip):
        return pagina(request, "entrar.html", error="Demasiados intentos. Espera 5 minutos.")
    if not seguridad.verificar(CARPETA / "admin.json", usuario, clave):
        seguridad.registrar_fallo(ip)
        return pagina(request, "entrar.html", error="Usuario o contraseña incorrectos.")
    seguridad.limpiar_fallos(ip)
    request.session.clear()  # sesión nueva al entrar
    request.session["admin"] = usuario
    return RedirectResponse("/panel", status_code=303)


@app.post("/salir")
def salir(request: Request, csrf: str = Form("")):
    if seguridad.csrf_valido(request.session, csrf):
        request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/panel", response_class=HTMLResponse)
def panel(request: Request):
    if not es_admin(request):
        return a_entrar()
    con = datos.conexion()
    if con is None:
        return RedirectResponse("/admin", status_code=303)
    acciones = (f'<a href="/admin">Administrar</a>'
                f'<form method="post" action="/salir"><input type="hidden" name="csrf" value="{seguridad.token_csrf(request.session)}">'
                f'<button type="submit">Salir</button></form>')
    with con:
        return HTMLResponse(dashboard.construir(con, acciones))


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    if not es_admin(request):
        return a_entrar()
    con = datos.conexion()
    conciliacion = con.execute("SELECT * FROM gold.conciliacion ORDER BY fuente").fetchall() if con else []
    pendientes = datos.sin_mapear(con)
    if con:
        con.close()
    return pagina(request, "admin.html", aviso=request.session.pop("aviso", None), archivos=datos.archivos(),
                  tipos=datos.TIPOS, conciliacion=conciliacion, pendientes=pendientes,
                  productos=datos.productos(), alias=datos.alias())


def _post_admin(request: Request, csrf: str):
    """Devuelve una redirección si la petición no puede seguir; None si es un administrador con CSRF válido."""
    if not es_admin(request):
        return a_entrar()
    if not seguridad.csrf_valido(request.session, csrf):
        return Response("Petición no válida.", status_code=403)
    return None


@app.post("/admin/cargar")
async def cargar(request: Request, tipo: str = Form(...), archivo: UploadFile = Form(...), mes: str = Form(""),
                 csrf: str = Form("")):
    if (corte := _post_admin(request, csrf)) is not None:
        return corte
    contenido = await archivo.read(datos.TAMANO_MAXIMO + 1)
    try:
        filas, fallos = datos.cargar_archivo(tipo, contenido, mes)
        resultado(request, fallos, f"Archivo cargado: {filas} filas. El panel ya está actualizado.")
    except datos.ErrorDatos as e:
        request.session["aviso"] = {"tipo": "error", "texto": str(e), "detalle": []}
    return RedirectResponse("/admin#cargar", status_code=303)


@app.post("/admin/producto")
def producto(request: Request, sku: str = Form(""), nombre: str = Form(""), unidad: str = Form(""), csrf: str = Form("")):
    if (corte := _post_admin(request, csrf)) is not None:
        return corte
    try:
        resultado(request, datos.guardar_producto(sku, nombre, unidad), f"Producto {sku.strip().upper()} guardado.")
    except datos.ErrorDatos as e:
        request.session["aviso"] = {"tipo": "error", "texto": str(e), "detalle": []}
    return RedirectResponse("/admin#catalogo", status_code=303)


@app.post("/admin/alias")
def guardar_alias(request: Request, alias: str = Form(""), sku: str = Form(""), csrf: str = Form("")):
    if (corte := _post_admin(request, csrf)) is not None:
        return corte
    try:
        resultado(request, datos.guardar_alias(alias, sku), f"«{alias.strip()}» ahora cuenta como {sku}.")
    except datos.ErrorDatos as e:
        request.session["aviso"] = {"tipo": "error", "texto": str(e), "detalle": []}
    return RedirectResponse("/admin#catalogo", status_code=303)


@app.post("/admin/alias/borrar")
def borrar_alias(request: Request, alias: str = Form(""), csrf: str = Form("")):
    if (corte := _post_admin(request, csrf)) is not None:
        return corte
    resultado(request, datos.borrar_alias(alias), f"Forma «{alias}» eliminada.")
    return RedirectResponse("/admin#catalogo", status_code=303)
