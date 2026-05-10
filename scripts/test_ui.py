from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PySide6.QtWidgets import QApplication

from app.database.connection import Database
from app.database.repository import Repository
from app.services.bookkeeping_service import BookkeepingService
from app.services.inventory_service import InventoryService
from app.services.print_service import PrintService
from app.services.report_service import ReportService
from app.services.sales_service import SalesService
from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    db_path = Path(tempfile.gettempdir()) / "cafe_pos_ui_smoke_tmp.db"
    if db_path.exists():
        db_path.unlink()

    db = Database(str(db_path))
    db.init_schema()
    repo = Repository(db)
    window = MainWindow(
        inventory_service=InventoryService(repo),
        sales_service=SalesService(db, repo),
        bookkeeping_service=BookkeepingService(repo),
        report_service=ReportService(repo),
        print_service=PrintService(str(ROOT_DIR / "data" / "printed_bills_ui_smoke")),
        db_path=str(db_path),
    )
    window.show()
    window._switch_page(1)
    QApplication.processEvents()
    time.sleep(0.5)
    QApplication.processEvents()

    output_path = Path(tempfile.gettempdir()) / "cafe_pos_recipes_tab.png"
    window.grab().save(str(output_path))
    print(f"Screenshot saved to {output_path}")
    window.close()
    if db_path.exists():
        db_path.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
