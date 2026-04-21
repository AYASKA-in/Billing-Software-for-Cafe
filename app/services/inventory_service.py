from __future__ import annotations

from app.database.repository import Repository


class InventoryService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def list_items(self) -> list[dict]:
        return self.repo.list_items(active_only=True)

    def list_categories(self) -> list[dict]:
        return self.repo.list_categories()

    def add_item(
        self,
        name: str,
        category_id: int | None,
        selling_price: float,
        cost_price: float,
        stock_quantity: float,
        reorder_level: float,
        item_kind: str = "sellable",
        costing_mode: str = "manual",
        unit_name: str = "pcs",
        is_stock_tracked: bool = True,
    ) -> int:
        if not name.strip():
            raise ValueError("Item name is required.")
        if selling_price <= 0:
            raise ValueError("Selling price must be greater than zero.")
        if cost_price < 0:
            raise ValueError("Cost price must be non-negative.")
        if stock_quantity < 0 or reorder_level < 0:
            raise ValueError("Stock and reorder level must be non-negative.")

        category_name = None
        if category_id is not None:
            categories = self.repo.list_categories()
            category_name = next((c["name"] for c in categories if c["id"] == category_id), None)

        size_type = None
        if category_name and category_name.lower() == "cigarette":
            size_type = self._size_from_price(selling_price)

        return self.repo.create_item(
            name=name,
            category_id=category_id,
            selling_price=selling_price,
            cost_price=cost_price,
            size_type=size_type,
            stock_quantity=stock_quantity,
            reorder_level=reorder_level,
            item_kind=item_kind,
            costing_mode=costing_mode,
            unit_name=unit_name,
            is_stock_tracked=is_stock_tracked,
        )

    def list_ingredients(self) -> list[dict]:
        return self.repo.list_ingredients(active_only=True)

    def set_item_classification(
        self,
        item_id: int,
        item_kind: str,
        costing_mode: str,
        is_stock_tracked: bool,
        admin_pin: str,
        unit_name: str | None = None,
    ) -> None:
        if not self.verify_admin_pin(admin_pin):
            raise ValueError("Invalid admin PIN.")
        if item_kind not in {"sellable", "ingredient"}:
            raise ValueError("Invalid item kind.")
        if costing_mode not in {"manual", "recipe"}:
            raise ValueError("Invalid costing mode.")
        if item_kind == "ingredient" and costing_mode != "manual":
            costing_mode = "manual"

        self.repo.set_item_classification(
            item_id=item_id,
            item_kind=item_kind,
            costing_mode=costing_mode,
            is_stock_tracked=is_stock_tracked,
            unit_name=unit_name,
        )

    def save_recipe(
        self,
        sellable_item_id: int,
        lines: list[dict],
        yield_qty: float,
        admin_pin: str,
    ) -> int:
        if not self.verify_admin_pin(admin_pin):
            raise ValueError("Invalid admin PIN.")
        return self.repo.upsert_recipe(
            sellable_item_id=sellable_item_id,
            lines=lines,
            yield_qty=yield_qty,
        )

    def get_recipe(self, sellable_item_id: int) -> dict | None:
        return self.repo.get_recipe_for_item(sellable_item_id)

    def low_stock_items(self) -> list[dict]:
        return self.repo.low_stock_items()

    def verify_admin_pin(self, pin: str) -> bool:
        configured_pin = self.repo.get_setting("admin_pin", "1234")
        return pin == configured_pin

    def update_item_pricing(
        self,
        item_id: int,
        selling_price: float,
        cost_price: float,
        admin_pin: str,
    ) -> None:
        if not self.verify_admin_pin(admin_pin):
            raise ValueError("Invalid admin PIN.")
        if selling_price <= 0:
            raise ValueError("Selling price must be greater than zero.")
        if cost_price < 0:
            raise ValueError("Cost price must be non-negative.")
        self.repo.update_item_pricing(item_id, selling_price, cost_price)

    def update_item_sell_and_reorder(
        self,
        item_id: int,
        selling_price: float,
        reorder_level: float,
        admin_pin: str,
    ) -> None:
        if not self.verify_admin_pin(admin_pin):
            raise ValueError("Invalid admin PIN.")
        if selling_price <= 0:
            raise ValueError("Selling price must be greater than zero.")
        if reorder_level < 0:
            raise ValueError("Reorder level must be non-negative.")
        self.repo.update_item_sell_and_reorder(item_id, selling_price, reorder_level)

    def manual_stock_adjustment(
        self,
        item_id: int,
        quantity_delta: float,
        admin_pin: str,
        notes: str = "",
    ) -> None:
        if not self.verify_admin_pin(admin_pin):
            raise ValueError("Invalid admin PIN.")
        if quantity_delta == 0:
            raise ValueError("Stock change cannot be zero.")

        with self.repo.db.transaction() as conn:
            self.repo.adjust_stock(
                conn,
                item_id=item_id,
                quantity_delta=quantity_delta,
                movement_type="manual",
                notes=notes or "Manual stock correction",
            )

    def stock_movements(self, limit: int = 200) -> list[dict]:
        return self.repo.get_stock_movements(limit=limit)

    def delete_item(self, item_id: int, admin_pin: str) -> None:
        if not self.verify_admin_pin(admin_pin):
            raise ValueError("Invalid admin PIN.")
        self.repo.soft_delete_item(item_id)

    def cigarette_items_grouped(self) -> dict[str, list[dict]]:
        groups = {"small": [], "medium": [], "big": []}
        for item in self.repo.list_items(active_only=True):
            if (item.get("category_name") or "").lower() != "cigarette":
                continue

            size_type = item.get("size_type") or self._size_from_price(float(item["selling_price"]))
            if size_type not in groups:
                continue
            groups[size_type].append(item)

        for key in groups:
            groups[key].sort(key=lambda i: (float(i["selling_price"]), i["name"].lower()))
        return groups

    def load_starter_cigarette_items(self) -> int:
        categories = self.repo.list_categories()
        category_id = next((c["id"] for c in categories if c["name"].lower() == "cigarette"), None)
        if category_id is None:
            raise ValueError("Cigarette category is missing.")

        existing = {
            (i["name"].lower(), float(i["selling_price"]))
            for i in self.repo.list_items(active_only=False)
            if (i.get("category_name") or "").lower() == "cigarette"
        }

        starter_items = [
            ("Gold Flake", 10),
            ("Gold Flake", 13),
            ("Gold Flake", 15),
            ("Classic", 18),
            ("Classic", 20),
            ("Classic", 22),
            ("Benson", 25),
            ("Benson", 30),
        ]

        created_count = 0
        for name, price in starter_items:
            if (name.lower(), float(price)) in existing:
                continue
            self.repo.create_item(
                name=f"{name}",
                category_id=category_id,
                selling_price=float(price),
                cost_price=max(float(price) - 2, 0),
                size_type=self._size_from_price(float(price)),
                stock_quantity=0,
                reorder_level=5,
            )
            created_count += 1
        return created_count

    @staticmethod
    def _size_from_price(price: float) -> str:
        if price <= 15:
            return "small"
        if price <= 22:
            return "medium"
        return "big"
