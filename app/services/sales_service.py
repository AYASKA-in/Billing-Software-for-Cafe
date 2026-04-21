from __future__ import annotations

from collections import defaultdict
from datetime import date

from app.database.connection import Database
from app.database.repository import Repository


class SalesService:
    def __init__(self, db: Database, repo: Repository) -> None:
        self.db = db
        self.repo = repo

    def checkout(self, cart_items: list[dict], payment_method: str = "cash") -> dict:
        if not cart_items:
            raise ValueError("Cart is empty.")

        with self.db.transaction() as conn:
            prepared_items: list[dict] = []
            ingredient_deductions: dict[int, float] = defaultdict(float)
            deferred_exceptions: list[dict] = []
            total_amount = 0.0

            overhead = self.repo.get_daily_overhead(date.today().isoformat())
            overhead_total = float(overhead["gas_cost"]) + float(overhead["labor_cost"]) + float(overhead["misc_cost"])
            expected_units = float(overhead["expected_units"])
            overhead_per_unit = (overhead_total / expected_units) if expected_units > 0 else 0.0

            for cart_item in cart_items:
                item_id = int(cart_item["item_id"])
                quantity = float(cart_item["quantity"])
                if quantity <= 0:
                    raise ValueError("Quantity must be greater than zero.")

                item = self.repo.get_item(item_id)
                if item is None or int(item["is_active"]) != 1:
                    raise ValueError(f"Item id {item_id} is unavailable.")

                unit_price = float(item["selling_price"])
                recipe = self.repo.get_recipe_for_item(item_id)

                deduct_item_stock = recipe is None
                if deduct_item_stock and int(item.get("is_stock_tracked", 1)) == 1:
                    if float(item["stock_quantity"]) < quantity:
                        raise ValueError(
                            f"Insufficient stock for {item['name']}. Available: {item['stock_quantity']}"
                        )

                unit_cost = float(item["cost_price"])
                if recipe is not None:
                    yield_qty = float(recipe.get("yield_qty", 1) or 1)
                    if yield_qty <= 0:
                        yield_qty = 1.0

                    recipe_unit_cost = 0.0
                    for line in recipe.get("lines", []):
                        ingredient_id = int(line["ingredient_item_id"])
                        ingredient = self.repo.get_item(ingredient_id)
                        if ingredient is None or int(ingredient["is_active"]) != 1:
                            raise ValueError(f"Recipe ingredient unavailable for {item['name']}")

                        base_qty = float(line["quantity_used"]) / yield_qty
                        waste_multiplier = 1.0 + (float(line.get("waste_percent", 0.0)) / 100.0)
                        consumed_per_unit = base_qty * waste_multiplier
                        required_qty = consumed_per_unit * quantity

                        available_stock = float(ingredient["stock_quantity"])
                        if available_stock < required_qty:
                            raise ValueError(
                                f"Insufficient ingredient stock for {ingredient['name']}. "
                                f"Need {required_qty:.2f}, available {available_stock:.2f}"
                            )

                        ingredient_cost = float(ingredient["cost_price"])
                        recipe_unit_cost += consumed_per_unit * ingredient_cost
                        ingredient_deductions[ingredient_id] += required_qty

                    unit_cost = recipe_unit_cost + overhead_per_unit
                elif (item.get("costing_mode") or "manual") == "recipe":
                    deferred_exceptions.append(
                        {
                            "type": "recipe_missing_fallback_cost",
                            "item_id": item_id,
                            "details": (
                                f"Recipe costing expected for {item['name']} but no active recipe found. "
                                "Fallback to manual item cost."
                            ),
                        }
                    )

                line_total = unit_price * quantity
                total_amount += line_total

                prepared_items.append(
                    {
                        "item_id": item_id,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "unit_cost": unit_cost,
                        "line_total": line_total,
                        "deduct_item_stock": deduct_item_stock,
                    }
                )

            sale_id, invoice_number = self.repo.create_sale(
                conn,
                total_amount=total_amount,
                payment_method=payment_method,
            )
            self.repo.add_sale_items(conn, sale_id, prepared_items)

            for item in prepared_items:
                if item.get("deduct_item_stock", True):
                    self.repo.adjust_stock(
                        conn,
                        item_id=item["item_id"],
                        quantity_delta=-item["quantity"],
                        movement_type="sale",
                        reference_id=sale_id,
                        notes="Stock decreased via sale",
                    )

            for ingredient_id, qty in ingredient_deductions.items():
                self.repo.adjust_stock(
                    conn,
                    item_id=ingredient_id,
                    quantity_delta=-qty,
                    movement_type="recipe_sale",
                    reference_id=sale_id,
                    notes="Ingredient consumed via recipe sale",
                )

            for ex in deferred_exceptions:
                self.repo.create_costing_exception(
                    exception_type=ex["type"],
                    item_id=ex.get("item_id"),
                    sale_id=sale_id,
                    details=ex["details"],
                    conn=conn,
                )

            return {
                "sale_id": sale_id,
                "invoice_number": invoice_number,
                "total_amount": total_amount,
            }

    def sale_details(self, sale_id: int) -> dict:
        sale = self.repo.get_sale(sale_id)
        if sale is None:
            raise ValueError("Sale not found.")

        items = self.repo.get_sale_items(sale_id)
        sale["items"] = items
        return sale
