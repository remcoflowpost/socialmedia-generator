"""Versleuteling van provider-tokens (AES-256-GCM).

Formaat: v1.<sleutel-id>.<nonce>.<ciphertext+tag>, alles base64url. De associated data
bindt een ciphertext aan zijn rij (bijv. het account-id), zodat een token niet naar een
andere rij te kopieren is.
"""

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.settings import get_settings


class SecretError(ValueError):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _key() -> bytes:
    raw = get_settings().token_encryption_key
    if not raw:
        raise SecretError("TOKEN_ENCRYPTION_KEY ontbreekt in .env.")
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise SecretError("TOKEN_ENCRYPTION_KEY moet 32 bytes (base64) zijn.")
    return key


def _key_id(key: bytes) -> str:
    return hashlib.sha256(key).hexdigest()[:8]


def encrypt(plain: str, aad: str) -> str:
    key = _key()
    nonce = os.urandom(12)
    sealed = AESGCM(key).encrypt(nonce, plain.encode(), aad.encode())
    return ".".join(["v1", _key_id(key), _b64(nonce), _b64(sealed)])


def decrypt(blob: str, aad: str) -> str:
    parts = blob.split(".")
    if len(parts) != 4 or parts[0] != "v1":
        raise SecretError("Onbekend formaat van versleutelde waarde.")
    key = _key()
    if parts[1] != _key_id(key):
        raise SecretError("Versleuteld met een andere sleutel (geroteerd?).")
    return AESGCM(key).decrypt(_unb64(parts[2]), _unb64(parts[3]), aad.encode()).decode()
