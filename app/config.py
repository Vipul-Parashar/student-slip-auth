import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory: root of the project (student-slip-auth)
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if present
load_dotenv(BASE_DIR / ".env")

class Settings:
    # App Information
    APP_NAME: str = os.getenv("APP_NAME", "Smart QR Student Slip Authentication")
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

    # Security Keys
    SECRET_KEY: str = os.getenv("SECRET_KEY", "smart-qr-slip-super-secret-key-change-in-production-2026")
    HMAC_SECRET: str = os.getenv("HMAC_SECRET", "smart-qr-hmac-integrity-key-32charslong!")
    SESSION_COOKIE_NAME: str = "slip_auth_session"
    SESSION_MAX_AGE: int = int(os.getenv("SESSION_MAX_AGE", "86400"))  # 24 hours

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'slips.db'}")

    # Verification URL base (used when embedding QR payloads)
    # If empty or localhost, can dynamically resolve to the incoming request base_url
    VERIFY_BASE_URL: str = os.getenv("VERIFY_BASE_URL", "http://localhost:8000")

    # Storage Paths
    STORAGE_DIR: Path = BASE_DIR / "app" / "storage"
    QR_STORAGE_DIR: Path = STORAGE_DIR / "qr_codes"
    ZIP_STORAGE_DIR: Path = STORAGE_DIR / "zips"
    DATA_DIR: Path = BASE_DIR / "data"
    BACKUP_DIR: Path = BASE_DIR / "backups"

    # Default Admin Credentials (created on first run if no admin exists)
    DEFAULT_ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "AdminPass@2026")

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))

settings = Settings()

# Ensure required directories exist
for p in [settings.STORAGE_DIR, settings.QR_STORAGE_DIR, settings.ZIP_STORAGE_DIR, settings.DATA_DIR, settings.BACKUP_DIR]:
    p.mkdir(parents=True, exist_ok=True)
