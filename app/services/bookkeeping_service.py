from __future__ import annotations

from datetime import date

from app.database.repository import Repository


class BookkeepingService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def verify_admin_pin(self, pin: str) -> bool:
        configured_pin = self.repo.get_setting("admin_pin", "1234")
        return pin == configured_pin

    def add_expense(self, expense_type: str, amount: float, notes: str = "") -> int:
        if not expense_type.strip():
            raise ValueError("Expense type is required.")
        if amount <= 0:
            raise ValueError("Expense amount must be greater than zero.")
        return self.repo.create_expense(expense_type=expense_type, amount=amount, notes=notes)

    def add_purchase(self, supplier_name: str, items: list[dict], notes: str = "") -> int:
        if not items:
            raise ValueError("Purchase must contain at least one item.")
        for item in items:
            if float(item.get("quantity", 0)) <= 0:
                raise ValueError("Purchase quantity must be greater than zero.")
            if float(item.get("cost_price", 0)) < 0:
                raise ValueError("Cost price cannot be negative.")
        return self.repo.create_purchase(supplier_name=supplier_name, items=items, notes=notes)

    def get_purchase_for_edit(self, purchase_id: int, admin_pin: str) -> dict:
        if not self.verify_admin_pin(admin_pin):
            raise ValueError("Invalid admin PIN.")

        purchase = self.repo.get_purchase(purchase_id)
        if purchase is None:
            raise ValueError("Purchase not found.")
        purchase["items"] = self.repo.get_purchase_items(purchase_id)
        return purchase

    def update_purchase(
        self,
        purchase_id: int,
        supplier_name: str,
        items: list[dict],
        notes: str,
        admin_pin: str,
    ) -> None:
        if not self.verify_admin_pin(admin_pin):
            raise ValueError("Invalid admin PIN.")
        if not items:
            raise ValueError("Purchase must contain at least one item.")
        for item in items:
            if float(item.get("quantity", 0)) <= 0:
                raise ValueError("Purchase quantity must be greater than zero.")
            if float(item.get("cost_price", 0)) < 0:
                raise ValueError("Cost price cannot be negative.")

        self.repo.update_purchase(
            purchase_id=purchase_id,
            supplier_name=supplier_name,
            items=items,
            notes=notes,
        )

    def list_recent_purchases(self, limit: int = 100) -> list[dict]:
        return self.repo.list_recent_purchases(limit=limit)

    def list_purchases_between(self, start_date: str, end_date: str, limit: int = 500) -> list[dict]:
        return self.repo.list_purchases_between(start_date=start_date, end_date=end_date, limit=limit)

    def list_recent_expenses(self, limit: int = 100) -> list[dict]:
        return self.repo.list_recent_expenses(limit=limit)

    def list_expenses_between(self, start_date: str, end_date: str, limit: int = 500) -> list[dict]:
        return self.repo.list_expenses_between(start_date=start_date, end_date=end_date, limit=limit)

    def update_expense(self, expense_id: int, expense_type: str, amount: float, notes: str = "") -> None:
        if not expense_type.strip():
            raise ValueError("Expense type is required.")
        if amount <= 0:
            raise ValueError("Expense amount must be greater than zero.")
        self.repo.update_expense(
            expense_id=expense_id,
            expense_type=expense_type,
            amount=amount,
            notes=notes,
        )

    def close_day(self, closure_date: str | None = None) -> dict:
        target_date = closure_date or date.today().isoformat()
        return self.repo.close_day(target_date)

    def set_setting(self, key: str, value: str) -> None:
        self.repo.set_setting(key, value)

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        return self.repo.get_setting(key, default)

    def log_audit(
        self,
        actor_role: str,
        action_type: str,
        entity_type: str = "",
        entity_id: str = "",
        details: str = "",
    ) -> int:
        return self.repo.create_audit_log(
            actor_role=actor_role,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )

    def list_audit_logs(self, limit: int = 500) -> list[dict]:
        return self.repo.list_audit_logs(limit=limit)

    def current_database_counts(self) -> dict:
        return self.repo.database_counts()
