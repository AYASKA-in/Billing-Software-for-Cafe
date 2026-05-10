"""
Reset historic sales data for a client-ready cafe database.

Keeps inventory, recipes, purchases, expenses, and other operational data.
Removes sales history, sale-linked stock movements, and generated receipts.
By default it also restores stock quantities affected by those sale movements.

Usage:
    python scripts/clear_sales_history.py

Optional flags:
    --db-path data/cafe.db
    --receipts-dir data/printed_bills
    --skip-receipts
    --no-stock-restore
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "cafe.db"
DEFAULT_RECEIPTS_DIR = ROOT_DIR / "data" / "printed_bills"


def clear_sales_history(
    db_path: Path,
    receipts_dir: Path | None = None,
    restore_stock: bool = True,
) -> dict[str, int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    deleted_sales = 0
    deleted_stock_movements = 0
    deleted_receipts = 0
    reset_invoice_sequence = False
    restored_item_count = 0

    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        with conn:
            sales_row = conn.execute("SELECT COUNT(*) AS count FROM sales").fetchone()
            deleted_sales = int(sales_row["count"]) if sales_row else 0

            stock_row = conn.execute(
                "SELECT COUNT(*) AS count FROM stock_movements WHERE movement_type IN ('sale', 'recipe_sale')"
            ).fetchone()
            deleted_stock_movements = int(stock_row["count"]) if stock_row else 0

            if restore_stock:
                restore_rows = conn.execute(
                    """
                    SELECT item_id, COALESCE(SUM(quantity_delta), 0) AS net_delta
                    FROM stock_movements
                    WHERE movement_type IN ('sale', 'recipe_sale')
                    GROUP BY item_id
                    HAVING net_delta != 0
                    """
                ).fetchall()
                for row in restore_rows:
                    conn.execute(
                        """
                        UPDATE items
                        SET stock_quantity = stock_quantity - ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (float(row["net_delta"]), int(row["item_id"])),
                    )
                    restored_item_count += 1

            conn.execute("DELETE FROM sales")
            conn.execute(
                "DELETE FROM stock_movements WHERE movement_type IN ('sale', 'recipe_sale')"
            )

            conn.execute("DELETE FROM costing_exceptions WHERE sale_id IS NOT NULL")

            conn.execute(
                """
                INSERT INTO app_settings (setting_key, setting_value)
                VALUES ('invoice_sequence', '0')
                ON CONFLICT(setting_key)
                DO UPDATE SET setting_value = excluded.setting_value, updated_at = CURRENT_TIMESTAMP
                """
            )
            reset_invoice_sequence = True

        if receipts_dir and receipts_dir.exists():
            for path in receipts_dir.iterdir():
                if path.is_file() or path.is_symlink():
                    path.unlink()
                    deleted_receipts += 1
                elif path.is_dir():
                    shutil.rmtree(path)

    finally:
        conn.close()

    return {
        "sales": deleted_sales,
        "stock_movements": deleted_stock_movements,
        "receipts": deleted_receipts,
        "invoice_sequence_reset": int(reset_invoice_sequence),
        "restored_item_count": restored_item_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Clear historic sales data while preserving inventory and recipes.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="Path to the SQLite database file")
    parser.add_argument(
        "--receipts-dir",
        default=str(DEFAULT_RECEIPTS_DIR),
        help="Directory containing generated receipt text files",
    )
    parser.add_argument(
        "--skip-receipts",
        action="store_true",
        help="Do not delete generated receipt files",
    )
    parser.add_argument(
        "--no-stock-restore",
        action="store_true",
        help="Do not reverse sale stock movements before clearing sales",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    receipts_dir = None if args.skip_receipts else Path(args.receipts_dir)
    result = clear_sales_history(
        db_path=db_path,
        receipts_dir=receipts_dir,
        restore_stock=not args.no_stock_restore,
    )

    print("Sales history cleared.")
    print(f"Database: {db_path}")
    print(f"Deleted sales rows: {result['sales']}")
    print(f"Deleted stock movements: {result['stock_movements']}")
    print(f"Deleted receipt files: {result['receipts']}")
    print(f"Restored stock item count: {result['restored_item_count']}")
    print(f"Invoice sequence reset: {'yes' if result['invoice_sequence_reset'] else 'no'}")


if __name__ == "__main__":
    main()
