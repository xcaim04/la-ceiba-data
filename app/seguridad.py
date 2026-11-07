"""Usuario administrador, contraseñas con scrypt, token CSRF y límite de intentos de acceso."""

import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path

INTENTOS_MAXIMOS = 5
BLOQUEO_SEGUNDOS = 300
_fallos: dict[str, list[float]] = {}


def _hash(clave: str, sal: bytes) -> bytes:
    return hashlib.scrypt(clave.encode(), salt=sal, n=2**14, r=8, p=1, dklen=32)


def guardar_admin(archivo: Path, usuario: str, clave: str) -> None:
    if len(clave) < 12:
        raise ValueError("La contraseña debe tener al menos 12 caracteres.")
    sal = secrets.token_bytes(16)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps({"usuario": usuario, "sal": sal.hex(), "hash": _hash(clave, sal).hex()}))
    archivo.chmod(0o600)


def verificar(archivo: Path, usuario: str, clave: str) -> bool:
    if not archivo.exists():
        return False
    datos = json.loads(archivo.read_text())
    calculado = _hash(clave, bytes.fromhex(datos["sal"]))
    # Se comparan las dos cosas siempre, para no revelar por tiempo cuál falló.
    return hmac.compare_digest(calculado.hex(), datos["hash"]) & hmac.compare_digest(usuario, datos["usuario"])


def secreto_de_sesion(archivo: Path) -> str:
    """Clave para firmar la cookie de sesión; se crea una vez y se guarda junto a los datos."""
    if not archivo.exists():
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(secrets.token_hex(32))
        archivo.chmod(0o600)
    return archivo.read_text().strip()


def bloqueado(ip: str) -> bool:
    ahora = time.monotonic()
    _fallos[ip] = [t for t in _fallos.get(ip, []) if ahora - t < BLOQUEO_SEGUNDOS]
    return len(_fallos[ip]) >= INTENTOS_MAXIMOS


def registrar_fallo(ip: str) -> None:
    _fallos.setdefault(ip, []).append(time.monotonic())


def limpiar_fallos(ip: str) -> None:
    _fallos.pop(ip, None)


def token_csrf(sesion: dict) -> str:
    if "csrf" not in sesion:
        sesion["csrf"] = secrets.token_urlsafe(32)
    return sesion["csrf"]


def csrf_valido(sesion: dict, enviado: str) -> bool:
    return bool(enviado) and hmac.compare_digest(sesion.get("csrf", ""), enviado)
