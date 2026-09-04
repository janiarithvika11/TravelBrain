import os
import hmac
import hashlib
import json
import base64
import secrets

SECRET_KEY = os.getenv("SECRET_KEY", "travelbrain-super-secret-key-12345")

def hash_password(password: str) -> str:
    """Hash password securely using PBKDF2 and SHA-256."""
    salt = secrets.token_hex(16)
    data_bytes = password.encode("utf-8")
    salt_bytes = salt.encode("utf-8")
    hashed = hashlib.pbkdf2_hmac("sha256", data_bytes, salt_bytes, 100000)
    return f"pbkdf2_sha256$100000${salt}${hashed.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """Verify standard password against PBKDF2 hash components."""
    try:
        parts = hashed.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = parts[2]
        expected_hash = parts[3]
        
        data_bytes = password.encode("utf-8")
        salt_bytes = salt.encode("utf-8")
        new_hash = hashlib.pbkdf2_hmac("sha256", data_bytes, salt_bytes, iterations)
        return secrets.compare_digest(new_hash.hex(), expected_hash)
    except Exception:
        return False

def sign_token(payload: dict) -> str:
    """Serialize and sign session payload using HMAC-SHA256."""
    data = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    sig = hmac.new(SECRET_KEY.encode("utf-8"), data.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{data}.{sig}"

def verify_token(token: str) -> dict | None:
    """Verify HMAC signature and decode session payload."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        data, sig = parts
        expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), data.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        return json.loads(base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8"))
    except Exception:
        return None
