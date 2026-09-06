
import os, base64, hashlib
from cryptography.fernet import Fernet

def _fernet():
    raw=os.getenv("APP_ENCRYPTION_KEY","")
    if not raw:
        raise RuntimeError("APP_ENCRYPTION_KEY is required for live connections.")
    # Accept either a Fernet key or any strong secret and derive a Fernet-compatible key.
    try:
        return Fernet(raw.encode())
    except Exception:
        key=base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
        return Fernet(key)

def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()

def decrypt_secret(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()
