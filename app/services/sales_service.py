from __future__ import annotations

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
            total_amount = 0.0

            for cart_item in cart_items:
                item_id = int(cart_item["item_id"])
                quantity = float(cart_item["quantity"])
                if quantity <= 0:
                    raise ValueError("Quantity must be greater than zero.")

                item = self.repo.get_item(item_id)
                if item is None or int(item["is_active"]) != 1:
                    raise ValueError(f"Item id {item_id} is unavailable.")
                if float(item["stock_quantity"]) < quantity:
                    raise ValueError(
                        f"Insufficient stock for {item['name']}. Available: {item['stock_quantity']}"
                    )

                unit_price = float(item["selling_price"])
                unit_cost = float(item["cost_price"])
                line_total = unit_price * quantity
                total_amount += line_total

                prepared_items.append(
                    {
                        "item_id": item_id,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "unit_cost": unit_cost,
                        "line_total": line_total,
                    }
                )

            sale_id, invoice_number = self.repo.create_sale(
                conn,
                total_amount=total_amount,
                payment_method=payment_method,
            )
            self.repo.add_sale_items(conn, sale_id, prepared_items)

            for item in prepared_items:
                self.repo.adjust_stock(
                    conn,
                    item_id=item["item_id"],
                    quantity_delta=-item["quantity"],
                    movement_type="sale",
                    reference_id=sale_id,
                    notes="Stock decreased via sale",
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
