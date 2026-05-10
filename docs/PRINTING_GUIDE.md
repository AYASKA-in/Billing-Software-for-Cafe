# Bill Printing Guide - CafePOS v1.2.4+

## Overview

The CafePOS application now includes **integrated printer support** for printing bills directly to your receipt printer or thermal printer on Windows.

## Features

✅ **Real-time Printing** - Automatic bill printing after checkout  
✅ **Reprint Bills** - Print any previous bill from the Recent Sales table  
✅ **Multiple Printer Support** - Automatic printer detection and selection  
✅ **Bill History** - All printed bills saved as text files in `data/printed_bills/`  
✅ **User-Friendly** - Printer selection dialog if multiple printers available  

## How It Works

### 1. **Automatic Printing During Checkout**

When you complete a sale:
1. Bill is automatically saved to the database
2. System attempts to print to the default printer
3. If printing fails, you're given an option to retry
4. Bill is always saved even if printing fails (important for reconciliation)

### 2. **Reprinting Previous Bills**

Navigate to the **Reports** tab and look for the **Recent Sales** section:

1. **Select a bill** from the "Recent Sales" table by clicking on any row
2. Click the **"🖨️ Print Selected Bill"** button
3. If multiple printers are available, choose which printer to use
4. Bill will be sent to the selected printer
5. Confirmation message shows when print completes

### 3. **Printer Setup**

#### Requirements:
- Windows 10/11 operating system
- Printer connected and set up in Windows
- Printer drivers installed and working

#### Setting Default Printer:
1. Go to **Settings > Devices > Printers & Scanners**
2. Click on your printer and select "Manage"
3. Click "Set as default"

The app will automatically use your default printer.

#### Changing Printers:
If you have multiple printers installed, the app will detect them. When you try to print:
- If only one printer exists: Uses it automatically
- If multiple printers exist: Shows a dialog to select which printer

## Bill Format

Printed bills include:
```
Cafe POS
------------------------------
Invoice: CAFE-000123
Sale ID: 456
Date: 2026-05-10 14:30:45
Payment: CASH
Customer: John Doe
Phone: 9876543210

Item Name x Qty @ Price = Total
Item Name 2 x Qty @ Price = Total
------------------------------
Total: INR 1,250.00
```

## Troubleshooting

### "No Printers Found"
- **Cause**: No printers detected on your system
- **Solution**: 
  1. Go to Windows Settings > Devices > Printers & Scanners
  2. Click "Add a printer or scanner"
  3. Select your printer and complete setup
  4. Restart CafePOS application

### "Print command failed"
- **Cause**: Printer driver issue or printer offline
- **Solution**:
  1. Check if printer is turned on and connected
  2. Verify printer cable/network connection
  3. Go to Settings > Devices > Printers & Scanners
  4. Click on your printer > "Open queue"
  5. Remove any stuck jobs
  6. Try printing again

### "Printer operation timed out"
- **Cause**: Printer is slow to respond or offline
- **Solution**:
  1. Verify printer is online
  2. Check printer for paper, toner/ink, and jams
  3. Restart printer
  4. Try printing again

### Bill saves but won't print
- **Good news**: Your bill is already saved in the database
- **Next steps**:
  1. Fix the printer issue
  2. Go to Reports tab
  3. Find the bill in Recent Sales
  4. Click "Print Selected Bill" to retry

## Technical Details

### PrintService Methods

```python
# Save bill to file (automatic during checkout)
print_service.print_bill(bill_payload)

# Send bill to printer (automatic or manual)
print_service.send_to_printer(bill_payload, printer_name=None)

# Get available printers
printers = print_service.list_available_printers()

# Get default printer
default = print_service.get_default_printer()
```

### Bill File Storage

All bills are saved to: `data/printed_bills/CAFE-000123.txt`

These files:
- Persist between application restarts
- Serve as backup records
- Can be opened in any text editor
- Help with reconciliation if printer issues occur

## Tips & Best Practices

1. **Set up a dedicated receipt printer** - Thermal printers (80mm or 58mm) are recommended
2. **Check paper regularly** - Low paper causes print failures
3. **Use standard bill paper** - Works best with 80x80mm thermal rolls
4. **Backup your data** - Bills are saved digitally even if printer fails
5. **Test print first** - Before your first customer, do a test transaction to verify everything works

## Audit Trail

Every bill print action is logged in the Audit Log for tracking:
- Who printed the bill
- When it was printed
- Which bill was printed
- Printer status

Access audit logs in the **Data Ops** tab > **Audit Log** section.

## Support

If you encounter issues:
1. Check the **Troubleshooting** section above
2. Verify printer is set up in Windows
3. Check application logs in `data/printed_bills/` folder
4. Document the error message and printer model for support

---

**Last Updated**: May 2026  
**Version**: 1.2.4+  
**Platform**: Windows 10/11
