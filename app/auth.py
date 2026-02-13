"""
Módulo de autenticación - Gestión de contraseña hasheada con bcrypt
"""
import os
import json
import bcrypt

AUTH_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'auth.json')
DEFAULT_PASSWORD = 'Weinstein'


def _ensure_auth_file():
    """Crea el fichero auth.json con la contraseña por defecto si no existe"""
    if not os.path.exists(AUTH_FILE):
        os.makedirs(os.path.dirname(AUTH_FILE), exist_ok=True)
        save_password(DEFAULT_PASSWORD)


def get_password_hash() -> str:
    """Lee el hash de la contraseña del fichero"""
    _ensure_auth_file()
    with open(AUTH_FILE, 'r') as f:
        data = json.load(f)
    return data['password_hash']


def save_password(password: str):
    """Guarda el hash de una nueva contraseña"""
    os.makedirs(os.path.dirname(AUTH_FILE), exist_ok=True)
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    with open(AUTH_FILE, 'w') as f:
        json.dump({'password_hash': password_hash}, f)


def verify_password(password: str) -> bool:
    """Verifica una contraseña contra el hash almacenado"""
    stored_hash = get_password_hash()
    return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
