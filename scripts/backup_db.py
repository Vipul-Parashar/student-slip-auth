#!/usr/bin/env python3
"""
Create a timestamped backup of the SQLite database.
Usage: python scripts/backup_db.py
"""
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings

def backup_database():
    db_file = settings.DATA_DIR / "slips.db"
    if not db_file.exists():
        print(f"[ERROR] Database file not found at: {db_file}")
        sys.exit(1)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = settings.BACKUP_DIR / f"slips_backup_{timestamp}.db"

    shutil.copy2(db_file, backup_file)
    size_kb = round(backup_file.stat().st_size / 1024, 2)
    print(f"[OK] Database successfully backed up to:")
    print(f"     Path: {backup_file}")
    print(f"     Size: {size_kb} KB")
    print(f"     Timestamp: {timestamp} UTC")

if __name__ == "__main__":
    backup_database()
