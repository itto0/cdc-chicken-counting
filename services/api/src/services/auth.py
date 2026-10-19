import hashlib
import hmac
import os
import secrets
import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "cdc-poultry-counter-secret-key-32bytes")
ALGORITHM = "HS256"


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}${derived.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    if "$" not in hashed_password:
        # Backward compatibility with legacy unsalted SHA-256 hashes
        return hmac.compare_digest(hashlib.sha256(plain_password.encode("utf-8")).hexdigest(), hashed_password)
    parts = hashed_password.split("$", 1)
    if len(parts) != 2:
        return False
    salt, key = parts
    derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return hmac.compare_digest(derived.hex(), key)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None


def hash_api_key(raw_key: str) -> str:
    """Return SHA-256 hex digest of a raw API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Generate a high-entropy API key.
    Returns: (raw_key, key_hash, prefix)
    """
    token_hex = secrets.token_hex(32)
    raw_key = f"cdc_live_{token_hex}"
    key_hash = hash_api_key(raw_key)
    prefix = raw_key[:16]
    return raw_key, key_hash, prefix

