from __future__ import annotations

from pathlib import Path


class PrintService:
    def __init__(self, output_dir: str = "data/printed_bills") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def print_bill(self, bill_payload: dict) -> Path:
        invoice_number = bill_payload.get("invoice_number")
        if not invoice_number:
            raise ValueError("Invoice number is required for printing.")

        target = self.output_dir / f"{invoice_number}.txt"
        lines: list[str] = []
        lines.append("Cafe POS")
        lines.append("------------------------------")
        lines.append(f"Invoice: {invoice_number}")
        lines.append(f"Sale ID: {bill_payload.get('sale_id')}")
        lines.append(f"Date: {bill_payload.get('sold_at', 'N/A')}")
        lines.append("")

        for item in bill_payload.get("items", []):
            lines.append(
                f"{item['name']} x {item['quantity']:.2f} @ {item['unit_price']:.2f} = {item['line_total']:.2f}"
            )

        lines.append("------------------------------")
        lines.append(f"Total: INR {bill_payload.get('total_amount', 0):.2f}")

        target.write_text("\n".join(lines), encoding="utf-8")
        return target
