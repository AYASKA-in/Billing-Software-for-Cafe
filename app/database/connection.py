from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, db_path: str = "data/cafe.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @contextmanager
    def connection(self):
        conn = self.get_connection()
        try:
            yield conn
        finally:
            conn.close()

    def init_schema(self, schema_path: str | None = None) -> None:
        if schema_path:
            schema_file = Path(schema_path)
        else:
            schema_file = Path(__file__).resolve().parent / "schema.sql"
            if not schema_file.exists():
                schema_file = Path("app/database/schema.sql")
        sql = schema_file.read_text(encoding="utf-8")
        with self.connection() as conn:
            conn.executescript(sql)
            self._run_migrations(conn)
            conn.commit()

    def _run_migrations(self, conn: sqlite3.Connection) -> None:
        sale_item_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(sale_items)").fetchall()
        }
        if "unit_cost" not in sale_item_columns:
            conn.execute(
                "ALTER TABLE sale_items ADD COLUMN unit_cost REAL NOT NULL DEFAULT 0 CHECK (unit_cost >= 0)"
            )

        items_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(items)").fetchall()
        }
        if "size_type" not in items_columns:
            conn.execute("ALTER TABLE items ADD COLUMN size_type TEXT")
        if "selling_price" in items_columns:
            conn.execute(
                "UPDATE items SET selling_price = 0.01 WHERE selling_price <= 0"
            )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS day_closures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                closure_date TEXT NOT NULL UNIQUE,
                sales_total REAL NOT NULL,
                cogs_total REAL NOT NULL,
                expenses_total REAL NOT NULL,
                gross_profit REAL NOT NULL,
                net_profit REAL NOT NULL,
                closed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_role TEXT NOT NULL,
                action_type TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            "INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('invoice_sequence', '0')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('invoice_prefix', 'CAFE')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('admin_pin', '1234')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('current_role', 'cashier')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('auto_backup_enabled', '0')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('backup_interval_minutes', '60')"
        )

    @contextmanager
    def transaction(self):
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
