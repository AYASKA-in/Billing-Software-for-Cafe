from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

from app.database.connection import Database


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_categories(self) -> list[dict]:
        with self.db.connection() as conn:
            rows = conn.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
            return [dict(r) for r in rows]

    def list_items(self, active_only: bool = True) -> list[dict]:
        query = """
            SELECT i.id, i.name, i.category_id, c.name AS category_name,
                   i.selling_price, i.cost_price, i.size_type,
                   i.stock_quantity, i.reorder_level, i.is_active
            FROM items i
            LEFT JOIN categories c ON c.id = i.category_id
        """
        if active_only:
            query += " WHERE i.is_active = 1"
        query += " ORDER BY i.name"
        with self.db.connection() as conn:
            rows = conn.execute(query).fetchall()
            return [dict(r) for r in rows]

    def create_item(
        self,
        name: str,
        category_id: int | None,
        selling_price: float,
        cost_price: float,
        size_type: str | None,
        stock_quantity: float,
        reorder_level: float,
    ) -> int:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO items (name, category_id, selling_price, cost_price, size_type, stock_quantity, reorder_level)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name.strip(),
                    category_id,
                    selling_price,
                    cost_price,
                    size_type,
                    stock_quantity,
                    reorder_level,
                ),
            )
            item_id = cursor.lastrowid
            conn.execute(
                """
                INSERT INTO stock_movements (item_id, movement_type, quantity_delta, notes)
                VALUES (?, 'initial_stock', ?, 'Initial stock entry')
                """,
                (item_id, stock_quantity),
            )
            return int(item_id)

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT setting_value FROM app_settings WHERE setting_key = ?",
                (key,),
            ).fetchone()
            return row["setting_value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO app_settings (setting_key, setting_value)
                VALUES (?, ?)
                ON CONFLICT(setting_key)
                DO UPDATE SET setting_value = excluded.setting_value, updated_at = CURRENT_TIMESTAMP
                """,
                (key, value),
            )

    def get_item(self, item_id: int) -> dict | None:
        with self.db.connection() as conn:
            row = conn.execute(
                """
                SELECT id, name, selling_price, cost_price, stock_quantity, reorder_level, is_active
                FROM items
                WHERE id = ?
                """,
                (item_id,),
            ).fetchone()
            return dict(row) if row else None

    def update_item_pricing(self, item_id: int, selling_price: float, cost_price: float) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE items
                SET selling_price = ?, cost_price = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (selling_price, cost_price, item_id),
            )

    def update_item_sell_and_reorder(self, item_id: int, selling_price: float, reorder_level: float) -> None:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE items
                SET selling_price = ?, reorder_level = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (selling_price, reorder_level, item_id),
            )
            if cursor.rowcount == 0:
                raise ValueError("Item not found.")

    def soft_delete_item(self, item_id: int) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE items SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (item_id,),
            )

    def adjust_stock(
        self,
        conn,
        item_id: int,
        quantity_delta: float,
        movement_type: str,
        reference_id: int | None = None,
        notes: str | None = None,
    ) -> None:
        row = conn.execute(
            "SELECT stock_quantity FROM items WHERE id = ?",
            (item_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Item not found for stock update.")
        next_stock = float(row["stock_quantity"]) + float(quantity_delta)
        if next_stock < 0:
            raise ValueError("Stock update rejected: resulting stock would be negative.")

        conn.execute(
            """
            UPDATE items
            SET stock_quantity = stock_quantity + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (quantity_delta, item_id),
        )
        conn.execute(
            """
            INSERT INTO stock_movements (item_id, movement_type, quantity_delta, reference_id, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (item_id, movement_type, quantity_delta, reference_id, notes),
        )

    def create_sale(self, conn, total_amount: float, payment_method: str = "cash") -> tuple[int, str]:
        row = conn.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key = 'invoice_sequence'"
        ).fetchone()
        current_seq = int(row["setting_value"]) if row else 0
        next_seq = current_seq + 1

        prefix_row = conn.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key = 'invoice_prefix'"
        ).fetchone()
        prefix = prefix_row["setting_value"] if prefix_row else "CAFE"

        invoice_number = f"{prefix}-{next_seq:06d}"
        cursor = conn.execute(
            """
            INSERT INTO sales (invoice_number, total_amount, payment_method)
            VALUES (?, ?, ?)
            """,
            (invoice_number, total_amount, payment_method),
        )
        conn.execute(
            """
            INSERT INTO app_settings (setting_key, setting_value)
            VALUES ('invoice_sequence', ?)
            ON CONFLICT(setting_key)
            DO UPDATE SET setting_value = excluded.setting_value, updated_at = CURRENT_TIMESTAMP
            """,
            (str(next_seq),),
        )
        return int(cursor.lastrowid), invoice_number

    def add_sale_items(self, conn, sale_id: int, items: Iterable[dict]) -> None:
        conn.executemany(
            """
            INSERT INTO sale_items (sale_id, item_id, quantity, unit_price, unit_cost, line_total)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    sale_id,
                    item["item_id"],
                    item["quantity"],
                    item["unit_price"],
                    item["unit_cost"],
                    item["line_total"],
                )
                for item in items
            ],
        )

    def get_sale(self, sale_id: int) -> dict | None:
        with self.db.connection() as conn:
            row = conn.execute(
                """
                SELECT id, invoice_number, sold_at, total_amount, payment_method
                FROM sales
                WHERE id = ?
                """,
                (sale_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_sale_items(self, sale_id: int) -> list[dict]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT si.item_id, i.name, si.quantity, si.unit_price, si.unit_cost, si.line_total
                FROM sale_items si
                INNER JOIN items i ON i.id = si.item_id
                WHERE si.sale_id = ?
                ORDER BY si.id
                """,
                (sale_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def create_expense(self, expense_type: str, amount: float, notes: str = "") -> int:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO expenses (expense_type, amount, notes)
                VALUES (?, ?, ?)
                """,
                (expense_type.strip(), amount, notes.strip()),
            )
            return int(cursor.lastrowid)

    def update_expense(self, expense_id: int, expense_type: str, amount: float, notes: str = "") -> None:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE expenses
                SET expense_type = ?, amount = ?, notes = ?
                WHERE id = ?
                """,
                (expense_type.strip(), amount, notes.strip(), expense_id),
            )
            if cursor.rowcount == 0:
                raise ValueError("Expense not found.")

    def create_purchase(self, supplier_name: str, items: Iterable[dict], notes: str = "") -> int:
        items = list(items)
        total_cost = sum(i["quantity"] * i["cost_price"] for i in items)
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO purchases (supplier_name, total_cost, notes)
                VALUES (?, ?, ?)
                """,
                (supplier_name.strip(), total_cost, notes.strip()),
            )
            purchase_id = int(cursor.lastrowid)

            conn.executemany(
                """
                INSERT INTO purchase_items (purchase_id, item_id, quantity, cost_price, line_total)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        purchase_id,
                        item["item_id"],
                        item["quantity"],
                        item["cost_price"],
                        item["quantity"] * item["cost_price"],
                    )
                    for item in items
                ],
            )

            for item in items:
                self.adjust_stock(
                    conn,
                    item["item_id"],
                    item["quantity"],
                    movement_type="purchase",
                    reference_id=purchase_id,
                    notes="Stock increased via purchase",
                )
            return purchase_id

    def get_purchase(self, purchase_id: int) -> dict | None:
        with self.db.connection() as conn:
            row = conn.execute(
                """
                SELECT id, supplier_name, purchased_at, total_cost, notes
                FROM purchases
                WHERE id = ?
                """,
                (purchase_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_purchase_items(self, purchase_id: int) -> list[dict]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT pi.item_id, i.name, pi.quantity, pi.cost_price, pi.line_total
                FROM purchase_items pi
                INNER JOIN items i ON i.id = pi.item_id
                WHERE pi.purchase_id = ?
                ORDER BY pi.id
                """,
                (purchase_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_purchase(self, purchase_id: int, supplier_name: str, items: Iterable[dict], notes: str = "") -> None:
        items = list(items)
        total_cost = sum(i["quantity"] * i["cost_price"] for i in items)

        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM purchases WHERE id = ?",
                (purchase_id,),
            ).fetchone()
            if existing is None:
                raise ValueError("Purchase not found.")

            old_lines = conn.execute(
                """
                SELECT item_id, quantity
                FROM purchase_items
                WHERE purchase_id = ?
                """,
                (purchase_id,),
            ).fetchall()

            # Reverse previous stock effect from the old purchase lines.
            for old_line in old_lines:
                self.adjust_stock(
                    conn,
                    item_id=int(old_line["item_id"]),
                    quantity_delta=-float(old_line["quantity"]),
                    movement_type="purchase_edit_reverse",
                    reference_id=purchase_id,
                    notes="Reversed stock from purchase edit",
                )

            conn.execute("DELETE FROM purchase_items WHERE purchase_id = ?", (purchase_id,))

            conn.executemany(
                """
                INSERT INTO purchase_items (purchase_id, item_id, quantity, cost_price, line_total)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        purchase_id,
                        item["item_id"],
                        item["quantity"],
                        item["cost_price"],
                        item["quantity"] * item["cost_price"],
                    )
                    for item in items
                ],
            )

            for item in items:
                self.adjust_stock(
                    conn,
                    item_id=item["item_id"],
                    quantity_delta=item["quantity"],
                    movement_type="purchase_edit_apply",
                    reference_id=purchase_id,
                    notes="Applied stock from edited purchase",
                )

            conn.execute(
                """
                UPDATE purchases
                SET supplier_name = ?, total_cost = ?, notes = ?
                WHERE id = ?
                """,
                (supplier_name.strip(), float(total_cost), notes.strip(), purchase_id),
            )

    def get_today_summary(self) -> dict:
        today = date.today().isoformat()
        return self.get_summary_between(start_date=today, end_date=today)

    def get_summary_between(self, start_date: str, end_date: str) -> dict:
        with self.db.connection() as conn:
            sales_total = conn.execute(
                """
                SELECT COALESCE(SUM(total_amount), 0) AS value
                FROM sales
                WHERE DATE(sold_at, 'localtime') BETWEEN DATE(?) AND DATE(?)
                """,
                (start_date, end_date),
            ).fetchone()["value"]

            expenses_total = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS value
                FROM expenses
                WHERE DATE(spent_at, 'localtime') BETWEEN DATE(?) AND DATE(?)
                """,
                (start_date, end_date),
            ).fetchone()["value"]

            purchase_total = conn.execute(
                """
                SELECT COALESCE(SUM(total_cost), 0) AS value
                FROM purchases
                WHERE DATE(purchased_at, 'localtime') BETWEEN DATE(?) AND DATE(?)
                """,
                (start_date, end_date),
            ).fetchone()["value"]

            cogs_total = conn.execute(
                """
                SELECT COALESCE(SUM(si.quantity * si.unit_cost), 0) AS value
                FROM sale_items si
                INNER JOIN sales s ON s.id = si.sale_id
                WHERE DATE(s.sold_at, 'localtime') BETWEEN DATE(?) AND DATE(?)
                """,
                (start_date, end_date),
            ).fetchone()["value"]

            return {
                "sales": float(sales_total),
                "purchases": float(purchase_total),
                "expenses": float(expenses_total),
                "cogs": float(cogs_total),
            }

    def low_stock_items(self) -> list[dict]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, name, stock_quantity, reorder_level
                FROM items
                WHERE is_active = 1 AND stock_quantity <= reorder_level
                ORDER BY stock_quantity ASC, name ASC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def list_recent_purchases(self, limit: int = 100) -> list[dict]:
        return self.list_purchases_between("1900-01-01", "9999-12-31", limit=limit)

    def list_purchases_between(self, start_date: str, end_date: str, limit: int = 500) -> list[dict]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT p.id, p.supplier_name, p.purchased_at, p.total_cost, p.notes,
                       COUNT(pi.id) AS line_items
                FROM purchases p
                LEFT JOIN purchase_items pi ON pi.purchase_id = p.id
                WHERE DATE(p.purchased_at, 'localtime') BETWEEN DATE(?) AND DATE(?)
                GROUP BY p.id, p.supplier_name, p.purchased_at, p.total_cost, p.notes
                ORDER BY p.id DESC
                LIMIT ?
                """,
                (start_date, end_date, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_recent_expenses(self, limit: int = 100) -> list[dict]:
        return self.list_expenses_between("1900-01-01", "9999-12-31", limit=limit)

    def list_expenses_between(self, start_date: str, end_date: str, limit: int = 500) -> list[dict]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, expense_type, amount, spent_at, notes
                FROM expenses
                WHERE DATE(spent_at, 'localtime') BETWEEN DATE(?) AND DATE(?)
                ORDER BY id DESC
                LIMIT ?
                """,
                (start_date, end_date, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def sales_by_day(self, days: int = 7) -> list[dict]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT DATE(s.sold_at, 'localtime') AS sale_date,
                       COUNT(DISTINCT s.id) AS bill_count,
                       COALESCE(SUM(s.total_amount), 0) AS sales_total,
                       COALESCE(SUM(si.quantity * si.unit_cost), 0) AS cogs_total
                FROM sales s
                LEFT JOIN sale_items si ON si.sale_id = s.id
                WHERE DATE(s.sold_at, 'localtime') >= DATE('now', 'localtime', ?)
                GROUP BY DATE(s.sold_at, 'localtime')
                ORDER BY sale_date DESC
                """,
                (f"-{days - 1} day",),
            ).fetchall()
            return [dict(r) for r in rows]

    def sales_by_date_range(self, start_date: str, end_date: str) -> list[dict]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT DATE(s.sold_at, 'localtime') AS sale_date,
                       COUNT(DISTINCT s.id) AS bill_count,
                       COALESCE(SUM(s.total_amount), 0) AS sales_total,
                       COALESCE(SUM(si.quantity * si.unit_cost), 0) AS cogs_total
                FROM sales s
                LEFT JOIN sale_items si ON si.sale_id = s.id
                WHERE DATE(s.sold_at, 'localtime') BETWEEN DATE(?) AND DATE(?)
                GROUP BY DATE(s.sold_at, 'localtime')
                ORDER BY sale_date DESC
                """,
                (start_date, end_date),
            ).fetchall()
            return [dict(r) for r in rows]

    def top_selling_items(self, limit: int = 10) -> list[dict]:
        return self.top_selling_items_between("1900-01-01", "9999-12-31", limit=limit)

    def top_selling_items_between(self, start_date: str, end_date: str, limit: int = 10) -> list[dict]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT i.name,
                       COALESCE(SUM(si.quantity), 0) AS qty_sold,
                       COALESCE(SUM(si.line_total), 0) AS sales_value
                FROM sale_items si
                INNER JOIN sales s ON s.id = si.sale_id
                INNER JOIN items i ON i.id = si.item_id
                WHERE DATE(s.sold_at, 'localtime') BETWEEN DATE(?) AND DATE(?)
                GROUP BY i.id, i.name
                ORDER BY qty_sold DESC, sales_value DESC
                LIMIT ?
                """,
                (start_date, end_date, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_stock_movements(self, limit: int = 200) -> list[dict]:
        return self.get_stock_movements_between("1900-01-01", "9999-12-31", limit=limit)

    def get_stock_movements_between(self, start_date: str, end_date: str, limit: int = 200) -> list[dict]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT sm.id, sm.item_id, i.name AS item_name, sm.movement_type,
                       sm.quantity_delta, sm.reference_id, sm.notes, sm.moved_at
                FROM stock_movements sm
                INNER JOIN items i ON i.id = sm.item_id
                WHERE DATE(sm.moved_at, 'localtime') BETWEEN DATE(?) AND DATE(?)
                ORDER BY sm.id DESC
                LIMIT ?
                """,
                (start_date, end_date, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def close_day(self, closure_date: str) -> dict:
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM day_closures WHERE closure_date = ?",
                (closure_date,),
            ).fetchone()
            if existing:
                raise ValueError("Day already closed.")

            sales_total = conn.execute(
                "SELECT COALESCE(SUM(total_amount), 0) AS value FROM sales WHERE DATE(sold_at) = DATE(?)",
                (closure_date,),
            ).fetchone()["value"]
            cogs_total = conn.execute(
                """
                SELECT COALESCE(SUM(si.quantity * si.unit_cost), 0) AS value
                FROM sale_items si
                INNER JOIN sales s ON s.id = si.sale_id
                WHERE DATE(s.sold_at) = DATE(?)
                """,
                (closure_date,),
            ).fetchone()["value"]
            expenses_total = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS value FROM expenses WHERE DATE(spent_at) = DATE(?)",
                (closure_date,),
            ).fetchone()["value"]

            gross_profit = float(sales_total) - float(cogs_total)
            net_profit = gross_profit - float(expenses_total)

            conn.execute(
                """
                INSERT INTO day_closures
                (closure_date, sales_total, cogs_total, expenses_total, gross_profit, net_profit)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    closure_date,
                    float(sales_total),
                    float(cogs_total),
                    float(expenses_total),
                    gross_profit,
                    net_profit,
                ),
            )

            return {
                "closure_date": closure_date,
                "sales": float(sales_total),
                "cogs": float(cogs_total),
                "expenses": float(expenses_total),
                "gross_profit": gross_profit,
                "net_profit": net_profit,
            }

    def create_audit_log(
        self,
        actor_role: str,
        action_type: str,
        entity_type: str = "",
        entity_id: str = "",
        details: str = "",
    ) -> int:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO audit_logs (actor_role, action_type, entity_type, entity_id, details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    actor_role.strip() or "unknown",
                    action_type.strip(),
                    entity_type.strip(),
                    entity_id.strip(),
                    details.strip(),
                ),
            )
            return int(cursor.lastrowid)

    def list_audit_logs(self, limit: int = 500) -> list[dict]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, actor_role, action_type, entity_type, entity_id, details, created_at
                FROM audit_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def database_counts(self) -> dict:
        with self.db.connection() as conn:
            return {
                "items": int(conn.execute("SELECT COUNT(*) AS c FROM items WHERE is_active = 1").fetchone()["c"]),
                "sales": int(conn.execute("SELECT COUNT(*) AS c FROM sales").fetchone()["c"]),
                "purchases": int(conn.execute("SELECT COUNT(*) AS c FROM purchases").fetchone()["c"]),
                "expenses": int(conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]),
                "stock_movements": int(conn.execute("SELECT COUNT(*) AS c FROM stock_movements").fetchone()["c"]),
            }

