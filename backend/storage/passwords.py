"""Versioned scrypt password hashes; independent of token encryption."""
import hashlib
import hmac
import os


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=131072, r=8, p=1, maxmem=268435456)
    return f"scrypt$131072$8$1${salt.hex()}${digest.hex()}"


def check_password(password, stored):
    if not stored.startswith("scrypt$"):
        return hmac.compare_digest(password.encode(), stored.encode()), True
    try:
        _, n, r, p, salt, expected = stored.split("$")
        if (n, r, p) != ("131072", "8", "1"):
            return False, False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n),
                                r=int(r), p=int(p), maxmem=268435456)
        return hmac.compare_digest(actual, bytes.fromhex(expected)), False
    except (ValueError, TypeError):
        return False, False
