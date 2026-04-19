from __future__ import annotations

import calendar
from datetime import date

from app.database.repository import Repository


class ReportService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def get_monthly_fixed_costs(self) -> dict:
        return {
            "rent": float(self.repo.get_setting("fixed_cost_rent", "0") or 0),
            "salary": float(self.repo.get_setting("fixed_cost_salary", "0") or 0),
            "maintenance": float(self.repo.get_setting("fixed_cost_maintenance", "0") or 0),
            "electricity": float(self.repo.get_setting("fixed_cost_electricity", "0") or 0),
        }

    def save_monthly_fixed_costs(
        self,
        rent: float,
        salary: float,
        maintenance: float,
        electricity: float,
    ) -> None:
        values = {
            "fixed_cost_rent": rent,
            "fixed_cost_salary": salary,
            "fixed_cost_maintenance": maintenance,
            "fixed_cost_electricity": electricity,
        }
        for key, value in values.items():
            if value < 0:
                raise ValueError("Fixed costs cannot be negative.")
            self.repo.set_setting(key, f"{float(value):.2f}")

    def today_summary(self) -> dict:
        today = date.today().isoformat()
        return self.summary_between(start_date=today, end_date=today)

    def summary_between(self, start_date: str, end_date: str) -> dict:
        summary = self.repo.get_summary_between(start_date=start_date, end_date=end_date)
        fixed = self.get_monthly_fixed_costs()
        monthly_fixed_total = fixed["rent"] + fixed["salary"] + fixed["maintenance"] + fixed["electricity"]
        days_in_month = calendar.monthrange(date.today().year, date.today().month)[1]
        daily_fixed_overhead = monthly_fixed_total / days_in_month if days_in_month > 0 else 0.0
        try:
            start_obj = date.fromisoformat(start_date)
            end_obj = date.fromisoformat(end_date)
            days_selected = abs((end_obj - start_obj).days) + 1
        except ValueError:
            days_selected = 1
        total_fixed_overhead = daily_fixed_overhead * float(days_selected)

        summary["gross_profit"] = summary["sales"] - summary["cogs"]
        summary["net_profit_before_fixed"] = summary["gross_profit"] - summary["expenses"]
        summary["daily_fixed_overhead"] = daily_fixed_overhead
        summary["selected_days"] = days_selected
        summary["selected_fixed_overhead"] = total_fixed_overhead
        summary["monthly_fixed_total"] = monthly_fixed_total
        summary["net_profit"] = summary["net_profit_before_fixed"] - total_fixed_overhead
        summary["fixed_costs"] = fixed
        return summary

    def low_stock(self) -> list[dict]:
        return self.repo.low_stock_items()

    def stock_ledger(self, limit: int = 200) -> list[dict]:
        return self.repo.get_stock_movements(limit=limit)

    def stock_ledger_between(self, start_date: str, end_date: str, limit: int = 200) -> list[dict]:
        return self.repo.get_stock_movements_between(start_date=start_date, end_date=end_date, limit=limit)

    def sales_trend(self, days: int = 7) -> list[dict]:
        rows = self.repo.sales_by_day(days=days)
        for row in rows:
            row["gross_profit"] = float(row["sales_total"]) - float(row["cogs_total"])
        return rows

    def sales_trend_between(self, start_date: str, end_date: str) -> list[dict]:
        rows = self.repo.sales_by_date_range(start_date=start_date, end_date=end_date)
        for row in rows:
            row["gross_profit"] = float(row["sales_total"]) - float(row["cogs_total"])
        return rows

    def top_items(self, limit: int = 10) -> list[dict]:
        return self.repo.top_selling_items(limit=limit)

    def top_items_between(self, start_date: str, end_date: str, limit: int = 10) -> list[dict]:
        return self.repo.top_selling_items_between(start_date=start_date, end_date=end_date, limit=limit)
