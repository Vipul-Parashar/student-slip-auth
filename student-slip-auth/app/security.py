import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict
from typing import Optional, Tuple
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app.config import settings

# Serializer for signed session cookies
serializer = URLSafeTimedSerializer(settings.SECRET_KEY)

# -------------------------------------------------------------
# Password Hashing using PBKDF2-HMAC-SHA256 (OWASP Standard)
# -------------------------------------------------------------
ITERATIONS = 310_000

def hash_password(password: str) -> str:
    """Hash password using salt + PBKDF2-HMAC-SHA256."""
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${key.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against stored PBKDF2 hash using constant-time comparison."""
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_key = bytes.fromhex(parts[3])
        calculated_key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(calculated_key, expected_key)
    except Exception:
        return False

# -------------------------------------------------------------
# QR Code Cryptographic Tokens & Signatures
# -------------------------------------------------------------
def generate_slip_token() -> str:
    """Generate 256 bits (32 bytes) of cryptographically random URL-safe token."""
    return secrets.token_urlsafe(32)

def hash_token(token: str) -> str:
    """Compute SHA-256 hash of the token for secure database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_payload_signature(slip_id: str, token: str) -> str:
    """Create HMAC-SHA256 signature for the slip ID and token."""
    message = f"{slip_id}:{token}".encode("utf-8")
    return hmac.new(settings.HMAC_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()

def verify_payload_signature(slip_id: str, token: str, signature: str) -> bool:
    """Verify HMAC signature using constant-time comparison."""
    expected = create_payload_signature(slip_id, token)
    return hmac.compare_digest(expected, signature)

# -------------------------------------------------------------
# Session Management
# -------------------------------------------------------------
def create_session_token(data: dict) -> str:
    """Create a tamper-proof signed session token."""
    return serializer.dumps(data)

def read_session_token(token: str, max_age: Optional[int] = None) -> Optional[dict]:
    """Validate and read signed session token. Returns None if invalid or expired."""
    try:
        max_age = max_age or settings.SESSION_MAX_AGE
        return serializer.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None

# -------------------------------------------------------------
# In-Memory Rate Limiting for Public Verification & Login
# -------------------------------------------------------------
class SimpleRateLimiter:
    def __init__(self, max_requests: int = 120, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        # Clean older requests outside the window
        timestamps = [t for t in self.requests[client_ip] if now - t < self.window_seconds]
        if len(timestamps) >= self.max_requests:
            self.requests[client_ip] = timestamps
            return False
        timestamps.append(now)
        self.requests[client_ip] = timestamps
        return True

rate_limiter = SimpleRateLimiter(max_requests=settings.RATE_LIMIT_PER_MINUTE, window_seconds=60)
