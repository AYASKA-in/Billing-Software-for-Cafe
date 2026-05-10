from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.config import load_app_settings, load_version
from app.database.connection import Database
from app.database.repository import Repository
from app.services.bookkeeping_service import BookkeepingService
from app.services.inventory_service import InventoryService
from app.services.print_service import PrintService
from app.services.report_service import ReportService
from app.services.sales_service import SalesService
from app.ui.main_window import MainWindow


def _runtime_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def bootstrap() -> MainWindow:
    app_dir = _runtime_app_dir()
    os.chdir(app_dir)
    app_settings = load_app_settings(app_dir)
    app_version = load_version(app_dir)
    db_path = str(app_dir / "data" / "cafe.db")
    db = Database(db_path=db_path)
    db.init_schema()

    repo = Repository(db)
    repo.set_setting("invoice_prefix", app_settings.billing.invoice_prefix)
    if repo.get_setting("admin_pin_hash") is None:
        repo.set_admin_pin(app_settings.default_admin_pin)
    repo.set_setting("shop_name", app_settings.shop_name)
    repo.set_setting("currency", app_settings.currency)
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
        app_version=app_version,
    )


def main() -> int:
    if sys.platform.startswith("win"):
        app_version = load_version(_runtime_app_dir())
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            f"BreakTime.CafePOS.{app_version}"
        )
    app = QApplication(sys.argv)
    window = bootstrap()
    if getattr(window, "_activation_failed", False):
        return 0
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
