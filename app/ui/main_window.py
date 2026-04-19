from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSpinBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.bookkeeping_service import BookkeepingService
from app.services.inventory_service import InventoryService
from app.services.print_service import PrintService
from app.services.report_service import ReportService
from app.services.sales_service import SalesService
from app.utils.backup import create_backup, export_backup, inspect_backup_counts, restore_backup


class MainWindow(QMainWindow):
    def __init__(
        self,
        inventory_service: InventoryService,
        sales_service: SalesService,
        bookkeeping_service: BookkeepingService,
        report_service: ReportService,
        print_service: PrintService,
        db_path: str = "data/cafe.db",
    ) -> None:
        super().__init__()
        self.inventory_service = inventory_service
        self.sales_service = sales_service
        self.bookkeeping_service = bookkeeping_service
        self.report_service = report_service
        self.print_service = print_service
        self.db_path = db_path

        self.cart: dict[int, dict] = {}
        self.billing_items_cache: list[dict] = []
        self.cigarette_shortcuts: list[QShortcut] = []
        self.purchase_cart: list[dict] = []
        self.purchase_item_cache: dict[int, dict] = {}
        self.editing_purchase_id: int | None = None
        self.current_role = (self.bookkeeping_service.get_setting("current_role", "cashier") or "cashier").lower()
        self._updating_inventory_table = False
        self._updating_purchase_table = False
        self._updating_expense_table = False
        self.cart_file = Path("data/pending_cart.json")

        self.setWindowTitle("Cafe POS and Bookkeeping")
        self.resize(1320, 820)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.billing_tab = self._build_billing_tab()
        self.inventory_tab = self._build_inventory_tab()
        self.purchases_tab = self._build_purchases_tab()
        self.expenses_tab = self._build_expenses_tab()
        self.reports_tab = self._build_reports_tab()

        self.tabs.addTab(self.billing_tab, "Billing")
        self.tabs.addTab(self.inventory_tab, "Inventory")
        self.tabs.addTab(self.purchases_tab, "Purchases")
        self.tabs.addTab(self.expenses_tab, "Expenses")
        self.tabs.addTab(self.reports_tab, "Reports")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self._wire_shortcuts()

        self.cart_timer = QTimer(self)
        self.cart_timer.setInterval(5000)
        self.cart_timer.timeout.connect(self._save_pending_cart)
        self.cart_timer.start()

        self.auto_backup_timer = QTimer(self)
        self.auto_backup_timer.timeout.connect(self._run_scheduled_backup)
        self._configure_auto_backup_timer()

        self.refresh_all()
        self._load_pending_cart()

    def _on_tab_changed(self, tab_index: int) -> None:
        if tab_index == 0:
            self.refresh_billing_items()
        elif tab_index == 1:
            self.refresh_inventory()
        elif tab_index == 2:
            self.refresh_purchases_tab()
        elif tab_index == 3:
            self.refresh_expenses_tab()
        elif tab_index == 4:
            self.refresh_reports()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "top_items_table"):
            self._apply_report_table_width_profiles()

    def _wire_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.checkout)
        QShortcut(QKeySequence("F5"), self, activated=self.refresh_all)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.close_day)

    def _build_placeholder_tab(self, message: str) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        return tab

    def _build_billing_tab(self) -> QWidget:
        tab = QWidget()
        root_layout = QVBoxLayout(tab)

        splitter = QSplitter(Qt.Horizontal)

        catalog_group = QGroupBox("Item Catalog")
        catalog_layout = QVBoxLayout(catalog_group)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search item name...")
        self.search_input.textChanged.connect(self.apply_billing_filter)
        self.search_input.returnPressed.connect(self.add_selected_item_to_cart)
        search_row.addWidget(QLabel("Search"))
        search_row.addWidget(self.search_input)
        catalog_layout.addLayout(search_row)

        self.billing_items_table = QTableWidget(0, 4)
        self.billing_items_table.setHorizontalHeaderLabels(["ID", "Name", "Price", "Stock"])
        self.billing_items_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.billing_items_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.billing_items_table.horizontalHeader().setStretchLastSection(True)
        self.billing_items_table.cellDoubleClicked.connect(self._on_catalog_double_click)

        controls = QHBoxLayout()
        self.qty_spin = QDoubleSpinBox()
        self.qty_spin.setDecimals(2)
        self.qty_spin.setMinimum(0.01)
        self.qty_spin.setMaximum(1000)
        self.qty_spin.setValue(1)

        add_btn = QPushButton("Add to Cart (Enter)")
        add_btn.clicked.connect(self.add_selected_item_to_cart)

        refresh_btn = QPushButton("Refresh Items")
        refresh_btn.clicked.connect(self.refresh_billing_items)

        controls.addWidget(QLabel("Qty"))
        controls.addWidget(self.qty_spin)
        controls.addWidget(add_btn)
        controls.addWidget(refresh_btn)

        quick_group = QGroupBox("Cigarette Quick Add")
        quick_layout = QVBoxLayout(quick_group)

        self.small_buttons_layout = QHBoxLayout()
        self.medium_buttons_layout = QHBoxLayout()
        self.big_buttons_layout = QHBoxLayout()

        quick_layout.addWidget(QLabel("SMALL (INR 10-15)"))
        quick_layout.addLayout(self.small_buttons_layout)
        quick_layout.addWidget(QLabel("MEDIUM (INR 18-22)"))
        quick_layout.addLayout(self.medium_buttons_layout)
        quick_layout.addWidget(QLabel("BIG (INR 25-30)"))
        quick_layout.addLayout(self.big_buttons_layout)

        catalog_layout.addWidget(self.billing_items_table)
        catalog_layout.addLayout(controls)
        catalog_layout.addWidget(quick_group)

        cart_group = QGroupBox("Current Bill")
        cart_layout = QVBoxLayout(cart_group)

        self.cart_table = QTableWidget(0, 5)
        self.cart_table.setHorizontalHeaderLabels(["Item ID", "Name", "Qty", "Unit", "Line Total"])
        self.cart_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cart_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cart_table.horizontalHeader().setStretchLastSection(True)

        cart_actions_row = QHBoxLayout()
        plus_qty_btn = QPushButton("+ Qty")
        plus_qty_btn.clicked.connect(self.increase_selected_cart_item_qty)

        minus_qty_btn = QPushButton("- Qty")
        minus_qty_btn.clicked.connect(self.decrease_selected_cart_item_qty)

        remove_selected_btn = QPushButton("Remove Selected")
        remove_selected_btn.clicked.connect(self.remove_selected_cart_item)

        cart_actions_row.addWidget(plus_qty_btn)
        cart_actions_row.addWidget(minus_qty_btn)
        cart_actions_row.addWidget(remove_selected_btn)
        cart_actions_row.addStretch()

        totals_row = QHBoxLayout()
        self.total_label = QLabel("Total: INR 0.00")
        self.total_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        clear_btn = QPushButton("Clear Cart")
        clear_btn.clicked.connect(self.clear_cart)

        checkout_btn = QPushButton("Generate Bill (Ctrl+Enter)")
        checkout_btn.clicked.connect(self.checkout)

        totals_row.addWidget(self.total_label)
        totals_row.addStretch()
        totals_row.addWidget(clear_btn)
        totals_row.addWidget(checkout_btn)

        cart_layout.addWidget(self.cart_table)
        cart_layout.addLayout(cart_actions_row)
        cart_layout.addLayout(totals_row)

        splitter.addWidget(catalog_group)
        splitter.addWidget(cart_group)
        splitter.setSizes([700, 550])

        root_layout.addWidget(splitter)
        return tab

    def _build_inventory_tab(self) -> QWidget:
        tab = QWidget()
        root_layout = QVBoxLayout(tab)

        form_group = QGroupBox("Add New Item")
        form_layout = QGridLayout(form_group)

        self.item_name_input = QLineEdit()
        self.category_combo = QComboBox()

        self.sell_price_spin = QDoubleSpinBox()
        self.sell_price_spin.setMaximum(100000)
        self.sell_price_spin.setPrefix("INR ")

        self.cost_price_spin = QDoubleSpinBox()
        self.cost_price_spin.setMaximum(100000)
        self.cost_price_spin.setPrefix("INR ")

        self.stock_spin = QDoubleSpinBox()
        self.stock_spin.setMaximum(100000)

        self.reorder_spin = QDoubleSpinBox()
        self.reorder_spin.setMaximum(100000)

        add_item_btn = QPushButton("Add Item")
        add_item_btn.clicked.connect(self.add_inventory_item)

        form_layout.addWidget(QLabel("Name"), 0, 0)
        form_layout.addWidget(self.item_name_input, 0, 1)
        form_layout.addWidget(QLabel("Category"), 0, 2)
        form_layout.addWidget(self.category_combo, 0, 3)

        form_layout.addWidget(QLabel("Selling Price"), 1, 0)
        form_layout.addWidget(self.sell_price_spin, 1, 1)
        form_layout.addWidget(QLabel("Cost Price"), 1, 2)
        form_layout.addWidget(self.cost_price_spin, 1, 3)

        form_layout.addWidget(QLabel("Opening Stock"), 2, 0)
        form_layout.addWidget(self.stock_spin, 2, 1)
        form_layout.addWidget(QLabel("Reorder Level"), 2, 2)
        form_layout.addWidget(self.reorder_spin, 2, 3)

        form_layout.addWidget(add_item_btn, 3, 3)

        self.inventory_items_table = QTableWidget(0, 6)
        self.inventory_items_table.setHorizontalHeaderLabels(
            ["ID", "Name", "Category", "Sell", "Stock", "Reorder"]
        )
        self.inventory_items_table.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.SelectedClicked | QTableWidget.EditKeyPressed
        )
        self.inventory_items_table.itemChanged.connect(self._on_inventory_item_changed)
        self.inventory_items_table.horizontalHeader().setStretchLastSection(True)

        inventory_hint = QLabel(
            "Tip: Double-click Sell/Reorder to edit inline. Admin PIN is required for each save."
        )

        action_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Inventory")
        refresh_btn.clicked.connect(self.refresh_inventory)

        export_inventory_btn = QPushButton("Export CSV")
        export_inventory_btn.clicked.connect(self.export_inventory_csv)

        update_price_btn = QPushButton("Update Price (Admin PIN)")
        update_price_btn.clicked.connect(self.update_selected_item_price)

        adjust_stock_btn = QPushButton("Manual Stock Adjust (Admin PIN)")
        adjust_stock_btn.clicked.connect(self.adjust_selected_item_stock)

        delete_item_btn = QPushButton("Delete Item (Admin PIN)")
        delete_item_btn.clicked.connect(self.delete_selected_item)

        load_starter_btn = QPushButton("Load Starter Cigarette SKUs")
        load_starter_btn.clicked.connect(self.load_starter_cigarettes)

        action_row.addWidget(refresh_btn)
        action_row.addWidget(export_inventory_btn)
        action_row.addWidget(update_price_btn)
        action_row.addWidget(adjust_stock_btn)
        action_row.addWidget(delete_item_btn)
        action_row.addWidget(load_starter_btn)
        action_row.addStretch()

        root_layout.addWidget(form_group)
        root_layout.addWidget(inventory_hint)
        root_layout.addWidget(self.inventory_items_table)
        root_layout.addLayout(action_row)

        return tab

    def _build_purchases_tab(self) -> QWidget:
        tab = QWidget()
        root_layout = QVBoxLayout(tab)

        entry_box = QGroupBox("Record Purchase")
        entry_layout = QGridLayout(entry_box)

        self.purchase_supplier_input = QLineEdit()
        self.purchase_notes_input = QLineEdit()
        self.purchase_item_combo = QComboBox()
        self.purchase_item_combo.currentIndexChanged.connect(self._on_purchase_item_changed)
        self.purchase_qty_spin = QDoubleSpinBox()
        self.purchase_qty_spin.setDecimals(2)
        self.purchase_qty_spin.setMinimum(0.01)
        self.purchase_qty_spin.setMaximum(100000)
        self.purchase_qty_spin.setValue(1)

        self.purchase_cost_spin = QDoubleSpinBox()
        self.purchase_cost_spin.setDecimals(2)
        self.purchase_cost_spin.setMinimum(0)
        self.purchase_cost_spin.setMaximum(100000)
        self.purchase_cost_spin.setPrefix("INR ")

        add_line_btn = QPushButton("Add Line")
        add_line_btn.clicked.connect(self.add_purchase_line)

        save_purchase_btn = QPushButton("Save Purchase")
        self.save_purchase_btn = save_purchase_btn
        save_purchase_btn.clicked.connect(self.save_purchase)

        cancel_edit_btn = QPushButton("Cancel Edit")
        self.cancel_purchase_edit_btn = cancel_edit_btn
        self.cancel_purchase_edit_btn.setEnabled(False)
        cancel_edit_btn.clicked.connect(self.cancel_purchase_edit)

        clear_lines_btn = QPushButton("Clear Lines")
        clear_lines_btn.clicked.connect(self.clear_purchase_lines)

        remove_line_btn = QPushButton("Remove Selected Line")
        remove_line_btn.clicked.connect(self.remove_selected_purchase_line)

        modify_saved_btn = QPushButton("Modify Selected Purchase (Admin PIN)")
        modify_saved_btn.clicked.connect(self.load_selected_purchase_for_edit)

        entry_layout.addWidget(QLabel("Supplier"), 0, 0)
        entry_layout.addWidget(self.purchase_supplier_input, 0, 1)
        entry_layout.addWidget(QLabel("Notes"), 0, 2)
        entry_layout.addWidget(self.purchase_notes_input, 0, 3)

        entry_layout.addWidget(QLabel("Item"), 1, 0)
        entry_layout.addWidget(self.purchase_item_combo, 1, 1)
        entry_layout.addWidget(QLabel("Qty"), 1, 2)
        entry_layout.addWidget(self.purchase_qty_spin, 1, 3)

        entry_layout.addWidget(QLabel("Cost Price"), 2, 0)
        entry_layout.addWidget(self.purchase_cost_spin, 2, 1)
        entry_layout.addWidget(add_line_btn, 2, 2)
        entry_layout.addWidget(remove_line_btn, 2, 3)

        entry_layout.addWidget(clear_lines_btn, 3, 2)
        entry_layout.addWidget(save_purchase_btn, 3, 3)
        entry_layout.addWidget(cancel_edit_btn, 4, 3)

        self.purchase_lines_table = QTableWidget(0, 5)
        self.purchase_lines_table.setHorizontalHeaderLabels(
            ["Item ID", "Name", "Qty", "Cost", "Line Total"]
        )
        self.purchase_lines_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.purchase_lines_table.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.SelectedClicked | QTableWidget.EditKeyPressed
        )
        self.purchase_lines_table.itemChanged.connect(self._on_purchase_line_item_changed)
        self.purchase_lines_table.horizontalHeader().setStretchLastSection(True)

        self.purchase_total_label = QLabel("Purchase Total: INR 0.00")
        self.purchase_total_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.purchase_mode_label = QLabel("Mode: New Purchase")
        self.purchase_mode_label.setStyleSheet("font-weight: bold;")
        purchase_hint = QLabel("Tip: Double-click Qty/Cost in a line to edit inline before saving purchase.")

        history_box = QGroupBox("Recent Purchases")
        history_layout = QVBoxLayout(history_box)
        self.purchase_history_table = QTableWidget(0, 6)
        self.purchase_history_table.setHorizontalHeaderLabels(
            ["ID", "Supplier", "Date", "Lines", "Total", "Notes"]
        )
        self.purchase_history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.purchase_history_table.horizontalHeader().setStretchLastSection(True)
        history_layout.addWidget(self.purchase_history_table)

        history_actions = QHBoxLayout()
        history_actions.addWidget(modify_saved_btn)
        history_actions.addStretch()
        history_layout.addLayout(history_actions)

        filter_box = QGroupBox("Purchase Date Filter")
        filter_layout = QHBoxLayout(filter_box)
        self.purchase_from_date = QDateEdit()
        self.purchase_from_date.setCalendarPopup(True)
        self.purchase_from_date.setDisplayFormat("yyyy-MM-dd")
        self.purchase_from_date.setDate(QDate.currentDate())

        self.purchase_to_date = QDateEdit()
        self.purchase_to_date.setCalendarPopup(True)
        self.purchase_to_date.setDisplayFormat("yyyy-MM-dd")
        self.purchase_to_date.setDate(QDate.currentDate())

        p_today_btn = QPushButton("Today")
        p_today_btn.clicked.connect(
            lambda: self._apply_quick_range(
                self.purchase_from_date,
                self.purchase_to_date,
                "today",
                self.refresh_purchases_tab,
            )
        )
        p_7d_btn = QPushButton("Last 7 Days")
        p_7d_btn.clicked.connect(
            lambda: self._apply_quick_range(
                self.purchase_from_date,
                self.purchase_to_date,
                "last7",
                self.refresh_purchases_tab,
            )
        )
        p_month_btn = QPushButton("This Month")
        p_month_btn.clicked.connect(
            lambda: self._apply_quick_range(
                self.purchase_from_date,
                self.purchase_to_date,
                "month",
                self.refresh_purchases_tab,
            )
        )
        p_custom_btn = QPushButton("Custom")
        p_custom_btn.clicked.connect(self.refresh_purchases_tab)
        p_apply_btn = QPushButton("Apply")
        p_apply_btn.clicked.connect(self.refresh_purchases_tab)

        filter_layout.addWidget(QLabel("From"))
        filter_layout.addWidget(self.purchase_from_date)
        filter_layout.addWidget(QLabel("To"))
        filter_layout.addWidget(self.purchase_to_date)
        filter_layout.addWidget(p_today_btn)
        filter_layout.addWidget(p_7d_btn)
        filter_layout.addWidget(p_month_btn)
        filter_layout.addWidget(p_custom_btn)
        filter_layout.addWidget(p_apply_btn)
        filter_layout.addStretch()

        refresh_btn = QPushButton("Refresh Purchases")
        refresh_btn.clicked.connect(self.refresh_purchases_tab)

        export_purchases_btn = QPushButton("Export CSV")
        export_purchases_btn.clicked.connect(self.export_purchases_csv)

        root_layout.addWidget(entry_box)
        root_layout.addWidget(self.purchase_mode_label)
        root_layout.addWidget(purchase_hint)
        root_layout.addWidget(self.purchase_lines_table)
        root_layout.addWidget(self.purchase_total_label)
        root_layout.addWidget(filter_box)
        root_layout.addWidget(history_box)
        root_layout.addWidget(export_purchases_btn)
        root_layout.addWidget(refresh_btn)
        return tab

    def _build_expenses_tab(self) -> QWidget:
        tab = QWidget()
        root_layout = QVBoxLayout(tab)

        entry_box = QGroupBox("Record Expense")
        form_layout = QGridLayout(entry_box)

        self.expense_type_combo = QComboBox()
        self.expense_type_combo.setEditable(True)
        self.expense_type_combo.addItems(["Rent", "Electricity", "Wages", "Misc"])

        self.expense_amount_spin = QDoubleSpinBox()
        self.expense_amount_spin.setDecimals(2)
        self.expense_amount_spin.setMinimum(0.01)
        self.expense_amount_spin.setMaximum(10000000)
        self.expense_amount_spin.setPrefix("INR ")

        self.expense_notes_input = QLineEdit()

        add_expense_btn = QPushButton("Add Expense")
        add_expense_btn.clicked.connect(self.add_expense)

        form_layout.addWidget(QLabel("Type"), 0, 0)
        form_layout.addWidget(self.expense_type_combo, 0, 1)
        form_layout.addWidget(QLabel("Amount"), 0, 2)
        form_layout.addWidget(self.expense_amount_spin, 0, 3)
        form_layout.addWidget(QLabel("Notes"), 1, 0)
        form_layout.addWidget(self.expense_notes_input, 1, 1, 1, 3)
        form_layout.addWidget(add_expense_btn, 2, 3)

        history_box = QGroupBox("Recent Expenses")
        history_layout = QVBoxLayout(history_box)
        self.expense_history_table = QTableWidget(0, 5)
        self.expense_history_table.setHorizontalHeaderLabels(["ID", "Type", "Amount", "Date", "Notes"])
        self.expense_history_table.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.SelectedClicked | QTableWidget.EditKeyPressed
        )
        self.expense_history_table.itemChanged.connect(self._on_expense_item_changed)
        self.expense_history_table.horizontalHeader().setStretchLastSection(True)
        history_layout.addWidget(self.expense_history_table)

        expense_hint = QLabel("Tip: Double-click Type, Amount, or Notes in Recent Expenses to edit inline.")

        filter_box = QGroupBox("Expense Date Filter")
        filter_layout = QHBoxLayout(filter_box)
        self.expense_from_date = QDateEdit()
        self.expense_from_date.setCalendarPopup(True)
        self.expense_from_date.setDisplayFormat("yyyy-MM-dd")
        self.expense_from_date.setDate(QDate.currentDate())

        self.expense_to_date = QDateEdit()
        self.expense_to_date.setCalendarPopup(True)
        self.expense_to_date.setDisplayFormat("yyyy-MM-dd")
        self.expense_to_date.setDate(QDate.currentDate())

        e_today_btn = QPushButton("Today")
        e_today_btn.clicked.connect(
            lambda: self._apply_quick_range(
                self.expense_from_date,
                self.expense_to_date,
                "today",
                self.refresh_expenses_tab,
            )
        )
        e_7d_btn = QPushButton("Last 7 Days")
        e_7d_btn.clicked.connect(
            lambda: self._apply_quick_range(
                self.expense_from_date,
                self.expense_to_date,
                "last7",
                self.refresh_expenses_tab,
            )
        )
        e_month_btn = QPushButton("This Month")
        e_month_btn.clicked.connect(
            lambda: self._apply_quick_range(
                self.expense_from_date,
                self.expense_to_date,
                "month",
                self.refresh_expenses_tab,
            )
        )
        e_custom_btn = QPushButton("Custom")
        e_custom_btn.clicked.connect(self.refresh_expenses_tab)
        e_apply_btn = QPushButton("Apply")
        e_apply_btn.clicked.connect(self.refresh_expenses_tab)

        filter_layout.addWidget(QLabel("From"))
        filter_layout.addWidget(self.expense_from_date)
        filter_layout.addWidget(QLabel("To"))
        filter_layout.addWidget(self.expense_to_date)
        filter_layout.addWidget(e_today_btn)
        filter_layout.addWidget(e_7d_btn)
        filter_layout.addWidget(e_month_btn)
        filter_layout.addWidget(e_custom_btn)
        filter_layout.addWidget(e_apply_btn)
        filter_layout.addStretch()

        refresh_btn = QPushButton("Refresh Expenses")
        refresh_btn.clicked.connect(self.refresh_expenses_tab)

        export_expenses_btn = QPushButton("Export CSV")
        export_expenses_btn.clicked.connect(self.export_expenses_csv)

        root_layout.addWidget(entry_box)
        root_layout.addWidget(expense_hint)
        root_layout.addWidget(filter_box)
        root_layout.addWidget(history_box)
        root_layout.addWidget(export_expenses_btn)
        root_layout.addWidget(refresh_btn)
        return tab

    def _build_reports_tab(self) -> QWidget:
        tab = QWidget()
        root_layout = QVBoxLayout(tab)

        title = QLabel("Operations Dashboard")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #e0e0e0;")

        subtitle = QLabel("Live performance snapshot for sales, stock, and profitability")
        subtitle.setStyleSheet("color: #9ea7b8;")

        cards_grid = QGridLayout()
        cards_grid.setHorizontalSpacing(10)
        cards_grid.setVerticalSpacing(10)

        sales_card, self.sales_value = self._make_report_metric_card("Sales", "#4caf50")
        cogs_card, self.cogs_value = self._make_report_metric_card("COGS", "#ffb74d")
        gross_card, self.gross_profit_value = self._make_report_metric_card("Gross Profit", "#64b5f6")
        purchases_card, self.purchases_value = self._make_report_metric_card("Purchases", "#9575cd")
        expenses_card, self.expenses_value = self._make_report_metric_card("Expenses", "#ef5350")
        fixed_daily_card, self.fixed_daily_value = self._make_report_metric_card("Fixed Cost / Day", "#ff7043")
        net_card, self.net_value = self._make_report_metric_card("Realistic Daily Profit", "#26c6da")

        metric_cards = [
            sales_card,
            cogs_card,
            gross_card,
            purchases_card,
            expenses_card,
            fixed_daily_card,
            net_card,
        ]
        for index, card in enumerate(metric_cards):
            row = index // 4
            col = index % 4
            cards_grid.addWidget(card, row, col)
        for col in range(4):
            cards_grid.setColumnStretch(col, 1)

        fixed_cost_box = QGroupBox("Monthly Fixed Costs (Auto-divided daily)")
        fixed_cost_layout = QGridLayout(fixed_cost_box)

        self.rent_spin = QDoubleSpinBox()
        self.rent_spin.setPrefix("INR ")
        self.rent_spin.setMaximum(100000000)

        self.salary_spin = QDoubleSpinBox()
        self.salary_spin.setPrefix("INR ")
        self.salary_spin.setMaximum(100000000)

        self.maintenance_spin = QDoubleSpinBox()
        self.maintenance_spin.setPrefix("INR ")
        self.maintenance_spin.setMaximum(100000000)

        self.electricity_spin = QDoubleSpinBox()
        self.electricity_spin.setPrefix("INR ")
        self.electricity_spin.setMaximum(100000000)

        self.monthly_fixed_total_label = QLabel("Monthly Fixed Total: INR 0.00")
        self.monthly_fixed_total_label.setStyleSheet("font-weight: bold;")

        save_fixed_btn = QPushButton("Save Fixed Costs")
        save_fixed_btn.clicked.connect(self.save_monthly_fixed_costs)

        fixed_cost_layout.addWidget(QLabel("Rent"), 0, 0)
        fixed_cost_layout.addWidget(self.rent_spin, 0, 1)
        fixed_cost_layout.addWidget(QLabel("Salaries"), 0, 2)
        fixed_cost_layout.addWidget(self.salary_spin, 0, 3)

        fixed_cost_layout.addWidget(QLabel("Maintenance"), 1, 0)
        fixed_cost_layout.addWidget(self.maintenance_spin, 1, 1)
        fixed_cost_layout.addWidget(QLabel("Electricity"), 1, 2)
        fixed_cost_layout.addWidget(self.electricity_spin, 1, 3)

        fixed_cost_layout.addWidget(self.monthly_fixed_total_label, 2, 0, 1, 3)
        fixed_cost_layout.addWidget(save_fixed_btn, 2, 3)

        backup_automation_box = QGroupBox("Backup Automation")
        backup_auto_layout = QHBoxLayout(backup_automation_box)
        self.auto_backup_enabled_checkbox = QCheckBox("Enable scheduled backup")
        self.auto_backup_interval_spin = QSpinBox()
        self.auto_backup_interval_spin.setRange(5, 1440)
        self.auto_backup_interval_spin.setSuffix(" min")
        auto_backup_save_btn = QPushButton("Save Backup Schedule")
        auto_backup_save_btn.clicked.connect(self.save_backup_preferences)
        backup_auto_layout.addWidget(self.auto_backup_enabled_checkbox)
        backup_auto_layout.addWidget(QLabel("Interval"))
        backup_auto_layout.addWidget(self.auto_backup_interval_spin)
        backup_auto_layout.addWidget(auto_backup_save_btn)
        backup_auto_layout.addStretch()

        trend_box = QGroupBox("Sales Trend (Selected Range)")
        trend_layout = QVBoxLayout(trend_box)
        self.sales_trend_table = QTableWidget(0, 5)
        self.sales_trend_table.setHorizontalHeaderLabels(
            ["Date", "Bills", "Sales", "COGS", "Gross Profit"]
        )
        self._style_report_table(self.sales_trend_table)
        self._apply_report_column_modes(
            self.sales_trend_table,
            [
                QHeaderView.Stretch,
                QHeaderView.Stretch,
                QHeaderView.Stretch,
                QHeaderView.Stretch,
                QHeaderView.Stretch,
            ],
        )
        trend_layout.addWidget(self.sales_trend_table)

        top_items_box = QGroupBox("Top Selling Items")
        top_items_layout = QVBoxLayout(top_items_box)
        self.top_items_table = QTableWidget(0, 3)
        self.top_items_table.setHorizontalHeaderLabels(["Item", "Qty Sold", "Sales Value"])
        self._style_report_table(self.top_items_table)
        self._apply_report_column_modes(
            self.top_items_table,
            [
                QHeaderView.Interactive,
                QHeaderView.ResizeToContents,
                QHeaderView.ResizeToContents,
            ],
        )
        self.top_items_table.setColumnWidth(0, 220)
        top_items_layout.addWidget(self.top_items_table)

        low_stock_box = QGroupBox("Low Stock")
        low_stock_layout = QVBoxLayout(low_stock_box)
        self.low_stock_table = QTableWidget(0, 3)
        self.low_stock_table.setHorizontalHeaderLabels(["Item", "Stock", "Reorder"])
        self._style_report_table(self.low_stock_table)
        self._apply_report_column_modes(
            self.low_stock_table,
            [
                QHeaderView.Interactive,
                QHeaderView.ResizeToContents,
                QHeaderView.ResizeToContents,
            ],
        )
        self.low_stock_table.setColumnWidth(0, 220)
        low_stock_layout.addWidget(self.low_stock_table)

        ledger_box = QGroupBox("Stock Movement Ledger")
        ledger_layout = QVBoxLayout(ledger_box)
        self.ledger_table = QTableWidget(0, 6)
        self.ledger_table.setHorizontalHeaderLabels(
            ["Time", "Item", "Change", "Reason", "Reference", "Notes"]
        )
        self._style_report_table(self.ledger_table)
        self._apply_report_column_modes(
            self.ledger_table,
            [
                QHeaderView.ResizeToContents,
                QHeaderView.ResizeToContents,
                QHeaderView.ResizeToContents,
                QHeaderView.ResizeToContents,
                QHeaderView.ResizeToContents,
                QHeaderView.Interactive,
            ],
        )
        self.ledger_table.setColumnWidth(5, 320)
        ledger_layout.addWidget(self.ledger_table)

        refresh_reports_btn = QPushButton("Refresh Reports")
        refresh_reports_btn.clicked.connect(self.refresh_reports)

        close_day_btn = QPushButton("Close Day (Ctrl+L)")
        close_day_btn.clicked.connect(self.close_day)

        backup_btn = QPushButton("Backup Now")
        backup_btn.clicked.connect(self.backup_now)

        export_btn = QPushButton("Export DB Backup")
        export_btn.clicked.connect(self.export_backup_dialog)

        restore_btn = QPushButton("Restore DB Backup")
        restore_btn.clicked.connect(self.restore_backup_dialog)

        export_reports_btn = QPushButton("Export CSV")
        export_reports_btn.clicked.connect(self.export_reports_csv)

        export_reports_xlsx_btn = QPushButton("Export XLSX")
        export_reports_xlsx_btn.clicked.connect(self.export_reports_xlsx)

        export_all_btn = QPushButton("Export All CSV")
        export_all_btn.clicked.connect(self.export_all_csv)

        print_summary_btn = QPushButton("Print Summary")
        print_summary_btn.clicked.connect(self.export_printable_summary)

        self.report_from_date = QDateEdit()
        self.report_from_date.setCalendarPopup(True)
        self.report_from_date.setDisplayFormat("yyyy-MM-dd")
        self.report_from_date.setDate(QDate.currentDate().addDays(-6))

        self.report_to_date = QDateEdit()
        self.report_to_date.setCalendarPopup(True)
        self.report_to_date.setDisplayFormat("yyyy-MM-dd")
        self.report_to_date.setDate(QDate.currentDate())

        r_today_btn = QPushButton("Today")
        r_today_btn.clicked.connect(
            lambda: self._apply_quick_range(
                self.report_from_date,
                self.report_to_date,
                "today",
                self.refresh_reports,
            )
        )
        r_7d_btn = QPushButton("Last 7 Days")
        r_7d_btn.clicked.connect(
            lambda: self._apply_quick_range(
                self.report_from_date,
                self.report_to_date,
                "last7",
                self.refresh_reports,
            )
        )
        r_month_btn = QPushButton("This Month")
        r_month_btn.clicked.connect(
            lambda: self._apply_quick_range(
                self.report_from_date,
                self.report_to_date,
                "month",
                self.refresh_reports,
            )
        )
        r_custom_btn = QPushButton("Custom")
        r_custom_btn.clicked.connect(self.refresh_reports)

        self.top_items_limit_spin = QSpinBox()
        self.top_items_limit_spin.setRange(5, 100)
        self.top_items_limit_spin.setValue(20)
        self.ledger_limit_spin = QSpinBox()
        self.ledger_limit_spin.setRange(50, 2000)
        self.ledger_limit_spin.setValue(500)

        self.role_combo = QComboBox()
        self.role_combo.addItems(["cashier", "admin"])
        self.role_combo.setCurrentText(self.current_role)
        self.role_combo.currentTextChanged.connect(self.on_role_changed)

        self.open_after_export_checkbox = QCheckBox("Open after export")
        self.open_after_export_checkbox.setChecked(True)
        reports_tabs = QTabWidget()

        overview_tab = QWidget()
        overview_layout = QVBoxLayout(overview_tab)
        overview_filters_box = QGroupBox("Overview Filters")
        overview_filters_layout = QGridLayout(overview_filters_box)
        overview_filters_layout.addWidget(QLabel("From"), 0, 0)
        overview_filters_layout.addWidget(self.report_from_date, 0, 1)
        overview_filters_layout.addWidget(QLabel("To"), 0, 2)
        overview_filters_layout.addWidget(self.report_to_date, 0, 3)
        overview_filters_layout.addWidget(r_today_btn, 0, 4)
        overview_filters_layout.addWidget(r_7d_btn, 0, 5)
        overview_filters_layout.addWidget(r_month_btn, 0, 6)
        overview_filters_layout.addWidget(r_custom_btn, 0, 7)
        overview_filters_layout.addWidget(QLabel("Top Items"), 1, 0)
        overview_filters_layout.addWidget(self.top_items_limit_spin, 1, 1)
        overview_filters_layout.addWidget(refresh_reports_btn, 1, 2)
        overview_filters_layout.setColumnStretch(8, 1)

        overview_layout.addWidget(title)
        overview_layout.addWidget(subtitle)
        overview_layout.addWidget(overview_filters_box)
        overview_layout.addLayout(cards_grid)
        overview_layout.addWidget(trend_box)
        overview_layout.addWidget(top_items_box)

        stock_tab = QWidget()
        stock_layout = QVBoxLayout(stock_tab)
        stock_refresh_btn = QPushButton("Refresh Stock and Audit")
        stock_refresh_btn.clicked.connect(self.refresh_reports)
        stock_controls_box = QGroupBox("Stock Analysis Controls")
        stock_controls_layout = QHBoxLayout(stock_controls_box)
        stock_controls_layout.addWidget(QLabel("Ledger"))
        stock_controls_layout.addWidget(self.ledger_limit_spin)
        stock_controls_layout.addWidget(stock_refresh_btn)
        stock_controls_layout.addStretch()

        stock_layout.addWidget(stock_controls_box)
        stock_layout.addWidget(low_stock_box)
        stock_layout.addWidget(ledger_box)

        audit_box = QGroupBox("Audit Log")
        audit_box_layout = QVBoxLayout(audit_box)
        self.audit_log_table = QTableWidget(0, 6)
        self.audit_log_table.setHorizontalHeaderLabels(["Time", "Role", "Action", "Entity", "Entity ID", "Details"])
        self._style_report_table(self.audit_log_table)
        self._apply_report_column_modes(
            self.audit_log_table,
            [
                QHeaderView.ResizeToContents,
                QHeaderView.ResizeToContents,
                QHeaderView.ResizeToContents,
                QHeaderView.ResizeToContents,
                QHeaderView.ResizeToContents,
                QHeaderView.Interactive,
            ],
        )
        self.audit_log_table.setColumnWidth(5, 340)
        refresh_audit_btn = QPushButton("Refresh Audit")
        refresh_audit_btn.clicked.connect(self.refresh_reports)
        export_audit_csv_btn = QPushButton("Export Audit CSV")
        export_audit_csv_btn.clicked.connect(self.export_audit_csv)
        export_audit_xlsx_btn = QPushButton("Export Audit XLSX")
        export_audit_xlsx_btn.clicked.connect(self.export_audit_xlsx)
        audit_actions = QHBoxLayout()
        audit_actions.addWidget(refresh_audit_btn)
        audit_actions.addWidget(export_audit_csv_btn)
        audit_actions.addWidget(export_audit_xlsx_btn)
        audit_actions.addStretch()
        audit_box_layout.addWidget(self.audit_log_table)
        audit_box_layout.addLayout(audit_actions)

        stock_layout.addWidget(audit_box)

        data_ops_tab = QWidget()
        data_ops_layout = QVBoxLayout(data_ops_tab)
        data_ops_layout.setSpacing(8)

        data_ops_buttons = [
            close_day_btn,
            backup_btn,
            export_btn,
            restore_btn,
            export_reports_btn,
            export_reports_xlsx_btn,
            export_all_btn,
            print_summary_btn,
            auto_backup_save_btn,
            save_fixed_btn,
        ]
        for button in data_ops_buttons:
            button.setMinimumHeight(34)
            button.setMaximumHeight(34)

        section_style = (
            "QGroupBox {"
            "border: 1px solid #3a4250;"
            "border-radius: 6px;"
            "margin-top: 10px;"
            "padding-top: 8px;"
            "}"
            "QGroupBox::title {"
            "subcontrol-origin: margin;"
            "left: 10px;"
            "padding: 0 4px;"
            "color: #dbe1ee;"
            "}"
        )

        role_and_close_box = QGroupBox("Access and Closing")
        role_and_close_box.setStyleSheet(section_style)
        role_and_close_layout = QHBoxLayout(role_and_close_box)
        role_and_close_layout.addWidget(QLabel("Role"))
        role_and_close_layout.addWidget(self.role_combo)
        role_and_close_layout.addWidget(close_day_btn)
        role_and_close_layout.addStretch()

        backup_actions_box = QGroupBox("Backup and Restore")
        backup_actions_box.setStyleSheet(section_style)
        backup_actions_layout = QHBoxLayout(backup_actions_box)
        backup_actions_layout.addWidget(backup_btn)
        backup_actions_layout.addWidget(export_btn)
        backup_actions_layout.addWidget(restore_btn)
        backup_actions_layout.addStretch()

        report_exports_box = QGroupBox("Reporting Exports")
        report_exports_box.setStyleSheet(section_style)
        report_exports_layout = QHBoxLayout(report_exports_box)
        report_exports_layout.addWidget(export_reports_btn)
        report_exports_layout.addWidget(export_reports_xlsx_btn)
        report_exports_layout.addWidget(export_all_btn)
        report_exports_layout.addWidget(print_summary_btn)
        report_exports_layout.addWidget(self.open_after_export_checkbox)
        report_exports_layout.addStretch()

        backup_automation_box.setStyleSheet(section_style)
        fixed_cost_box.setStyleSheet(section_style)

        separator_one = QFrame()
        separator_one.setFrameShape(QFrame.HLine)
        separator_one.setStyleSheet("color: #313846;")

        separator_two = QFrame()
        separator_two.setFrameShape(QFrame.HLine)
        separator_two.setStyleSheet("color: #313846;")

        separator_three = QFrame()
        separator_three.setFrameShape(QFrame.HLine)
        separator_three.setStyleSheet("color: #313846;")

        separator_four = QFrame()
        separator_four.setFrameShape(QFrame.HLine)
        separator_four.setStyleSheet("color: #313846;")

        data_ops_layout.addWidget(role_and_close_box)
        data_ops_layout.addWidget(separator_one)
        data_ops_layout.addWidget(backup_actions_box)
        data_ops_layout.addWidget(separator_two)
        data_ops_layout.addWidget(backup_automation_box)
        data_ops_layout.addWidget(separator_three)
        data_ops_layout.addWidget(fixed_cost_box)
        data_ops_layout.addWidget(separator_four)
        data_ops_layout.addWidget(report_exports_box)
        data_ops_layout.addStretch()

        reports_tabs.addTab(overview_tab, "Overview")
        reports_tabs.addTab(stock_tab, "Stock and Audit")
        reports_tabs.addTab(data_ops_tab, "Data Ops")

        reports_content = QWidget()
        reports_content_layout = QVBoxLayout(reports_content)
        reports_content_layout.setContentsMargins(8, 8, 8, 8)
        reports_content_layout.setSpacing(10)
        reports_content_layout.addWidget(reports_tabs)

        reports_scroll = QScrollArea()
        reports_scroll.setWidgetResizable(True)
        reports_scroll.setWidget(reports_content)

        root_layout.addWidget(reports_scroll)
        self._apply_report_table_width_profiles()

        return tab

    def _make_report_metric_card(self, heading: str, accent_color: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet(
            "QFrame {"
            "border: 1px solid #3a3f4b;"
            "border-radius: 8px;"
            "background-color: #1f232b;"
            "padding: 8px;"
            "}"
        )

        layout = QVBoxLayout(card)
        title = QLabel(heading)
        title.setStyleSheet(f"color: {accent_color}; font-weight: bold;")

        value = QLabel("INR 0.00")
        value.setStyleSheet("font-size: 17px; font-weight: bold; color: #f4f6fa;")

        layout.addWidget(title)
        layout.addWidget(value)
        layout.addStretch()
        return card, value

    def _style_report_table(self, table: QTableWidget) -> None:
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(True)
        table.setWordWrap(False)
        table.setMinimumHeight(145)
        table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setMinimumSectionSize(72)
        table.horizontalHeader().setDefaultSectionSize(122)
        table.verticalHeader().setDefaultSectionSize(34)
        table.setStyleSheet(
            "QTableWidget {"
            "gridline-color: #3e4657;"
            "alternate-background-color: #262b35;"
            "background-color: #1e222a;"
            "}"
            "QHeaderView::section {"
            "background-color: #2d3441;"
            "color: #dce2ef;"
            "padding: 8px 10px;"
            "border: 0px;"
            "border-right: 1px solid #3b4352;"
            "}"
        )

    def _apply_report_column_modes(self, table: QTableWidget, modes: list[QHeaderView.ResizeMode]) -> None:
        header = table.horizontalHeader()
        for idx, mode in enumerate(modes):
            header.setSectionResizeMode(idx, mode)

    def _apply_report_table_width_profiles(self) -> None:
        width = self.width()
        if width < 1200:
            item_col = 170
            ledger_notes_col = 260
            audit_details_col = 280
        elif width < 1500:
            item_col = 220
            ledger_notes_col = 320
            audit_details_col = 340
        else:
            item_col = 280
            ledger_notes_col = 420
            audit_details_col = 460

        self.top_items_table.setColumnWidth(0, item_col)
        self.low_stock_table.setColumnWidth(0, item_col)
        self.ledger_table.setColumnWidth(5, ledger_notes_col)
        self.audit_log_table.setColumnWidth(5, audit_details_col)

    @staticmethod
    def _report_item(value: str, right_align: bool = False) -> QTableWidgetItem:
        item = QTableWidgetItem(value)
        if right_align:
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
        else:
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        return item

    def _table_rows_for_csv(self, table: QTableWidget) -> list[list[str]]:
        headers = [table.horizontalHeaderItem(col).text() for col in range(table.columnCount())]
        rows: list[list[str]] = [headers]

        for row in range(table.rowCount()):
            values: list[str] = []
            for col in range(table.columnCount()):
                cell = table.item(row, col)
                values.append(cell.text() if cell is not None else "")
            rows.append(values)
        return rows

    @staticmethod
    def _set_date_edit_range(from_edit: QDateEdit, to_edit: QDateEdit, start: date, end: date) -> None:
        from_edit.setDate(QDate(start.year, start.month, start.day))
        to_edit.setDate(QDate(end.year, end.month, end.day))

    @staticmethod
    def _iso_range_from_edits(from_edit: QDateEdit, to_edit: QDateEdit) -> tuple[str, str]:
        start = from_edit.date().toPython()
        end = to_edit.date().toPython()
        if start > end:
            start, end = end, start
            from_edit.setDate(QDate(start.year, start.month, start.day))
            to_edit.setDate(QDate(end.year, end.month, end.day))
        return start.isoformat(), end.isoformat()

    def _apply_quick_range(
        self,
        from_edit: QDateEdit,
        to_edit: QDateEdit,
        preset: str,
        refresh_callback,
    ) -> None:
        today = date.today()
        if preset == "today":
            start, end = today, today
        elif preset == "last7":
            start, end = today - timedelta(days=6), today
        elif preset == "month":
            start, end = today.replace(day=1), today
        else:
            start, end = today, today

        self._set_date_edit_range(from_edit, to_edit, start, end)
        refresh_callback()

    @staticmethod
    def _range_suffix(start_date: str, end_date: str) -> str:
        if start_date == end_date:
            return start_date
        return f"{start_date}_to_{end_date}"

    def _save_csv_rows(self, default_name: str, rows: list[list[str]]) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save CSV",
            default_name,
            "CSV Files (*.csv)",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerows(rows)
        except Exception as exc:
            QMessageBox.critical(self, "CSV Export", f"Failed to export CSV: {exc}")
            return

        try:
            if getattr(self, "open_after_export_checkbox", None) is None:
                should_open = True
            else:
                should_open = self.open_after_export_checkbox.isChecked()
            if should_open and hasattr(os, "startfile"):
                os.startfile(path)
        except Exception:
            pass

        QMessageBox.information(self, "CSV Export", f"CSV exported successfully:\n{path}")

    @staticmethod
    def _write_csv_file(path: str, rows: list[list[str]]) -> None:
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerows(rows)

    def _build_reports_csv_rows(self, start_date: str, end_date: str) -> list[list[str]]:
        rows: list[list[str]] = []

        rows.append(["Report Range", start_date, end_date])
        rows.append([])
        rows.append(["Today Summary"])
        rows.append(["Sales", self.sales_value.text().replace("INR ", "")])
        rows.append(["COGS", self.cogs_value.text().replace("INR ", "")])
        rows.append(["Gross Profit", self.gross_profit_value.text().replace("INR ", "")])
        rows.append(["Purchases", self.purchases_value.text().replace("INR ", "")])
        rows.append(["Expenses", self.expenses_value.text().replace("INR ", "")])
        rows.append(["Fixed Cost / Day", self.fixed_daily_value.text().replace("INR ", "")])
        rows.append(["Realistic Daily Profit", self.net_value.text().replace("INR ", "")])
        rows.append(["Monthly Fixed Total", self.monthly_fixed_total_label.text().replace("Monthly Fixed Total: INR ", "")])
        rows.append([])

        rows.append(["Sales Trend"])
        rows.extend(self._table_rows_for_csv(self.sales_trend_table))
        rows.append([])

        rows.append(["Top Selling Items"])
        rows.extend(self._table_rows_for_csv(self.top_items_table))
        rows.append([])

        rows.append(["Low Stock"])
        rows.extend(self._table_rows_for_csv(self.low_stock_table))
        rows.append([])

        rows.append(["Stock Movement Ledger"])
        rows.extend(self._table_rows_for_csv(self.ledger_table))
        return rows

    def export_inventory_csv(self) -> None:
        rows = self._table_rows_for_csv(self.inventory_items_table)
        self._save_csv_rows("inventory_export.csv", rows)

    def export_purchases_csv(self) -> None:
        start_date, end_date = self._iso_range_from_edits(self.purchase_from_date, self.purchase_to_date)
        rows = self._table_rows_for_csv(self.purchase_history_table)
        self._save_csv_rows(f"purchases_{self._range_suffix(start_date, end_date)}.csv", rows)

    def export_expenses_csv(self) -> None:
        start_date, end_date = self._iso_range_from_edits(self.expense_from_date, self.expense_to_date)
        rows = self._table_rows_for_csv(self.expense_history_table)
        self._save_csv_rows(f"expenses_{self._range_suffix(start_date, end_date)}.csv", rows)

    def export_reports_csv(self) -> None:
        start_date, end_date = self._iso_range_from_edits(self.report_from_date, self.report_to_date)
        rows = self._build_reports_csv_rows(start_date=start_date, end_date=end_date)
        self._save_csv_rows(f"reports_{self._range_suffix(start_date, end_date)}.csv", rows)

    def export_all_csv(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Folder for CSV Export")
        if not folder:
            return

        report_start, report_end = self._iso_range_from_edits(self.report_from_date, self.report_to_date)

        files_to_export = {
            "inventory.csv": self._table_rows_for_csv(self.inventory_items_table),
            "purchases.csv": self._table_rows_for_csv(self.purchase_history_table),
            "expenses.csv": self._table_rows_for_csv(self.expense_history_table),
            "reports.csv": self._build_reports_csv_rows(start_date=report_start, end_date=report_end),
        }

        written_paths: list[str] = []
        try:
            for filename, rows in files_to_export.items():
                out_path = os.path.join(folder, filename)
                self._write_csv_file(out_path, rows)
                written_paths.append(out_path)
        except Exception as exc:
            QMessageBox.critical(self, "CSV Export", f"Failed during Export All: {exc}")
            return

        if self.open_after_export_checkbox.isChecked() and hasattr(os, "startfile"):
            try:
                os.startfile(folder)
            except Exception:
                pass

        QMessageBox.information(
            self,
            "CSV Export",
            "Export All completed:\n" + "\n".join(written_paths),
        )

    def save_monthly_fixed_costs(self) -> None:
        try:
            self.report_service.save_monthly_fixed_costs(
                rent=float(self.rent_spin.value()),
                salary=float(self.salary_spin.value()),
                maintenance=float(self.maintenance_spin.value()),
                electricity=float(self.electricity_spin.value()),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Fixed Costs", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Fixed Costs Error", str(exc))
            return

        QMessageBox.information(self, "Fixed Costs", "Monthly fixed costs saved.")
        self.refresh_reports()

    def refresh_all(self) -> None:
        self.refresh_categories()
        self.refresh_inventory()
        self.refresh_billing_items()
        self.refresh_purchases_tab()
        self.refresh_expenses_tab()
        self.refresh_reports()

    def refresh_categories(self) -> None:
        categories = self.inventory_service.list_categories()
        self.category_combo.clear()
        self.category_combo.addItem("Uncategorized", None)
        for category in categories:
            self.category_combo.addItem(category["name"], category["id"])

    def refresh_inventory(self) -> None:
        items = self.inventory_service.list_items()
        table = self.inventory_items_table
        self._updating_inventory_table = True
        table.setRowCount(len(items))

        for row_index, item in enumerate(items):
            id_item = QTableWidgetItem(str(item["id"]))
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row_index, 0, id_item)

            name_item = QTableWidgetItem(item["name"])
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row_index, 1, name_item)

            category_item = QTableWidgetItem(item.get("category_name") or "-")
            category_item.setFlags(category_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row_index, 2, category_item)

            sell_item = QTableWidgetItem(f"{item['selling_price']:.2f}")
            table.setItem(row_index, 3, sell_item)

            stock_item = QTableWidgetItem(f"{item['stock_quantity']:.2f}")
            stock_item.setFlags(stock_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row_index, 4, stock_item)

            reorder_item = QTableWidgetItem(f"{item['reorder_level']:.2f}")
            table.setItem(row_index, 5, reorder_item)
        self._updating_inventory_table = False

    def _on_inventory_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_inventory_table:
            return

        column = item.column()
        if column not in (3, 5):
            return

        row = item.row()
        id_cell = self.inventory_items_table.item(row, 0)
        sell_cell = self.inventory_items_table.item(row, 3)
        reorder_cell = self.inventory_items_table.item(row, 5)
        if id_cell is None or sell_cell is None or reorder_cell is None:
            return

        pin = self._require_admin_access("Inventory Edit")
        if pin is None:
            self.refresh_inventory()
            return

        try:
            item_id = int(id_cell.text())
            selling_price = float(sell_cell.text().strip())
            reorder_level = float(reorder_cell.text().strip())
            self.inventory_service.update_item_sell_and_reorder(
                item_id=item_id,
                selling_price=selling_price,
                reorder_level=reorder_level,
                admin_pin=pin,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Inventory Edit", str(exc))
            self.refresh_inventory()
            return
        except Exception as exc:
            QMessageBox.critical(self, "Inventory Edit Error", str(exc))
            self.refresh_inventory()
            return

        self.refresh_inventory()
        self.refresh_billing_items()
        self.refresh_reports()
        self._log_audit("inventory_inline_edit", "item", str(item_id), f"sell={selling_price}, reorder={reorder_level}")

    def refresh_purchases_tab(self) -> None:
        items = self.inventory_service.list_items()
        self.purchase_item_cache = {int(item["id"]): item for item in items}

        self.purchase_item_combo.clear()
        for item in items:
            self.purchase_item_combo.addItem(
                f"{item['name']} (Stock {item['stock_quantity']:.2f})",
                int(item["id"]),
            )
        self._on_purchase_item_changed()

        start_date, end_date = self._iso_range_from_edits(self.purchase_from_date, self.purchase_to_date)
        history = self.bookkeeping_service.list_purchases_between(
            start_date=start_date,
            end_date=end_date,
            limit=1000,
        )
        self.purchase_history_table.setRowCount(len(history))
        for row_index, purchase in enumerate(history):
            self.purchase_history_table.setItem(row_index, 0, QTableWidgetItem(str(purchase["id"])))
            self.purchase_history_table.setItem(
                row_index,
                1,
                QTableWidgetItem(purchase["supplier_name"] or "-"),
            )
            self.purchase_history_table.setItem(row_index, 2, QTableWidgetItem(purchase["purchased_at"]))
            self.purchase_history_table.setItem(row_index, 3, QTableWidgetItem(str(purchase["line_items"])))
            self.purchase_history_table.setItem(
                row_index,
                4,
                QTableWidgetItem(f"{float(purchase['total_cost']):.2f}"),
            )
            self.purchase_history_table.setItem(
                row_index,
                5,
                QTableWidgetItem(purchase["notes"] or ""),
            )

        self.refresh_purchase_lines_table()

    def refresh_expenses_tab(self) -> None:
        self._updating_expense_table = True
        start_date, end_date = self._iso_range_from_edits(self.expense_from_date, self.expense_to_date)
        history = self.bookkeeping_service.list_expenses_between(
            start_date=start_date,
            end_date=end_date,
            limit=1000,
        )
        self.expense_history_table.setRowCount(len(history))
        for row_index, expense in enumerate(history):
            id_item = QTableWidgetItem(str(expense["id"]))
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            self.expense_history_table.setItem(row_index, 0, id_item)

            type_item = QTableWidgetItem(expense["expense_type"])
            self.expense_history_table.setItem(row_index, 1, type_item)

            amount_item = QTableWidgetItem(f"{float(expense['amount']):.2f}")
            self.expense_history_table.setItem(
                row_index,
                2,
                amount_item,
            )

            date_item = QTableWidgetItem(expense["spent_at"])
            date_item.setFlags(date_item.flags() & ~Qt.ItemIsEditable)
            self.expense_history_table.setItem(row_index, 3, date_item)

            notes_item = QTableWidgetItem(expense["notes"] or "")
            self.expense_history_table.setItem(row_index, 4, notes_item)
        self._updating_expense_table = False

    def _on_purchase_item_changed(self) -> None:
        item_id = self.purchase_item_combo.currentData()
        if item_id is None:
            return
        item = self.purchase_item_cache.get(int(item_id))
        if item is None:
            return
        self.purchase_cost_spin.setValue(float(item.get("cost_price") or 0))

    def add_purchase_line(self) -> None:
        item_id = self.purchase_item_combo.currentData()
        if item_id is None:
            QMessageBox.warning(self, "Purchase", "Please select an item.")
            return

        item = self.purchase_item_cache.get(int(item_id))
        if item is None:
            QMessageBox.warning(self, "Purchase", "Selected item was not found.")
            return

        quantity = float(self.purchase_qty_spin.value())
        cost_price = float(self.purchase_cost_spin.value())
        if quantity <= 0:
            QMessageBox.warning(self, "Purchase", "Quantity must be greater than zero.")
            return
        if cost_price < 0:
            QMessageBox.warning(self, "Purchase", "Cost price cannot be negative.")
            return

        existing = next((line for line in self.purchase_cart if int(line["item_id"]) == int(item_id)), None)
        if existing:
            existing["quantity"] = float(existing["quantity"]) + quantity
            existing["cost_price"] = cost_price
        else:
            self.purchase_cart.append(
                {
                    "item_id": int(item_id),
                    "name": item["name"],
                    "quantity": quantity,
                    "cost_price": cost_price,
                }
            )
        self.refresh_purchase_lines_table()

    def remove_selected_purchase_line(self) -> None:
        selected = self.purchase_lines_table.currentRow()
        if selected < 0:
            QMessageBox.information(self, "Purchase", "Please select a purchase line.")
            return

        item_id = int(self.purchase_lines_table.item(selected, 0).text())
        self.purchase_cart = [line for line in self.purchase_cart if int(line["item_id"]) != item_id]
        self.refresh_purchase_lines_table()

    def clear_purchase_lines(self) -> None:
        self.purchase_cart = []
        self.refresh_purchase_lines_table()

    def _set_purchase_mode(self, editing: bool, purchase_id: int | None = None) -> None:
        if editing and purchase_id is not None:
            self.editing_purchase_id = int(purchase_id)
            self.save_purchase_btn.setText("Update Purchase")
            self.cancel_purchase_edit_btn.setEnabled(True)
            self.purchase_mode_label.setText(f"Mode: Editing Purchase #{purchase_id}")
        else:
            self.editing_purchase_id = None
            self.save_purchase_btn.setText("Save Purchase")
            self.cancel_purchase_edit_btn.setEnabled(False)
            self.purchase_mode_label.setText("Mode: New Purchase")

    def cancel_purchase_edit(self) -> None:
        self.purchase_supplier_input.clear()
        self.purchase_notes_input.clear()
        self.clear_purchase_lines()
        self._set_purchase_mode(False)

    def load_selected_purchase_for_edit(self) -> None:
        selected = self.purchase_history_table.currentRow()
        if selected < 0:
            QMessageBox.information(self, "Purchase Edit", "Please select a purchase from history.")
            return

        id_cell = self.purchase_history_table.item(selected, 0)
        if id_cell is None:
            return

        purchase_id = int(id_cell.text())
        pin = self._require_admin_access("Purchase Edit")
        if pin is None:
            return

        try:
            purchase = self.bookkeeping_service.get_purchase_for_edit(purchase_id=purchase_id, admin_pin=pin)
        except ValueError as exc:
            QMessageBox.warning(self, "Purchase Edit", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Purchase Edit Error", str(exc))
            return

        self.purchase_supplier_input.setText(purchase.get("supplier_name") or "")
        self.purchase_notes_input.setText(purchase.get("notes") or "")
        self.purchase_cart = [
            {
                "item_id": int(line["item_id"]),
                "name": line["name"],
                "quantity": float(line["quantity"]),
                "cost_price": float(line["cost_price"]),
            }
            for line in purchase.get("items", [])
        ]
        self.refresh_purchase_lines_table()
        self._set_purchase_mode(True, purchase_id=purchase_id)

    def refresh_purchase_lines_table(self) -> None:
        self._updating_purchase_table = True
        self.purchase_lines_table.setRowCount(len(self.purchase_cart))
        total = 0.0
        for row_index, line in enumerate(self.purchase_cart):
            line_total = float(line["quantity"]) * float(line["cost_price"])
            total += line_total
            id_item = QTableWidgetItem(str(line["item_id"]))
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            self.purchase_lines_table.setItem(row_index, 0, id_item)

            name_item = QTableWidgetItem(line["name"])
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.purchase_lines_table.setItem(row_index, 1, name_item)

            qty_item = QTableWidgetItem(f"{line['quantity']:.2f}")
            self.purchase_lines_table.setItem(row_index, 2, qty_item)

            cost_item = QTableWidgetItem(f"{line['cost_price']:.2f}")
            self.purchase_lines_table.setItem(row_index, 3, cost_item)

            total_item = QTableWidgetItem(f"{line_total:.2f}")
            total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
            self.purchase_lines_table.setItem(row_index, 4, total_item)

        self._updating_purchase_table = False

        self.purchase_total_label.setText(f"Purchase Total: INR {total:.2f}")

    def _on_purchase_line_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_purchase_table:
            return

        row = item.row()
        column = item.column()
        if column not in (2, 3):
            return

        id_cell = self.purchase_lines_table.item(row, 0)
        if id_cell is None:
            return

        item_id = int(id_cell.text())
        target = next((line for line in self.purchase_cart if int(line["item_id"]) == item_id), None)
        if target is None:
            return

        try:
            value = float(item.text().strip())
            if column == 2 and value <= 0:
                raise ValueError("Quantity must be greater than zero.")
            if column == 3 and value < 0:
                raise ValueError("Cost cannot be negative.")
        except ValueError as exc:
            QMessageBox.warning(self, "Purchase Line", str(exc))
            self.refresh_purchase_lines_table()
            return

        if column == 2:
            target["quantity"] = value
        else:
            target["cost_price"] = value
        self.refresh_purchase_lines_table()

    def save_purchase(self) -> None:
        if not self.purchase_cart:
            QMessageBox.warning(self, "Purchase", "Add at least one purchase line.")
            return

        was_editing = self.editing_purchase_id is not None

        supplier_name = self.purchase_supplier_input.text().strip()
        notes = self.purchase_notes_input.text().strip()
        payload = [
            {
                "item_id": int(line["item_id"]),
                "quantity": float(line["quantity"]),
                "cost_price": float(line["cost_price"]),
            }
            for line in self.purchase_cart
        ]

        try:
            if self.editing_purchase_id is None:
                purchase_id = self.bookkeeping_service.add_purchase(
                    supplier_name=supplier_name,
                    items=payload,
                    notes=notes,
                )
                message = f"Purchase recorded. ID: {purchase_id}"
            else:
                pin = self._require_admin_access("Purchase Update")
                if pin is None:
                    return
                self.bookkeeping_service.update_purchase(
                    purchase_id=self.editing_purchase_id,
                    supplier_name=supplier_name,
                    items=payload,
                    notes=notes,
                    admin_pin=pin,
                )
                purchase_id = self.editing_purchase_id
                message = f"Purchase updated. ID: {purchase_id}"
        except ValueError as exc:
            QMessageBox.warning(self, "Purchase", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Purchase Error", str(exc))
            return

        QMessageBox.information(self, "Purchase Saved", message)
        self.purchase_supplier_input.clear()
        self.purchase_notes_input.clear()
        self.clear_purchase_lines()
        self._set_purchase_mode(False)
        self.refresh_inventory()
        self.refresh_billing_items()
        self.refresh_purchases_tab()
        self.refresh_reports()
        self._log_audit(
            "purchase_update" if was_editing else "purchase_save",
            "purchase",
            str(purchase_id),
            f"lines={len(payload)}",
        )

    def add_expense(self) -> None:
        expense_type = self.expense_type_combo.currentText().strip()
        amount = float(self.expense_amount_spin.value())
        notes = self.expense_notes_input.text().strip()

        try:
            expense_id = self.bookkeeping_service.add_expense(
                expense_type=expense_type,
                amount=amount,
                notes=notes,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Expense", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Expense Error", str(exc))
            return

        QMessageBox.information(self, "Expense Saved", f"Expense recorded. ID: {expense_id}")
        self.expense_amount_spin.setValue(0.01)
        self.expense_notes_input.clear()
        self.refresh_expenses_tab()
        self.refresh_reports()
        self._log_audit("expense_add", "expense", str(expense_id), expense_type)

    def _on_expense_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_expense_table:
            return

        row = item.row()
        column = item.column()
        if column not in (1, 2, 4):
            return

        id_cell = self.expense_history_table.item(row, 0)
        type_cell = self.expense_history_table.item(row, 1)
        amount_cell = self.expense_history_table.item(row, 2)
        notes_cell = self.expense_history_table.item(row, 4)
        if id_cell is None or type_cell is None or amount_cell is None or notes_cell is None:
            return

        try:
            expense_id = int(id_cell.text())
            expense_type = type_cell.text().strip()
            amount = float(amount_cell.text().strip())
            notes = notes_cell.text().strip()
            self.bookkeeping_service.update_expense(
                expense_id=expense_id,
                expense_type=expense_type,
                amount=amount,
                notes=notes,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Expense Edit", str(exc))
            self.refresh_expenses_tab()
            return
        except Exception as exc:
            QMessageBox.critical(self, "Expense Edit Error", str(exc))
            self.refresh_expenses_tab()
            return

        self.refresh_expenses_tab()
        self.refresh_reports()
        self._log_audit("expense_edit", "expense", str(expense_id), f"type={expense_type}, amount={amount:.2f}")

    def refresh_billing_items(self) -> None:
        self.billing_items_cache = self.inventory_service.list_items()
        self.apply_billing_filter()
        self.refresh_cigarette_quick_buttons()

    def refresh_cigarette_quick_buttons(self) -> None:
        grouped = self.inventory_service.cigarette_items_grouped()

        self._clear_layout(self.small_buttons_layout)
        self._clear_layout(self.medium_buttons_layout)
        self._clear_layout(self.big_buttons_layout)
        for shortcut in self.cigarette_shortcuts:
            shortcut.setParent(None)
        self.cigarette_shortcuts = []

        shortcut_number = 1
        shortcut_number = self._populate_quick_row(
            layout=self.small_buttons_layout,
            items=grouped.get("small", []),
            color="#2e7d32",
            start_shortcut=shortcut_number,
        )
        shortcut_number = self._populate_quick_row(
            layout=self.medium_buttons_layout,
            items=grouped.get("medium", []),
            color="#f9a825",
            start_shortcut=shortcut_number,
        )
        self._populate_quick_row(
            layout=self.big_buttons_layout,
            items=grouped.get("big", []),
            color="#c62828",
            start_shortcut=shortcut_number,
        )

    def _populate_quick_row(
        self,
        layout: QHBoxLayout,
        items: list[dict],
        color: str,
        start_shortcut: int,
    ) -> int:
        shortcut_number = start_shortcut
        for item in items:
            label = f"{item['name']} {item['selling_price']:.0f}"
            if 1 <= shortcut_number <= 9:
                label += f" ({shortcut_number})"
            btn = QPushButton(label)
            btn.setStyleSheet(f"background-color: {color}; color: white; font-weight: bold;")
            btn.clicked.connect(lambda _, item_id=item["id"]: self.add_item_to_cart_by_id(item_id))
            layout.addWidget(btn)

            if 1 <= shortcut_number <= 9:
                sc = QShortcut(QKeySequence(str(shortcut_number)), self)
                sc.activated.connect(lambda item_id=item["id"]: self.add_item_to_cart_by_id(item_id))
                self.cigarette_shortcuts.append(sc)
            shortcut_number += 1

        layout.addStretch()
        return shortcut_number

    @staticmethod
    def _clear_layout(layout: QHBoxLayout) -> None:
        while layout.count():
            child = layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

    def apply_billing_filter(self) -> None:
        query = self.search_input.text().strip().lower()
        if query:
            filtered = [i for i in self.billing_items_cache if query in i["name"].lower()]
        else:
            filtered = self.billing_items_cache

        table = self.billing_items_table
        table.setRowCount(len(filtered))

        for row_index, item in enumerate(filtered):
            table.setItem(row_index, 0, QTableWidgetItem(str(item["id"])))
            table.setItem(row_index, 1, QTableWidgetItem(item["name"]))
            table.setItem(row_index, 2, QTableWidgetItem(f"{item['selling_price']:.2f}"))
            table.setItem(row_index, 3, QTableWidgetItem(f"{item['stock_quantity']:.2f}"))

        if len(filtered) > 0:
            table.selectRow(0)

    def add_inventory_item(self) -> None:
        try:
            self.inventory_service.add_item(
                name=self.item_name_input.text(),
                category_id=self.category_combo.currentData(),
                selling_price=float(self.sell_price_spin.value()),
                cost_price=float(self.cost_price_spin.value()),
                stock_quantity=float(self.stock_spin.value()),
                reorder_level=float(self.reorder_spin.value()),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Validation Error", str(exc))
            return

        self.item_name_input.clear()
        self.sell_price_spin.setValue(0)
        self.cost_price_spin.setValue(0)
        self.stock_spin.setValue(0)
        self.reorder_spin.setValue(0)
        self.refresh_inventory()
        self.refresh_billing_items()
        self.refresh_reports()

    def _selected_inventory_item(self) -> dict | None:
        selected = self.inventory_items_table.currentRow()
        if selected < 0:
            QMessageBox.information(self, "Select Item", "Please select an item from inventory.")
            return None

        return {
            "item_id": int(self.inventory_items_table.item(selected, 0).text()),
            "name": self.inventory_items_table.item(selected, 1).text(),
            "selling_price": float(self.inventory_items_table.item(selected, 3).text()),
        }

    def _log_audit(
        self,
        action_type: str,
        entity_type: str = "",
        entity_id: str = "",
        details: str = "",
    ) -> None:
        try:
            self.bookkeeping_service.log_audit(
                actor_role=self.current_role,
                action_type=action_type,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details,
            )
        except Exception:
            pass

    def _ask_admin_pin(self) -> str | None:
        pin, ok = QInputDialog.getText(self, "Admin PIN", "Enter admin PIN:")
        if not ok:
            return None
        return pin.strip()

    def _require_admin_access(self, action_name: str) -> str | None:
        if self.current_role == "admin":
            return self.bookkeeping_service.get_setting("admin_pin", "1234") or "1234"

        pin = self._ask_admin_pin()
        if pin is None:
            return None
        if not self.bookkeeping_service.verify_admin_pin(pin):
            QMessageBox.warning(self, action_name, "Invalid admin PIN.")
            return None
        return pin

    def on_role_changed(self, role_name: str) -> None:
        role = role_name.strip().lower()
        if role == self.current_role:
            return

        if role == "admin":
            pin = self._ask_admin_pin()
            if pin is None or not self.bookkeeping_service.verify_admin_pin(pin):
                QMessageBox.warning(self, "Role Switch", "Admin PIN verification failed.")
                self.role_combo.blockSignals(True)
                self.role_combo.setCurrentText(self.current_role)
                self.role_combo.blockSignals(False)
                return

        self.current_role = role
        self.bookkeeping_service.set_setting("current_role", role)
        self._log_audit("role_switch", "session", "current", f"Role changed to {role}")

    def _configure_auto_backup_timer(self) -> None:
        enabled = (self.bookkeeping_service.get_setting("auto_backup_enabled", "0") or "0") == "1"
        interval_str = self.bookkeeping_service.get_setting("backup_interval_minutes", "60") or "60"
        try:
            interval_minutes = max(5, int(float(interval_str)))
        except ValueError:
            interval_minutes = 60

        if hasattr(self, "auto_backup_enabled_checkbox"):
            self.auto_backup_enabled_checkbox.setChecked(enabled)
        if hasattr(self, "auto_backup_interval_spin"):
            self.auto_backup_interval_spin.setValue(interval_minutes)

        self.auto_backup_timer.stop()
        if enabled:
            self.auto_backup_timer.setInterval(interval_minutes * 60 * 1000)
            self.auto_backup_timer.start()

    def save_backup_preferences(self) -> None:
        enabled = self.auto_backup_enabled_checkbox.isChecked()
        interval = int(self.auto_backup_interval_spin.value())
        self.bookkeeping_service.set_setting("auto_backup_enabled", "1" if enabled else "0")
        self.bookkeeping_service.set_setting("backup_interval_minutes", str(interval))
        self._configure_auto_backup_timer()
        self._log_audit(
            "backup_schedule_update",
            "settings",
            "auto_backup",
            f"enabled={enabled}, interval_minutes={interval}",
        )
        QMessageBox.information(self, "Backup Schedule", "Backup schedule updated.")

    def _run_scheduled_backup(self) -> None:
        try:
            backup_path = create_backup(db_path=self.db_path)
            self._log_audit("scheduled_backup", "backup", str(backup_path), "Automatic backup completed")
        except Exception as exc:
            self._log_audit("scheduled_backup_failed", "backup", "", str(exc))

    @staticmethod
    def _format_restore_preview(current_counts: dict, backup_counts: dict, backup_file: str) -> str:
        lines = [
            "Restoring will overwrite current live database.",
            "",
            f"Backup file: {backup_file}",
            "",
            "Current DB -> Backup DB",
            f"Items: {current_counts.get('items', 0)} -> {backup_counts.get('items', 0)}",
            f"Sales: {current_counts.get('sales', 0)} -> {backup_counts.get('sales', 0)}",
            f"Purchases: {current_counts.get('purchases', 0)} -> {backup_counts.get('purchases', 0)}",
            f"Expenses: {current_counts.get('expenses', 0)} -> {backup_counts.get('expenses', 0)}",
            f"Stock Movements: {current_counts.get('stock_movements', 0)} -> {backup_counts.get('stock_movements', 0)}",
            "",
            "Continue with restore?",
        ]
        return "\n".join(lines)

    def export_reports_xlsx(self) -> None:
        try:
            from openpyxl import Workbook
        except Exception:
            QMessageBox.warning(self, "XLSX Export", "openpyxl is not installed. Run: pip install openpyxl")
            return

        start_date, end_date = self._iso_range_from_edits(self.report_from_date, self.report_to_date)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save XLSX",
            f"reports_{self._range_suffix(start_date, end_date)}.xlsx",
            "Excel Workbook (*.xlsx)",
        )
        if not path:
            return

        wb = Workbook()
        ws_summary = wb.active
        ws_summary.title = "Summary"
        ws_summary.append(["Metric", "Value"])
        ws_summary.append(["From", start_date])
        ws_summary.append(["To", end_date])
        ws_summary.append(["Sales", self.sales_value.text().replace("INR ", "")])
        ws_summary.append(["COGS", self.cogs_value.text().replace("INR ", "")])
        ws_summary.append(["Gross Profit", self.gross_profit_value.text().replace("INR ", "")])
        ws_summary.append(["Purchases", self.purchases_value.text().replace("INR ", "")])
        ws_summary.append(["Expenses", self.expenses_value.text().replace("INR ", "")])
        ws_summary.append(["Fixed Cost / Day", self.fixed_daily_value.text().replace("INR ", "")])
        ws_summary.append(["Realistic Daily Profit", self.net_value.text().replace("INR ", "")])

        table_sheets = [
            ("SalesTrend", self.sales_trend_table),
            ("TopItems", self.top_items_table),
            ("LowStock", self.low_stock_table),
            ("StockLedger", self.ledger_table),
        ]
        for sheet_name, table in table_sheets:
            ws = wb.create_sheet(title=sheet_name)
            for row in self._table_rows_for_csv(table):
                ws.append(row)

        try:
            wb.save(path)
        except Exception as exc:
            QMessageBox.critical(self, "XLSX Export", f"Failed to save XLSX: {exc}")
            return

        self._log_audit("xlsx_export", "report", "range", f"{start_date}..{end_date}")
        if self.open_after_export_checkbox.isChecked() and hasattr(os, "startfile"):
            try:
                os.startfile(path)
            except Exception:
                pass
        QMessageBox.information(self, "XLSX Export", f"XLSX exported successfully:\n{path}")

    def export_printable_summary(self) -> None:
        start_date, end_date = self._iso_range_from_edits(self.report_from_date, self.report_to_date)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Printable Summary",
            f"summary_{self._range_suffix(start_date, end_date)}.txt",
            "Text Files (*.txt)",
        )
        if not path:
            return

        lines = [
            "Cafe POS - Printable Summary",
            f"Range: {start_date} to {end_date}",
            "",
            f"Sales: {self.sales_value.text()}",
            f"COGS: {self.cogs_value.text()}",
            f"Gross Profit: {self.gross_profit_value.text()}",
            f"Purchases: {self.purchases_value.text()}",
            f"Expenses: {self.expenses_value.text()}",
            f"Fixed Cost / Day: {self.fixed_daily_value.text()}",
            f"Realistic Daily Profit: {self.net_value.text()}",
            "",
            "Top Selling Items:",
        ]
        for row in range(min(self.top_items_table.rowCount(), 15)):
            item = self.top_items_table.item(row, 0).text() if self.top_items_table.item(row, 0) else ""
            qty = self.top_items_table.item(row, 1).text() if self.top_items_table.item(row, 1) else ""
            value = self.top_items_table.item(row, 2).text() if self.top_items_table.item(row, 2) else ""
            lines.append(f"- {item}: qty {qty}, value {value}")

        try:
            Path(path).write_text("\n".join(lines), encoding="utf-8")
        except Exception as exc:
            QMessageBox.critical(self, "Printable Summary", f"Failed: {exc}")
            return

        self._log_audit("printable_summary_export", "report", "range", f"{start_date}..{end_date}")
        if self.open_after_export_checkbox.isChecked() and hasattr(os, "startfile"):
            try:
                os.startfile(path)
            except Exception:
                pass
        QMessageBox.information(self, "Printable Summary", f"Summary exported:\n{path}")

    def export_audit_csv(self) -> None:
        if not hasattr(self, "audit_log_table"):
            return
        rows = self._table_rows_for_csv(self.audit_log_table)
        self._save_csv_rows("audit_log_export.csv", rows)
        self._log_audit("audit_export_csv", "audit_log", "table", "audit log exported as csv")

    def export_audit_xlsx(self) -> None:
        try:
            from openpyxl import Workbook
        except Exception:
            QMessageBox.warning(self, "Audit XLSX", "openpyxl is not installed. Run: pip install openpyxl")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Audit XLSX",
            "audit_log_export.xlsx",
            "Excel Workbook (*.xlsx)",
        )
        if not path:
            return

        wb = Workbook()
        ws = wb.active
        ws.title = "AuditLog"
        for row in self._table_rows_for_csv(self.audit_log_table):
            ws.append(row)

        try:
            wb.save(path)
        except Exception as exc:
            QMessageBox.critical(self, "Audit XLSX", f"Failed to save XLSX: {exc}")
            return

        self._log_audit("audit_export_xlsx", "audit_log", "table", "audit log exported as xlsx")
        if self.open_after_export_checkbox.isChecked() and hasattr(os, "startfile"):
            try:
                os.startfile(path)
            except Exception:
                pass
        QMessageBox.information(self, "Audit XLSX", f"Audit XLSX exported successfully:\n{path}")

    def update_selected_item_price(self) -> None:
        item = self._selected_inventory_item()
        if item is None:
            return

        pin = self._require_admin_access("Update Price")
        if pin is None:
            return

        new_sell, ok_sell = QInputDialog.getDouble(
            self,
            "Update Selling Price",
            f"New selling price for {item['name']}",
            value=item["selling_price"],
            minValue=0.01,
            decimals=2,
        )
        if not ok_sell:
            return

        new_cost, ok_cost = QInputDialog.getDouble(
            self,
            "Update Cost Price",
            f"New cost price for {item['name']}",
            value=0,
            minValue=0,
            decimals=2,
        )
        if not ok_cost:
            return

        try:
            self.inventory_service.update_item_pricing(
                item_id=item["item_id"],
                selling_price=float(new_sell),
                cost_price=float(new_cost),
                admin_pin=pin,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Update Failed", str(exc))
            return

        self.refresh_inventory()
        self.refresh_billing_items()
        self._log_audit("price_update", "item", str(item["item_id"]), f"sell={float(new_sell):.2f}, cost={float(new_cost):.2f}")

    def adjust_selected_item_stock(self) -> None:
        item = self._selected_inventory_item()
        if item is None:
            return

        pin = self._require_admin_access("Manual Stock Adjustment")
        if pin is None:
            return

        quantity_delta, ok_delta = QInputDialog.getDouble(
            self,
            "Manual Stock Adjustment",
            "Enter stock change (+ add, - reduce):",
            decimals=2,
        )
        if not ok_delta:
            return

        notes, ok_notes = QInputDialog.getText(self, "Reason", "Reason for adjustment:")
        if not ok_notes:
            return

        try:
            self.inventory_service.manual_stock_adjustment(
                item_id=item["item_id"],
                quantity_delta=float(quantity_delta),
                admin_pin=pin,
                notes=notes,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Adjustment Failed", str(exc))
            return

        self.refresh_inventory()
        self.refresh_billing_items()
        self.refresh_reports()
        self._log_audit("manual_stock_adjust", "item", str(item["item_id"]), f"delta={float(quantity_delta):.2f}, notes={notes}")

    def load_starter_cigarettes(self) -> None:
        try:
            created = self.inventory_service.load_starter_cigarette_items()
        except ValueError as exc:
            QMessageBox.warning(self, "Starter Data", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Starter Data Error", str(exc))
            return

        QMessageBox.information(
            self,
            "Starter Data Loaded",
            f"Created {created} cigarette SKUs for quick billing presets.",
        )
        self.refresh_inventory()
        self.refresh_billing_items()

    def delete_selected_item(self) -> None:
        item = self._selected_inventory_item()
        if item is None:
            return

        confirm = QMessageBox.question(
            self,
            "Delete Item",
            f"Delete item '{item['name']}' from active inventory?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        pin = self._require_admin_access("Delete Item")
        if pin is None:
            return

        try:
            self.inventory_service.delete_item(item_id=item["item_id"], admin_pin=pin)
        except ValueError as exc:
            QMessageBox.warning(self, "Delete Failed", str(exc))
            return

        QMessageBox.information(self, "Item Deleted", f"{item['name']} was removed from active inventory.")
        self.refresh_inventory()
        self.refresh_billing_items()
        self.refresh_reports()
        self._log_audit("item_delete", "item", str(item["item_id"]), item["name"])

    def _on_catalog_double_click(self, row: int, _: int) -> None:
        self.billing_items_table.selectRow(row)
        self.add_selected_item_to_cart()

    def add_item_to_cart_by_id(self, item_id: int, quantity: float | None = None) -> None:
        item = next((i for i in self.billing_items_cache if int(i["id"]) == int(item_id)), None)
        if item is None:
            QMessageBox.warning(self, "Item Missing", "Selected item is no longer available.")
            return

        qty = float(quantity if quantity is not None else self.qty_spin.value())
        existing_qty = float(self.cart.get(item_id, {}).get("quantity", 0))
        available_stock = float(item["stock_quantity"])
        if qty + existing_qty > available_stock:
            QMessageBox.warning(
                self,
                "Insufficient Stock",
                f"Requested quantity exceeds available stock ({available_stock:.2f}).",
            )
            return

        self.cart[item_id] = {
            "item_id": item_id,
            "name": item["name"],
            "quantity": qty + existing_qty,
            "unit_price": float(item["selling_price"]),
        }
        self.refresh_cart_table()

    def add_selected_item_to_cart(self) -> None:
        selected = self.billing_items_table.currentRow()
        if selected < 0:
            QMessageBox.information(self, "Select Item", "Please select an item first.")
            return

        item_id = int(self.billing_items_table.item(selected, 0).text())
        self.add_item_to_cart_by_id(item_id)

    def _selected_cart_item_id(self) -> int | None:
        selected = self.cart_table.currentRow()
        if selected < 0:
            QMessageBox.information(self, "Select Cart Item", "Please select an item in the cart.")
            return None

        return int(self.cart_table.item(selected, 0).text())

    def remove_selected_cart_item(self) -> None:
        item_id = self._selected_cart_item_id()
        if item_id is None:
            return

        self.cart.pop(item_id, None)
        self.refresh_cart_table()

    def increase_selected_cart_item_qty(self) -> None:
        item_id = self._selected_cart_item_id()
        if item_id is None:
            return

        self.add_item_to_cart_by_id(item_id, quantity=float(self.qty_spin.value()))

    def decrease_selected_cart_item_qty(self) -> None:
        item_id = self._selected_cart_item_id()
        if item_id is None:
            return

        line = self.cart.get(item_id)
        if line is None:
            return

        next_qty = float(line["quantity"]) - float(self.qty_spin.value())
        if next_qty <= 0:
            self.cart.pop(item_id, None)
        else:
            line["quantity"] = next_qty
            self.cart[item_id] = line

        self.refresh_cart_table()

    def refresh_cart_table(self) -> None:
        items = list(self.cart.values())
        self.cart_table.setRowCount(len(items))

        total = 0.0
        for row_index, item in enumerate(items):
            line_total = item["quantity"] * item["unit_price"]
            total += line_total

            self.cart_table.setItem(row_index, 0, QTableWidgetItem(str(item["item_id"])))
            self.cart_table.setItem(row_index, 1, QTableWidgetItem(item["name"]))
            self.cart_table.setItem(row_index, 2, QTableWidgetItem(f"{item['quantity']:.2f}"))
            self.cart_table.setItem(row_index, 3, QTableWidgetItem(f"{item['unit_price']:.2f}"))
            self.cart_table.setItem(row_index, 4, QTableWidgetItem(f"{line_total:.2f}"))

        self.total_label.setText(f"Total: INR {total:.2f}")

    def clear_cart(self) -> None:
        self.cart.clear()
        self.refresh_cart_table()
        if self.cart_file.exists():
            self.cart_file.unlink(missing_ok=True)

    def checkout(self) -> None:
        cart_items = [
            {"item_id": item["item_id"], "quantity": item["quantity"]}
            for item in self.cart.values()
        ]

        try:
            sale_result = self.sales_service.checkout(cart_items)
            sale = self.sales_service.sale_details(int(sale_result["sale_id"]))
        except ValueError as exc:
            QMessageBox.warning(self, "Checkout Error", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Unexpected Error", str(exc))
            return

        sale["total_amount"] = sale_result["total_amount"]
        printed_path = self._print_with_retry(sale)

        message = (
            f"Bill saved successfully.\n"
            f"Invoice: {sale_result['invoice_number']}\n"
            f"Sale ID: {sale_result['sale_id']}"
        )
        if printed_path:
            message += f"\nPrinted copy: {printed_path}"
        else:
            message += "\nBill saved but print skipped/failed."

        QMessageBox.information(self, "Checkout Complete", message)
        self.clear_cart()
        self.refresh_billing_items()
        self.refresh_inventory()
        self.refresh_reports()
        self._log_audit("sale_checkout", "sale", str(sale_result["sale_id"]), sale_result["invoice_number"])

    def _print_with_retry(self, sale_payload: dict) -> str | None:
        while True:
            try:
                path = self.print_service.print_bill(sale_payload)
                return str(path)
            except Exception as exc:
                response = QMessageBox.question(
                    self,
                    "Printer Error",
                    f"Bill is saved, but printing failed: {exc}\nRetry printing?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if response == QMessageBox.No:
                    return None

    def refresh_reports(self) -> None:
        start_date, end_date = self._iso_range_from_edits(self.report_from_date, self.report_to_date)
        summary = self.report_service.summary_between(start_date=start_date, end_date=end_date)
        self.sales_value.setText(f"INR {summary['sales']:.2f}")
        self.cogs_value.setText(f"INR {summary['cogs']:.2f}")
        self.gross_profit_value.setText(f"INR {summary['gross_profit']:.2f}")
        self.purchases_value.setText(f"INR {summary['purchases']:.2f}")
        self.expenses_value.setText(f"INR {summary['expenses']:.2f}")
        self.fixed_daily_value.setText(f"INR {summary['daily_fixed_overhead']:.2f}")
        self.net_value.setText(f"INR {summary['net_profit']:.2f}")

        fixed = summary.get("fixed_costs", {})
        self.rent_spin.setValue(float(fixed.get("rent", 0)))
        self.salary_spin.setValue(float(fixed.get("salary", 0)))
        self.maintenance_spin.setValue(float(fixed.get("maintenance", 0)))
        self.electricity_spin.setValue(float(fixed.get("electricity", 0)))
        self.monthly_fixed_total_label.setText(
            f"Monthly Fixed Total: INR {summary['monthly_fixed_total']:.2f}"
        )

        low_stock = self.report_service.low_stock()
        self.low_stock_table.setRowCount(len(low_stock))
        for row_index, item in enumerate(low_stock):
            self.low_stock_table.setItem(row_index, 0, self._report_item(item["name"]))
            self.low_stock_table.setItem(row_index, 1, self._report_item(f"{item['stock_quantity']:.2f}", True))
            self.low_stock_table.setItem(row_index, 2, self._report_item(f"{item['reorder_level']:.2f}", True))

        ledger_limit = int(self.ledger_limit_spin.value()) if hasattr(self, "ledger_limit_spin") else 500
        ledger = self.report_service.stock_ledger_between(start_date=start_date, end_date=end_date, limit=ledger_limit)
        self.ledger_table.setRowCount(len(ledger))
        for row_index, row in enumerate(ledger):
            self.ledger_table.setItem(row_index, 0, self._report_item(row["moved_at"]))
            self.ledger_table.setItem(row_index, 1, self._report_item(row["item_name"]))
            self.ledger_table.setItem(row_index, 2, self._report_item(f"{row['quantity_delta']:.2f}", True))
            self.ledger_table.setItem(row_index, 3, self._report_item(row["movement_type"]))
            self.ledger_table.setItem(
                row_index,
                4,
                self._report_item(str(row["reference_id"]) if row["reference_id"] else "-"),
            )
            self.ledger_table.setItem(row_index, 5, self._report_item(row["notes"] or ""))

        trend = self.report_service.sales_trend_between(start_date=start_date, end_date=end_date)
        self.sales_trend_table.setRowCount(len(trend))
        for row_index, row in enumerate(trend):
            self.sales_trend_table.setItem(row_index, 0, self._report_item(row["sale_date"]))
            self.sales_trend_table.setItem(row_index, 1, self._report_item(str(row["bill_count"]), True))
            self.sales_trend_table.setItem(
                row_index,
                2,
                self._report_item(f"{float(row['sales_total']):.2f}", True),
            )
            self.sales_trend_table.setItem(
                row_index,
                3,
                self._report_item(f"{float(row['cogs_total']):.2f}", True),
            )
            self.sales_trend_table.setItem(
                row_index,
                4,
                self._report_item(f"{float(row['gross_profit']):.2f}", True),
            )

        top_limit = int(self.top_items_limit_spin.value()) if hasattr(self, "top_items_limit_spin") else 20
        top_items = self.report_service.top_items_between(start_date=start_date, end_date=end_date, limit=top_limit)
        self.top_items_table.setRowCount(len(top_items))
        for row_index, row in enumerate(top_items):
            self.top_items_table.setItem(row_index, 0, self._report_item(row["name"]))
            self.top_items_table.setItem(
                row_index,
                1,
                self._report_item(f"{float(row['qty_sold']):.2f}", True),
            )
            self.top_items_table.setItem(
                row_index,
                2,
                self._report_item(f"{float(row['sales_value']):.2f}", True),
            )

        if hasattr(self, "audit_log_table"):
            logs = self.bookkeeping_service.list_audit_logs(limit=500)
            self.audit_log_table.setRowCount(len(logs))
            for row_index, log in enumerate(logs):
                self.audit_log_table.setItem(row_index, 0, self._report_item(log.get("created_at", "")))
                self.audit_log_table.setItem(row_index, 1, self._report_item(log.get("actor_role", "")))
                self.audit_log_table.setItem(row_index, 2, self._report_item(log.get("action_type", "")))
                self.audit_log_table.setItem(row_index, 3, self._report_item(log.get("entity_type", "")))
                self.audit_log_table.setItem(row_index, 4, self._report_item(log.get("entity_id", "")))
                self.audit_log_table.setItem(row_index, 5, self._report_item(log.get("details", "")))

    def close_day(self) -> None:
        selected_date, ok = QInputDialog.getText(
            self,
            "Close Day",
            "Enter date to close (YYYY-MM-DD):",
            text=date.today().isoformat(),
        )
        if not ok:
            return

        try:
            result = self.bookkeeping_service.close_day(selected_date.strip())
        except ValueError as exc:
            QMessageBox.warning(self, "Close Day", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Close Day Error", str(exc))
            return

        QMessageBox.information(
            self,
            "Day Closed",
            (
                f"Date: {result['closure_date']}\n"
                f"Sales: INR {result['sales']:.2f}\n"
                f"COGS: INR {result['cogs']:.2f}\n"
                f"Expenses: INR {result['expenses']:.2f}\n"
                f"Gross: INR {result['gross_profit']:.2f}\n"
                f"Net: INR {result['net_profit']:.2f}"
            ),
        )
        self._log_audit("day_close", "closure", result["closure_date"], "manual close-day")

    def backup_now(self) -> None:
        try:
            backup_path = create_backup(db_path=self.db_path)
        except Exception as exc:
            QMessageBox.critical(self, "Backup Failed", str(exc))
            return

        self._log_audit("backup_now", "backup", str(backup_path), "manual backup")
        QMessageBox.information(self, "Backup Created", f"Backup saved at:\n{backup_path}")

    def export_backup_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Export Folder")
        if not folder:
            return

        try:
            path = export_backup(destination_dir=folder, db_path=self.db_path)
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))
            return

        self._log_audit("backup_export", "backup", str(path), f"export folder={folder}")
        QMessageBox.information(self, "Export Complete", f"Backup exported to:\n{path}")

    def restore_backup_dialog(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Backup File", filter="DB Files (*.db)")
        if not file_path:
            return

        pin = self._require_admin_access("Restore Backup")
        if pin is None:
            return

        try:
            current_counts = self.bookkeeping_service.current_database_counts()
            backup_counts = inspect_backup_counts(file_path)
            preview = self._format_restore_preview(
                current_counts=current_counts,
                backup_counts=backup_counts,
                backup_file=file_path,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Restore Pre-check Failed", str(exc))
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Restore",
            preview,
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            restore_backup(backup_file=file_path, db_path=self.db_path)
        except Exception as exc:
            QMessageBox.critical(self, "Restore Failed", str(exc))
            return

        QMessageBox.information(
            self,
            "Restore Complete",
            "Backup restored. Please restart the application to reload all data safely.",
        )
        self._log_audit("backup_restore", "backup", file_path, "restore completed")

    def _save_pending_cart(self) -> None:
        self.cart_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.cart:
            self.cart_file.unlink(missing_ok=True)
            return

        payload = {"items": list(self.cart.values())}
        self.cart_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load_pending_cart(self) -> None:
        if not self.cart_file.exists():
            return

        try:
            payload = json.loads(self.cart_file.read_text(encoding="utf-8"))
            items = payload.get("items", [])
        except Exception:
            self.cart_file.unlink(missing_ok=True)
            return

        if not items:
            self.cart_file.unlink(missing_ok=True)
            return

        answer = QMessageBox.question(
            self,
            "Recover Pending Bill",
            "Found an unsaved cart from previous session. Restore it?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            self.cart_file.unlink(missing_ok=True)
            return

        self.cart = {int(item["item_id"]): item for item in items}
        self.refresh_cart_table()
