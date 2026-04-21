from __future__ import annotations

import sqlite3
import sys
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
            try:
                conn.executescript(sql)
            except sqlite3.OperationalError as exc:
                # Older databases can fail on CREATE INDEX for columns added in later migrations.
                if "no such column" not in str(exc).lower():
                    raise
                print(
                    f"[DB] Schema recovery triggered ({exc}). Applying migrations before schema replay.",
                    file=sys.stderr,
                )
                self._run_migrations(conn)
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
        if "item_kind" not in items_columns:
            conn.execute("ALTER TABLE items ADD COLUMN item_kind TEXT NOT NULL DEFAULT 'sellable'")
        if "costing_mode" not in items_columns:
            conn.execute("ALTER TABLE items ADD COLUMN costing_mode TEXT NOT NULL DEFAULT 'manual'")
        if "unit_name" not in items_columns:
            conn.execute("ALTER TABLE items ADD COLUMN unit_name TEXT NOT NULL DEFAULT 'pcs'")
        if "is_stock_tracked" not in items_columns:
            conn.execute("ALTER TABLE items ADD COLUMN is_stock_tracked INTEGER NOT NULL DEFAULT 1")
        if "selling_price" in items_columns:
            conn.execute(
                "UPDATE items SET selling_price = 0.01 WHERE selling_price <= 0"
            )

        conn.execute(
            "UPDATE items SET item_kind = 'sellable' WHERE item_kind IS NULL OR item_kind = ''"
        )
        conn.execute(
            "UPDATE items SET costing_mode = 'manual' WHERE costing_mode IS NULL OR costing_mode = ''"
        )
        conn.execute(
            "UPDATE items SET unit_name = 'pcs' WHERE unit_name IS NULL OR unit_name = ''"
        )
        conn.execute(
            "UPDATE items SET is_stock_tracked = 1 WHERE is_stock_tracked IS NULL"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sellable_item_id INTEGER NOT NULL UNIQUE,
                yield_qty REAL NOT NULL DEFAULT 1 CHECK (yield_qty > 0),
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sellable_item_id) REFERENCES items (id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recipe_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER NOT NULL,
                ingredient_item_id INTEGER NOT NULL,
                quantity_used REAL NOT NULL CHECK (quantity_used > 0),
                waste_percent REAL NOT NULL DEFAULT 0 CHECK (waste_percent >= 0),
                UNIQUE(recipe_id, ingredient_item_id),
                FOREIGN KEY (recipe_id) REFERENCES recipes (id) ON DELETE CASCADE,
                FOREIGN KEY (ingredient_item_id) REFERENCES items (id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_overheads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                overhead_date TEXT NOT NULL UNIQUE,
                gas_cost REAL NOT NULL DEFAULT 0 CHECK (gas_cost >= 0),
                labor_cost REAL NOT NULL DEFAULT 0 CHECK (labor_cost >= 0),
                misc_cost REAL NOT NULL DEFAULT 0 CHECK (misc_cost >= 0),
                expected_units REAL NOT NULL DEFAULT 0 CHECK (expected_units >= 0),
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS costing_exceptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exception_type TEXT NOT NULL,
                item_id INTEGER,
                sale_id INTEGER,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES items (id),
                FOREIGN KEY (sale_id) REFERENCES sales (id)
            )
            """
        )

        conn.execute("CREATE INDEX IF NOT EXISTS idx_items_kind ON items (item_kind)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_recipe_lines_recipe_id ON recipe_lines (recipe_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_costing_exceptions_created_at ON costing_exceptions (created_at)")

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
