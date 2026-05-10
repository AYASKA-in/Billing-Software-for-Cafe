from __future__ import annotations


class ReportsController:
    def __init__(self, window) -> None:
        self.window = window

    @staticmethod
    def money(value: float) -> str:
        return f"INR {float(value):.2f}"

    @staticmethod
    def profit_state(value: float) -> str:
        if value < 0:
            return "negative"
        if value > 0:
            return "positive"
        return "neutral"

    def apply_profit_state(self, label, value: float) -> None:
        state = self.profit_state(value)
        label.setProperty("profitState", state)
        label.style().unpolish(label)
        label.style().polish(label)
