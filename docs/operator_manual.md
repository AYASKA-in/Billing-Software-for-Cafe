# Operator Manual (Cashier and Owner)

## 1. Login Role

1. Select role from Reports screen: cashier or admin.
2. Admin role requires PIN verification once at role switch.
3. Cashier role can run billing safely but sensitive operations ask for admin PIN.

## 2. Cashier Daily Flow

1. Open app and verify item list is loaded.
2. Billing tab:
   - search item or use cigarette quick buttons
   - adjust quantity and add to cart
   - use + Qty, - Qty, Remove Selected for corrections
3. Confirm total and click Generate Bill.
4. If printer fails, retry prompt appears.
5. Continue for next customer.

## 3. Inventory Basics

1. Add new item with sell/cost/stock/reorder.
2. Use Refresh Inventory after changes.
3. Sensitive changes:
   - update price
   - manual stock adjust
   - delete item
   These require admin permissions.

## 4. Purchases and Expenses

1. Purchases tab:
   - create lines
   - save purchase
   - edit old purchase only with admin approval
2. Expenses tab:
   - add expense
   - inline edit recent entries if needed

## 5. Reports and Exports

1. Reports screen is split into three tabs:
   - Overview: date filters, summary cards, trend, top items
   - Stock and Audit: low stock, stock movement ledger, audit log
   - Data Ops: close day, backup/restore, fixed costs, report exports
2. Set date range in Overview using Today, Last 7 Days, This Month, or custom dates.
3. Adjust limits:
   - Top Items limit in Overview
   - Ledger limit in Stock and Audit
4. Exports available in Data Ops:
   - CSV per section
   - Export All CSV
   - XLSX report (multi-sheet)
   - Printable Summary (text)

## 6. Backup and Restore

1. Backup Now creates immediate local backup.
2. Save Backup Schedule enables periodic automatic backups.
3. Restore Backup shows pre-check counts before overwrite.
4. Always restart app after successful restore.

## 7. Audit Log

1. Reports > Stock and Audit > Audit Log shows sensitive action history:
   - role switch
   - pricing edits
   - stock adjustments
   - purchase updates
   - deletes
   - restore operations
   - backup schedule updates
