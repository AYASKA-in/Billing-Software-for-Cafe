# Troubleshooting Guide

## 1. App does not start

1. Confirm virtual environment is active.
2. Run: python -m compileall app main.py
3. Check data file path exists: data/cafe.db

## 2. Backup/Restore issues

1. If restore fails, verify selected file is a valid .db backup.
2. Use restore pre-check counts to confirm expected data volume.
3. Use Reports > Data Ops for Backup Now, Export DB Backup, and Restore DB Backup actions.
4. Restart app after restore.

## 3. Export issues

1. CSV export: verify destination path permissions.
2. XLSX export requires openpyxl in environment.
   - install using: pip install openpyxl
3. Use Reports > Data Ops for Export CSV, Export XLSX, Export All CSV, and Print Summary.

## 4. Printer issues

1. Sale is saved before print attempt.
2. If print fails, use retry prompt.
3. Printed files are saved under data/printed_bills.

## 5. Stock mismatch checks

1. Review Stock Movement Ledger in Reports > Stock and Audit.
2. Confirm purchase edits were applied correctly.
3. Use Manual Stock Adjust with reason notes for corrections.

## 6. Release build issues

1. Run hard smoke first:
   - python scripts/hard_smoke.py
2. Run release:
   - powershell -ExecutionPolicy Bypass -File scripts/release.ps1 -Version 1.0.1
3. If installer missing, ensure Inno Setup is installed.

## 7. If data seems wrong after edits

1. Check Reports > Stock and Audit > Audit Log for who/what/when.
2. Restore from latest valid backup if needed.
3. Re-run hard smoke on a temporary DB to verify app logic.
