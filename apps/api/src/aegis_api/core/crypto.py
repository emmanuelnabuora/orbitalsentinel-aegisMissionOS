"""Symmetric encryption for small secrets at rest (TOTP seeds).

Key: AEGIS_ENCRYPTION_KEY if set (32-byte urlsafe-base64, i.e. a Fernet key);
otherwise derived from the JWT secret via SHA-256. Derivation keeps zero-config
dev working; production should set a dedicated key so JWT-secret rotation and
data-at-rest key rotation are independent events (ADR-0007).
"""

import base64
import hashlib

from cryptography.fernet import Fernet

from aegis_api.core.config import get_settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        s = get_settings()
        if s.encryption_key:
            key = s.encryption_key.encode()
        else:
            digest = hashlib.sha256(f"{s.secret_key}:aegis-data-at-rest".encode()).digest()
            key = base64.urlsafe_b64encode(digest)
        _fernet = Fernet(key)
    return _fernet


def encrypt(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()
