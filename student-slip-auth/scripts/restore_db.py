#!/usr/bin/env python3
"""
Restore database from a chosen backup file.
Usage: python scripts/restore_db.py [path_to_backup.db]
"""
import sys
import shutil
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings

def restore_database(backup_path_str: str = None):
    print("=" * 60)
    print("Smart QR Student Slip System - Database Restore Tool")
    print("=" * 60)

    target_db = settings.DATA_DIR / "slips.db"

    if not backup_path_str:
        # Pick the most recent backup from backups/
        backups = sorted(settings.BACKUP_DIR.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not backups:
            print("[ERROR] No backup .db files found in backups directory.")
            sys.exit(1)
        backup_file = backups[0]
        print(f"[INFO] No file specified. Auto-selected latest backup: {backup_file.name}")
    else:
        backup_file = Path(backup_path_str)
        if not backup_file.exists():
            print(f"[ERROR] Specified backup file does not exist: {backup_file}")
            sys.exit(1)

    # Make safety copy of current DB if exists
    if target_db.exists():
        safety_copy = target_db.with_suffix(".db.pre-restore")
        shutil.copy2(target_db, safety_copy)
        print(f"[INFO] Existing database saved to: {safety_copy.name}")

    # Restore
    shutil.copy2(backup_file, target_db)
    print(f"[OK] Successfully restored database from: {backup_file.name}")
    print(f"     Target: {target_db}")
    print("=" * 60)

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    restore_database(arg)
