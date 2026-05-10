from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CartItemDTO:
    item_id: int
    quantity: float


@dataclass(frozen=True)
class PreparedSaleItemDTO:
    item_id: int
    quantity: float
    unit_price: float
    unit_cost: float
    line_total: float
    deduct_item_stock: bool = True

    def as_repository_row(self) -> dict:
        return {
            "item_id": self.item_id,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "unit_cost": self.unit_cost,
            "line_total": self.line_total,
            "deduct_item_stock": self.deduct_item_stock,
        }


@dataclass(frozen=True)
class SaleResultDTO:
    sale_id: int
    invoice_number: str
    total_amount: float
    payment_method: str
    customer_name: str = ""
    customer_phone: str = ""

    def as_dict(self) -> dict:
        return {
            "sale_id": self.sale_id,
            "invoice_number": self.invoice_number,
            "total_amount": self.total_amount,
            "payment_method": self.payment_method,
            "customer_name": self.customer_name,
            "customer_phone": self.customer_phone,
        }


@dataclass(frozen=True)
class PurchaseLineDTO:
    item_id: int
    quantity: float
    cost_price: float

    def as_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "quantity": self.quantity,
            "cost_price": self.cost_price,
        }


@dataclass(frozen=True)
class ReportSummaryDTO:
    sales: float = 0.0
    purchases: float = 0.0
    expenses: float = 0.0
    cogs: float = 0.0
    extras: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        payload = {
            "sales": self.sales,
            "purchases": self.purchases,
            "expenses": self.expenses,
            "cogs": self.cogs,
        }
        payload.update(self.extras)
        return payload
