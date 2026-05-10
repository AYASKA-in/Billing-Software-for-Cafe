# Bill Printing - Quick Reference

## For Users

### Print Bills in 3 Steps:

1. **After Checkout** - Bill automatically prints to default printer
2. **Reprint from Reports Tab** - Select bill from "Recent Sales" table and click "🖨️ Print Selected Bill"
3. **Multiple Printers** - If you have multiple printers, app will let you choose

### Printer Setup:
- Windows automatically detects printers
- Set default printer in: Settings > Devices > Printers & Scanners
- App uses Windows default printer

---

## For Developers

### PrintService API

**New Methods:**

```python
# Send bill to physical printer
send_to_printer(bill_payload: dict, printer_name: str | None = None) -> str

# Get list of available printers
list_available_printers() -> list[str]

# Get default Windows printer
get_default_printer() -> str | None

# Internal: Format bill text
_format_bill_text(bill_payload: dict) -> str
```

**Usage:**

```python
# Print to default printer
msg = print_service.send_to_printer(bill_data)

# Print to specific printer
msg = print_service.send_to_printer(bill_data, printer_name="HP LaserJet")

# List printers and choose one
printers = print_service.list_available_printers()
print_service.send_to_printer(bill_data, printer_name=printers[0])
```

### MainWindow API

**New Methods:**

```python
# Handler for print button in Recent Sales
print_selected_bill() -> None
```

**Button location:** Reports Tab > Recent Sales section

### File Structure

```
app/
├── services/
│   └── print_service.py (ENHANCED)
│       ├── print_bill()          [existing - saves to file]
│       ├── send_to_printer()     [NEW - Windows printing]
│       ├── list_available_printers() [NEW]
│       └── get_default_printer() [NEW]
│
├── ui/
│   └── main_window.py (ENHANCED)
│       ├── print_selected_bill() [NEW - UI handler]
│       └── print_selected_bill_btn [NEW - UI button]

data/
├── printed_bills/               [directory for saved bills]
│   ├── CAFE-000001.txt
│   ├── CAFE-000002.txt
│   └── ...
```

### Flow Diagram

```
Checkout Flow:
User clicks Pay → checkout() → sales_service.checkout() 
  → print_service.print_bill() [saves .txt file]
  → _print_with_retry() → print_service.send_to_printer()
  → Success Message

Reprint Flow:
User selects bill in Reports → print_selected_bill()
  → list_available_printers()
  → [if multiple: show dialog]
  → send_to_printer() → Success Message
```

### Technology

- **Windows API**: `subprocess` with `print` command
- **Printer Detection**: `wmic printer get name` (WMI)
- **Default Printer**: `wmic printconfig get name` (WMI)
- **File Generation**: Temporary files auto-cleaned

### Error Handling

All printer operations wrapped in try-catch with user-friendly error messages:
- "No Printers Found" → Guide to Windows Settings
- "Print command failed" → Suggests checking printer
- "Printer operation timed out" → Suggests restarting printer

### Audit Logging

Each print action logged to audit trail:
```python
self._log_audit("bill_print", "sale", str(sale_id), invoice_number)
```

---

## Testing

### Unit Test Template

```python
def test_print_service_send_to_printer():
    service = PrintService()
    
    # Test with valid bill payload
    bill = {
        "invoice_number": "CAFE-000001",
        "sale_id": 1,
        "total_amount": 500.0,
        "items": [{"name": "Coffee", "quantity": 1, ...}],
        ...
    }
    
    # Get available printers
    printers = service.list_available_printers()
    if printers:
        result = service.send_to_printer(bill, printers[0])
        assert "success" in result.lower()

def test_list_available_printers():
    service = PrintService()
    printers = service.list_available_printers()
    assert isinstance(printers, list)

def test_get_default_printer():
    service = PrintService()
    default = service.get_default_printer()
    assert default is None or isinstance(default, str)
```

### Manual Testing Checklist

- [ ] App starts without errors
- [ ] "Print Selected Bill" button appears in Reports tab
- [ ] Can detect system printers (check by attempting print)
- [ ] Automatic printing works on checkout
- [ ] Reprint from Recent Sales works
- [ ] Multiple printer selection dialog appears if multiple printers exist
- [ ] Bill files saved to `data/printed_bills/` directory
- [ ] Audit log records print actions

---

## Future Enhancements

1. **ESC/POS Support** - For thermal receipt printers (specialized hardware)
2. **Network Printers** - Better support for IP-based printers
3. **Print Settings** - Let user configure margins, fonts, copies
4. **Print Preview** - Show preview before sending to printer
5. **Scheduled Reprints** - Auto-print bills at specific times
6. **Cloud Printing** - Google Cloud Print integration

---

**Version**: 1.0  
**Status**: Production Ready  
**Platform**: Windows 10/11  
**Date**: May 2026
