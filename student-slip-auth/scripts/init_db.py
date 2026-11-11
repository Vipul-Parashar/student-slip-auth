#!/usr/bin/env python3
"""
Initialize Database and seed default admin account.
Usage: python scripts/init_db.py
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.models import AdminUser
from app.security import hash_password

def init_database():
    print("=" * 60)
    print("Smart QR Student Slip System - Database Initializer")
    print("=" * 60)
    print(f"Target Database URL: {settings.DATABASE_URL}")

    # Create tables
    Base.metadata.create_all(bind=engine)
    print("[OK] Database tables created successfully.")

    # Seed Admin User
    db = SessionLocal()
    try:
        existing = db.query(AdminUser).filter(AdminUser.username == settings.DEFAULT_ADMIN_USERNAME).first()
        if not existing:
            admin = AdminUser(
                username=settings.DEFAULT_ADMIN_USERNAME,
                password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                is_active=True
            )
            db.add(admin)
            db.commit()
            print(f"[OK] Default administrator created:")
            print(f"     Username: {settings.DEFAULT_ADMIN_USERNAME}")
            print(f"     Password: {settings.DEFAULT_ADMIN_PASSWORD}")
            print("     (IMPORTANT: Change this password after initial login!)")
        else:
            print(f"[INFO] Administrator account '{existing.username}' already exists.")
    finally:
        db.close()

    print("=" * 60)
    print("Database initialization complete.")
    print("=" * 60)

if __name__ == "__main__":
    init_database()
