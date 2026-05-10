from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


class PrintService:
    def __init__(self, output_dir: str = "data/printed_bills") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _format_bill_text(self, bill_payload: dict) -> str:
        """Generate formatted bill text from bill payload."""
        invoice_number = bill_payload.get("invoice_number")
        if not invoice_number:
            raise ValueError("Invoice number is required for printing.")

        lines: list[str] = []
        lines.append("Cafe POS")
        lines.append("------------------------------")
        lines.append(f"Invoice: {invoice_number}")
        # Handle both 'id' (from database) and 'sale_id' (from checkout API)
        sale_id = bill_payload.get("sale_id") or bill_payload.get("id")
        if sale_id:
            lines.append(f"Sale ID: {sale_id}")
        lines.append(f"Date: {bill_payload.get('sold_at', 'N/A')}")
        lines.append(f"Payment: {str(bill_payload.get('payment_method') or 'cash').upper()}")
        if bill_payload.get("customer_name"):
            lines.append(f"Customer: {bill_payload.get('customer_name')}")
        if bill_payload.get("customer_phone"):
            lines.append(f"Phone: {bill_payload.get('customer_phone')}")
        lines.append("")

        for item in bill_payload.get("items", []):
            name = item.get('name', 'Unknown Item')
            qty = float(item.get('quantity', 0))
            unit_price = float(item.get('unit_price', 0))
            line_total = float(item.get('line_total', 0))
            lines.append(
                f"{name} x {qty:.2f} @ {unit_price:.2f} = {line_total:.2f}"
            )

        lines.append("------------------------------")
        lines.append(f"Total: INR {bill_payload.get('total_amount', 0):.2f}")
        return "\n".join(lines)

    def print_bill(self, bill_payload: dict) -> Path:
        """Save bill to file."""
        invoice_number = bill_payload.get("invoice_number")
        if not invoice_number:
            raise ValueError("Invoice number is required for printing.")

        target = self.output_dir / f"{invoice_number}.txt"
        bill_text = self._format_bill_text(bill_payload)
        target.write_text(bill_text, encoding="utf-8")
        return target

    def send_to_printer(self, bill_payload: dict, printer_name: str | None = None) -> str:
        """Send bill to physical printer on Windows.
        
        Args:
            bill_payload: Bill data dictionary
            printer_name: Name of printer (if None, uses default printer)
            
        Returns:
            Success message
            
        Raises:
            RuntimeError: If printer operation fails
        """
        try:
            bill_text = self._format_bill_text(bill_payload)
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp:
                tmp.write(bill_text)
                tmp_path = tmp.name
            
            try:
                # Use Windows print command
                if printer_name:
                    # Print to specific printer
                    cmd = f'print /d:"{printer_name}" "{tmp_path}"'
                else:
                    # Print to default printer
                    cmd = f'print "{tmp_path}"'
                
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                
                if result.returncode != 0:
                    raise RuntimeError(f"Print command failed: {result.stderr}")
                
                return f"Bill {bill_payload.get('invoice_number')} sent to printer successfully"
            finally:
                # Clean up temporary file
                Path(tmp_path).unlink(missing_ok=True)
                
        except subprocess.TimeoutExpired:
            raise RuntimeError("Printer operation timed out")
        except Exception as exc:
            raise RuntimeError(f"Failed to send bill to printer: {str(exc)}")

    def get_default_printer(self) -> str | None:
        """Get the default printer name on Windows."""
        try:
            result = subprocess.run(
                'wmic printconfig get name',
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    return lines[1].strip()
        except Exception:
            pass
        return None

    def list_available_printers(self) -> list[str]:
        """List all available printers on Windows."""
        try:
            result = subprocess.run(
                'wmic printer get name',
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                # Skip header and empty lines
                printers = [line.strip() for line in lines[1:] if line.strip()]
                return printers
        except Exception:
            pass
        return []
