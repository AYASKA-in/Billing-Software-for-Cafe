from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.database.connection import Database
from app.database.repository import Repository
from app.services.bookkeeping_service import BookkeepingService
from app.services.inventory_service import InventoryService
from app.services.print_service import PrintService
from app.services.report_service import ReportService
from app.services.sales_service import SalesService
from app.ui.main_window import MainWindow


def bootstrap() -> MainWindow:
    db_path = "data/cafe.db"
    db = Database(db_path=db_path)
    db.init_schema()

    repo = Repository(db)
    inventory_service = InventoryService(repo)
    sales_service = SalesService(db, repo)
    bookkeeping_service = BookkeepingService(repo)
    report_service = ReportService(repo)
    print_service = PrintService()

    return MainWindow(
        inventory_service=inventory_service,
        sales_service=sales_service,
        bookkeeping_service=bookkeeping_service,
        report_service=report_service,
        print_service=print_service,
        db_path=db_path,
    )


def main() -> int:
    app = QApplication(sys.argv)
    window = bootstrap()
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
