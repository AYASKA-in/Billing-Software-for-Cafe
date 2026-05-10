from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton, QTableWidgetItem


class BillingController:
    """Focused billing behavior that can be delegated from MainWindow."""

    def __init__(self, window) -> None:
        self.window = window

    def render_categories_and_grid(self, filter_category_id: int | None = None) -> None:
        w = self.window
        if not hasattr(w, "billing_category_tabs_layout"):
            return

        w.current_category_filter = filter_category_id
        sellable_cat_ids = {
            item.get("category_id")
            for item in w.billing_items_cache
            if item.get("category_id")
        }
        categories = [
            category
            for category in w.inventory_service.list_categories()
            if category["id"] in sellable_cat_ids
        ]

        while w.billing_category_tabs_layout.count():
            child = w.billing_category_tabs_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        all_btn = QPushButton("All Items")
        all_btn.setObjectName("CategoryTab")
        all_btn.setCheckable(True)
        all_btn.setChecked(filter_category_id is None)
        all_btn.clicked.connect(lambda: w._petpooja_render_categories_and_grid(None))
        w.billing_category_tabs_layout.addWidget(all_btn)

        for category in categories:
            btn = QPushButton(category["name"])
            btn.setObjectName("CategoryTab")
            btn.setCheckable(True)
            btn.setChecked(filter_category_id == category["id"])
            btn.clicked.connect(
                lambda _, cid=category["id"]: w._petpooja_render_categories_and_grid(cid)
            )
            w.billing_category_tabs_layout.addWidget(btn)

        w.billing_category_tabs_layout.addStretch()

        while w.billing_quick_grid_layout.count():
            child = w.billing_quick_grid_layout.takeAt(0)
            widget = child.widget()
            if widget and widget is not getattr(w, "billing_empty_state_label", None):
                widget.deleteLater()

        query = w.search_input.text().strip().lower() if hasattr(w, "search_input") else ""
        filtered = w.billing_items_cache
        if filter_category_id is not None:
            filtered = [item for item in filtered if item.get("category_id") == filter_category_id]
        if query:
            filtered = [item for item in filtered if query in item["name"].lower()]

        if not filtered:
            w.billing_empty_state_label.setText("No matching items")
            w.billing_empty_state_label.setVisible(True)
            w.billing_quick_grid_layout.addWidget(w.billing_empty_state_label, 0, 0, 1, 2)
            return

        w.billing_empty_state_label.setVisible(False)
        width = max(w.width(), 1000)
        cols = 5 if width >= 1600 else 4 if width >= 1280 else 3 if width >= 1020 else 2
        row, col = 0, 0
        for item in filtered:
            price = float(item["selling_price"])
            btn = QPushButton(f"{item['name']}\nINR {price:.0f}")
            btn.setObjectName("QuickAddItem")
            btn.setMinimumHeight(88)
            btn.setMinimumWidth(128)
            btn.setCursor(Qt.PointingHandCursor)
            tint = w._category_tint(item.get("category_id"))
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {tint['bg']};
                    border: 1px solid {tint['border']};
                    border-left: 5px solid {tint['border']};
                    border-radius: 10px;
                    color: {w.THEME['text_primary']};
                    font-weight: 800;
                    font-size: 12px;
                    padding: 8px 10px;
                    text-align: center;
                }}
                QPushButton:hover {{
                    background-color: {tint['hover']};
                    border-color: {tint['border']};
                    color: {w.THEME['text_primary']};
                }}
                """
            )
            btn.clicked.connect(lambda _, iid=item["id"]: w._handle_quick_add(iid))
            w.billing_quick_grid_layout.addWidget(btn, row, col)
            col += 1
            if col >= cols:
                col = 0
                row += 1

    def refresh_cart_table(self) -> None:
        w = self.window
        items = list(w.cart.values())
        w.cart_table.setRowCount(len(items))

        total = 0.0
        for row_index, item in enumerate(items):
            line_total = item["quantity"] * item["unit_price"]
            total += line_total

            name_item = QTableWidgetItem(item["name"])
            name_item.setData(Qt.UserRole, int(item["item_id"]))
            qty_item = QTableWidgetItem(f"{item['quantity']:.2f}")
            price_item = QTableWidgetItem(f"{item['unit_price']:.2f}")
            total_item = QTableWidgetItem(f"{line_total:.2f}")
            for numeric_item in (qty_item, price_item, total_item):
                numeric_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            w.cart_table.setItem(row_index, 0, name_item)
            w.cart_table.setItem(row_index, 1, qty_item)
            w.cart_table.setItem(row_index, 2, price_item)
            w.cart_table.setItem(row_index, 3, total_item)

        if hasattr(w, "cart_empty_label"):
            w.cart_empty_label.setVisible(not items)
        if hasattr(w, "_refresh_cost_preview_panel"):
            w._refresh_cost_preview_panel()
        self.update_metrics(total_amount=total)

    def update_metrics(self, total_amount: float | None = None) -> None:
        w = self.window
        if not hasattr(w, "billing_cart_lines_value"):
            return

        cart_lines = len(w.cart)
        cart_qty = sum(float(item.get("quantity", 0)) for item in w.cart.values())
        w.billing_cart_lines_value.setText(str(cart_lines))
        w.billing_cart_qty_value.setText(f"{cart_qty:.2f}")

        if total_amount is None:
            total_text = w.total_label.text().replace("TOTAL: INR ", "").strip()
            try:
                total_amount = float(total_text)
            except ValueError:
                total_amount = 0.0
        w.billing_total_value.setText(f"INR {total_amount:.2f}")
        w.total_label.setText(f"TOTAL: INR {total_amount:.2f}")
        if hasattr(w, "cart_summary_label"):
            w.cart_summary_label.setText(f"{cart_lines} lines | {cart_qty:.2f} units")

    def add_item_to_cart_by_id(self, item_id: int, quantity: float = 1.0) -> None:
        w = self.window
        item = next((i for i in w.billing_items_cache if int(i["id"]) == int(item_id)), None)
        if item is None:
            w.show_toast("Selected item is unavailable", is_error=True)
            return

        qty = float(quantity)
        existing_qty = float(w.cart.get(item_id, {}).get("quantity", 0))
        stock_tracked = int(item.get("is_stock_tracked", 1)) == 1
        recipe_costed = (item.get("costing_mode") or "manual") == "recipe"
        if stock_tracked and not recipe_costed:
            available_stock = float(item["stock_quantity"])
            if qty + existing_qty > available_stock:
                w.show_toast(f"Insufficient stock ({available_stock:.0f} max)", is_error=True)
                return

        w.cart[item_id] = {
            "item_id": item_id,
            "name": item["name"],
            "quantity": qty + existing_qty,
            "unit_price": float(item["selling_price"]),
        }
        self.refresh_cart_table()
        QApplication.beep()
