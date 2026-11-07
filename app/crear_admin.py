"""Crea o reemplaza el usuario administrador.

Uso: uv run python -m app.crear_admin <usuario>
La contraseña se pide por teclado y se guarda solo su hash (scrypt) en <datos>/admin.json.
"""

import getpass
import sys

from app.datos import CARPETA
from app.seguridad import guardar_admin

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: uv run python -m app.crear_admin <usuario>")
    clave = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
    if clave != getpass.getpass("Repítela: "):
        sys.exit("Las contraseñas no coinciden.")
    try:
        guardar_admin(CARPETA / "admin.json", sys.argv[1], clave)
    except ValueError as e:
        sys.exit(str(e))
    print(f"Administrador «{sys.argv[1]}» guardado en {CARPETA / 'admin.json'}")
