"""
Bridge Flow - Crypto Utilities (Phase 9: Security)

Uses the `cryptography` library's Fernet recipe: AES-128 in CBC mode
with an HMAC for authentication, key rotation via timestamps built in.
This is a deliberate choice over rolling custom encryption - Fernet is
misuse-resistant (you can't accidentally pick a broken mode or forget
the HMAC) which matters a lot for a project explicitly forbidden from
inventing its own cryptography.

Every trusted device-pair gets its own Fernet key, generated once
during pairing and stored in the `devices` table. All control messages
and (optionally) chunk data for that peer are encrypted with it.
"""

from cryptography.fernet import Fernet


def generate_shared_key() -> str:
    """Returns a new Fernet key as a string, safe to store in SQLite."""
    return Fernet.generate_key().decode("utf-8")


def encrypt_bytes(key: str, data: bytes) -> bytes:
    f = Fernet(key.encode("utf-8"))
    return f.encrypt(data)


def decrypt_bytes(key: str, token: bytes) -> bytes:
    f = Fernet(key.encode("utf-8"))
    return f.decrypt(token)
