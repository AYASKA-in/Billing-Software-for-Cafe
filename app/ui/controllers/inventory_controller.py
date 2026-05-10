from __future__ import annotations

from PySide6.QtGui import QColor


class InventoryController:
    def __init__(self, window) -> None:
        self.window = window

    @staticmethod
    def stock_status(stock: float, reorder: float) -> tuple[str, str, str]:
        if stock <= 0:
            return f"OUT {stock:.2f}", "#fef2f2", "#b91c1c"
        if stock <= reorder:
            return f"LOW {stock:.2f}", "#fff7ed", "#b45309"
        return f"OK {stock:.2f}", "#ecfdf5", "#047857"

    def apply_stock_status(self, stock_item, stock: float, reorder: float) -> None:
        _, background, foreground = self.stock_status(stock, reorder)
        stock_item.setBackground(QColor(background))
        stock_item.setForeground(QColor(foreground))

    def summary_counts(self, items: list[dict]) -> dict[str, int]:
        low_stock_count = 0
        out_of_stock_count = 0
        reorder_alerts_count = 0
        for item in items:
            stock = float(item.get("stock_quantity", 0) or 0)
            reorder = float(item.get("reorder_level", 0) or 0)
            if stock <= 0:
                out_of_stock_count += 1
            if stock <= reorder:
                low_stock_count += 1
            if stock <= reorder and reorder > 0:
                reorder_alerts_count += 1
        return {
            "total": len(items),
            "low": low_stock_count,
            "out": out_of_stock_count,
            "reorder": reorder_alerts_count,
        }
