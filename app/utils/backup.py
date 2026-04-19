from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import sqlite3


def create_backup(db_path: str = "data/cafe.db", backup_dir: str = "data/backups") -> Path:
    source = Path(db_path)
    if not source.exists():
        raise FileNotFoundError(f"Database file not found: {source}")

    target_dir = Path(backup_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_file = target_dir / f"cafe_backup_{stamp}.db"
    shutil.copy2(source, target_file)
    return target_file


def export_backup(destination_dir: str, db_path: str = "data/cafe.db") -> Path:
    return create_backup(db_path=db_path, backup_dir=destination_dir)


def restore_backup(backup_file: str, db_path: str = "data/cafe.db") -> Path:
    source = Path(backup_file)
    if not source.exists():
        raise FileNotFoundError(f"Backup file not found: {source}")

    target = Path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def inspect_backup_counts(backup_file: str) -> dict:
    source = Path(backup_file)
    if not source.exists():
        raise FileNotFoundError(f"Backup file not found: {source}")

    conn = sqlite3.connect(source)
    conn.row_factory = sqlite3.Row
    try:
        def count(query: str) -> int:
            return int(conn.execute(query).fetchone()[0])

        return {
            "items": count("SELECT COUNT(*) FROM items WHERE is_active = 1"),
            "sales": count("SELECT COUNT(*) FROM sales"),
            "purchases": count("SELECT COUNT(*) FROM purchases"),
            "expenses": count("SELECT COUNT(*) FROM expenses"),
            "stock_movements": count("SELECT COUNT(*) FROM stock_movements"),
        }
    finally:
        conn.close()
