from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, QSize, Qt, QTimer, QEasingCurve, QPropertyAnimation, QParallelAnimationGroup
from PySide6.QtGui import QColor, QKeySequence, QShortcut, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
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
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSpinBox,
    QStackedWidget,
    QPushButton,
    QSizePolicy,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from app.services.bookkeeping_service import BookkeepingService
from app.services.inventory_service import InventoryService
from app.services.license_service import LicenseService
from app.services.print_service import PrintService
from app.services.report_service import ReportService
from app.services.sales_service import SalesService
from app.ui.controllers.billing_controller import BillingController
from app.ui.controllers.inventory_controller import InventoryController
from app.ui.controllers.main_window_ops_controller import MainWindowOpsController
from app.ui.controllers.reports_controller import ReportsController
from app.ui.export_helpers import table_rows_for_csv, write_csv_file
from app.ui.premium_theme import premium_pos_stylesheet
from app.ui.views.billing_view import (
    apply_billing_dashboard_style,
    build_billing_tab,
    make_billing_stat_card,
    style_billing_table,
)
from app.ui.views.inventory_view import apply_inventory_panel_style, build_inventory_tab



class MainWindow(QMainWindow):
    MIN_WINDOW_WIDTH = 900
    MIN_WINDOW_HEIGHT = 680
    
    THEME = {
        "bg_deep": "#eef3f8",
        "bg_surface": "#ffffff",
        "bg_surface_light": "#f8fafc",
        "primary_soft": "#eaf2ff",
        "accent_primary": "#0f766e",
        "primary_hover": "#0b5e54",
        "accent_gold": "#c97900",
        "success": "#16a34a",
        "danger": "#b91c1c",
        "warning": "#c97900",
        "text_primary": "#111827",
        "text_medium": "#475569",
        "text_low": "#8190a6",
        "border": "#d7e0eb",
        "border_bold": "#98a8bd"
    }

    def __init__(
        self,
        inventory_service: InventoryService,
        sales_service: SalesService,
        bookkeeping_service: BookkeepingService,
        report_service: ReportService,
        print_service: PrintService,
        db_path: str = "data/cafe.db",
        app_version: str = "0.0.0",
    ) -> None:
        super().__init__()
        self.inventory_service = inventory_service
        self.sales_service = sales_service
        self.bookkeeping_service = bookkeeping_service
        self.report_service = report_service
        self.print_service = print_service
        self.db_path = db_path
        self.app_version = app_version
        self.license_service = LicenseService(self.bookkeeping_service)
        self._activation_failed = False

        self.cart: dict[int, dict] = {}
        self.billing_items_cache: list[dict] = []
        self.inventory_items_cache: list[dict] = []
        self.cigarette_shortcuts: list[QShortcut] = []
        self.purchase_cart: list[dict] = []
        self.purchase_item_cache: dict[int, dict] = {}
        self.editing_purchase_id: int | None = None
        self.current_role = (self.bookkeeping_service.get_setting("current_role", "cashier") or "cashier").lower()
        self._updating_inventory_table = False
        self._updating_purchase_table = False
        self._updating_expense_table = False
        self.cart_file = Path("data/pending_cart.json")
        self.sidebar_expanded_width = 220
        self.sidebar_collapsed_width = 78
        self.sidebar_collapsed = False
        self._sidebar_anim_group: QParallelAnimationGroup | None = None
        self.billing_controller = BillingController(self)
        self.inventory_controller = InventoryController(self)
        self.ops_controller = MainWindowOpsController(self)
        self.reports_controller = ReportsController(self)

        self.setWindowTitle(f"Cafe POS v{self.app_version}")
        self.setMinimumSize(self.MIN_WINDOW_WIDTH, self.MIN_WINDOW_HEIGHT)
        self.resize(1320, 820)
        
        # Set Window Icon
        icon_path = os.path.join(os.path.dirname(__file__), "app_icon.ico")
        if not os.path.exists(icon_path):
            # Fallback if it's in the project root
            icon_path = "app_icon.ico"
            
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._build_professional_shell_header()

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("AppPageStack")
        self.tabs = self.page_stack

        self.billing_tab = self._build_billing_tab()
        self.recipe_tab = self._build_recipe_tab()
        self.inventory_tab = self._build_inventory_tab()
        self.purchases_tab = self._build_purchases_tab()
        self.expenses_tab = self._build_expenses_tab()
        self.reports_tab = self._build_reports_tab()

        self.page_titles = ["Billing", "Recipes", "Inventory", "Purchases", "Expenses", "Reports"]
        self.page_widgets = [
            self.billing_tab,
            self.recipe_tab,
            self.inventory_tab,
            self.purchases_tab,
            self.expenses_tab,
            self.reports_tab,
        ]

        shell_root = QWidget()
        shell_root.setObjectName("AppShellRoot")
        shell_layout = QHBoxLayout(shell_root)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("AppSidebar")
        self.sidebar.setMinimumWidth(self.sidebar_expanded_width)
        self.sidebar.setMaximumWidth(self.sidebar_expanded_width)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(10, 14, 10, 14)
        self.sidebar_layout.setSpacing(8)

        self.sidebar_toggle_btn = QToolButton()
        self.sidebar_toggle_btn.setObjectName("SidebarToggleButton")
        self.sidebar_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.sidebar_toggle_btn.setToolTip("Collapse sidebar")
        self.sidebar_toggle_btn.clicked.connect(self._toggle_sidebar)
        self.sidebar_layout.addWidget(self.sidebar_toggle_btn, alignment=Qt.AlignLeft)

        self.sidebar_nav_buttons: list[QPushButton] = []
        for index, title in enumerate(self.page_titles):
            page = self.page_widgets[index]
            self.page_stack.addWidget(page)
            btn = QPushButton(title)
            btn.setObjectName("SidebarNavButton")
            btn.setCheckable(True)
            btn.setProperty("fullLabel", title)
            btn.setProperty("compact", False)
            btn.setIcon(self._sidebar_icon_for_page(title))
            btn.setIconSize(QSize(16, 16))
            btn.setMinimumHeight(42)
            btn.setMinimumWidth(184)
            btn.setMaximumWidth(184)
            btn.setToolTip(title)
            btn.clicked.connect(lambda _, i=index: self._switch_page(i))
            self.sidebar_layout.addWidget(btn)
            self.sidebar_nav_buttons.append(btn)

        self.sidebar_layout.addStretch(1)

        shell_layout.addWidget(self.sidebar)
        shell_layout.addWidget(self.page_stack, 1)
        self.setCentralWidget(shell_root)

        self.page_stack.currentChanged.connect(self._on_tab_changed)
        self._set_sidebar_collapsed(False, animate=False)
        self._switch_page(0)

        self._apply_professional_shell_theme()
        self._setup_status_bar()

        if not self.ops_controller.ensure_license_activation():
            self._activation_failed = True
            QTimer.singleShot(0, QApplication.instance().quit)
            return

        self._wire_shortcuts()

        self.cart_timer = QTimer(self)
        self.cart_timer.setInterval(5000)
        self.cart_timer.timeout.connect(self._save_pending_cart)
        self.cart_timer.start()

        self.auto_backup_timer = QTimer(self)
        self.auto_backup_timer.timeout.connect(self._run_scheduled_backup)
        self._configure_auto_backup_timer()

        self.shell_clock_timer = QTimer(self)
        self.shell_clock_timer.setInterval(1000)
        self.shell_clock_timer.timeout.connect(self._update_shell_status)
        self.shell_clock_timer.start()

        self.refresh_all()
        self._load_pending_cart()
        self._update_shell_status()
        self._apply_role_permissions()

    def minimumSizeHint(self) -> QSize:
        # Keep window constraints practical so the app can fit smaller screens.
        return QSize(self.MIN_WINDOW_WIDTH, self.MIN_WINDOW_HEIGHT)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._fit_window_to_available_screen)

    def _fit_window_to_available_screen(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        max_width = max(640, available.width())
        max_height = max(520, available.height())

        # Never exceed available geometry so taskbar does not overlay content.
        self.setMaximumSize(max_width, max_height)

        min_width = min(self.MIN_WINDOW_WIDTH, max_width)
        min_height = min(self.MIN_WINDOW_HEIGHT, max_height)
        self.setMinimumSize(min_width, min_height)

        target_width = min(max(self.width(), min_width), max_width)
        target_height = min(max(self.height(), min_height), max_height)
        self.setGeometry(available.x(), available.y(), target_width, target_height)

    def _on_tab_changed(self, tab_index: int) -> None:
        self._set_active_sidebar(tab_index)
        tab_widget = self.tabs.widget(tab_index)
        if tab_widget is self.billing_tab:
            self.refresh_billing_items()
            QTimer.singleShot(0, self._focus_billing_search)
        elif tab_widget is self.recipe_tab:
            self.refresh_recipe_tab()
        elif tab_widget is self.inventory_tab:
            self.refresh_inventory()
            QTimer.singleShot(0, self._focus_inventory_name)
        elif tab_widget is self.purchases_tab:
            self.refresh_purchases_tab()
        elif tab_widget is self.expenses_tab:
            self.refresh_expenses_tab()
        elif tab_widget is self.reports_tab:
            self.refresh_reports()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_adaptive_layout()

    def _apply_adaptive_layout(self) -> None:
        width = self.width()
        is_compact = width < 1200

        # Billing Adaptations
        if hasattr(self, "billing_tab"):
            self._set_billing_compact_mode(is_compact)
            if hasattr(self, "total_label"):
                size = 28 if is_compact else 38
                self.total_label.setStyleSheet(f"font-size: {size}px; font-weight: 900; color: {self.THEME['accent_primary']};")

        # Reports Adaptations
        if hasattr(self, "reports_cards_grid") and hasattr(self, "metric_cards"):
            cols = 2 if is_compact else 4
            if not hasattr(self, "_last_reports_cols") or self._last_reports_cols != cols:
                self._last_reports_cols = cols
                # Remove all from grid
                for card in self.metric_cards:
                    self.reports_cards_grid.removeWidget(card)
                # Re-add with new col count
                for index, card in enumerate(self.metric_cards):
                    row = index // cols
                    col = index % cols
                    self.reports_cards_grid.addWidget(card, row, col)

        if hasattr(self, "top_items_table"):
            self._apply_report_table_width_profiles()

    def _f(self, value, default: float = 0.0) -> float:
        """Safe float conversion for database fields."""
        try:
            if value is None: return default
            return float(value)
        except (ValueError, TypeError):
            return default

    def _i(self, value, default: int = 0) -> int:
        """Safe int conversion for database fields."""
        try:
            if value is None: return default
            return int(float(value))
        except (ValueError, TypeError):
            return default

    def _wire_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.checkout)
        QShortcut(QKeySequence("F5"), self, activated=self.refresh_all)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.close_day)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._focus_billing_search)
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=self._focus_billing_qty)
        QShortcut(QKeySequence("Return"), self, activated=self._try_checkout_from_enter)
        QShortcut(QKeySequence("F11"), self, activated=self._toggle_full_screen)

    def _toggle_full_screen(self) -> None:
        if self.isFullScreen():
            self.showMaximized()
            return
        self.showFullScreen()

    def _switch_page(self, page_index: int) -> None:
        if not hasattr(self, "page_stack"):
            return
        if page_index < 0 or page_index >= self.page_stack.count():
            return
        self.page_stack.setCurrentIndex(page_index)

    def _set_active_sidebar(self, active_index: int) -> None:
        if not hasattr(self, "sidebar_nav_buttons"):
            return
        for idx, btn in enumerate(self.sidebar_nav_buttons):
            btn.blockSignals(True)
            btn.setChecked(idx == active_index)
            btn.blockSignals(False)

    def _sidebar_icon_for_page(self, title: str) -> QIcon:
        icon_map = {
            "Billing": QStyle.SP_DialogApplyButton,
            "Recipes": QStyle.SP_FileDialogContentsView,
            "Inventory": QStyle.SP_DriveHDIcon,
            "Purchases": QStyle.SP_DialogOpenButton,
            "Expenses": QStyle.SP_DialogSaveButton,
            "Reports": QStyle.SP_FileDialogDetailedView,
        }
        return self.style().standardIcon(icon_map.get(title, QStyle.SP_FileIcon))

    def _toggle_sidebar(self) -> None:
        self._set_sidebar_collapsed(not self.sidebar_collapsed, animate=True)

    def _set_sidebar_collapsed(self, collapsed: bool, animate: bool = True) -> None:
        if not hasattr(self, "sidebar"):
            return

        collapsed = bool(collapsed)
        target_sidebar_width = self.sidebar_collapsed_width if collapsed else self.sidebar_expanded_width
        target_button_width = 46 if collapsed else 184

        self.sidebar_collapsed = collapsed
        self._update_sidebar_toggle_button()

        if not animate:
            self.sidebar.setMinimumWidth(target_sidebar_width)
            self.sidebar.setMaximumWidth(target_sidebar_width)
            for btn in self.sidebar_nav_buttons:
                btn.setMinimumWidth(target_button_width)
                btn.setMaximumWidth(target_button_width)
            self._apply_sidebar_visual_state(collapsed)
            return

        if not collapsed:
            for btn in self.sidebar_nav_buttons:
                btn.setText(str(btn.property("fullLabel") or btn.text()))

        self._sidebar_anim_group = QParallelAnimationGroup(self)
        duration = 220

        for prop_name in (b"minimumWidth", b"maximumWidth"):
            anim = QPropertyAnimation(self.sidebar, prop_name, self)
            anim.setDuration(duration)
            anim.setStartValue(self.sidebar.width())
            anim.setEndValue(target_sidebar_width)
            anim.setEasingCurve(QEasingCurve.InOutCubic)
            self._sidebar_anim_group.addAnimation(anim)

        for btn in self.sidebar_nav_buttons:
            for prop_name in (b"minimumWidth", b"maximumWidth"):
                anim = QPropertyAnimation(btn, prop_name, self)
                anim.setDuration(duration)
                anim.setStartValue(btn.width())
                anim.setEndValue(target_button_width)
                anim.setEasingCurve(QEasingCurve.InOutCubic)
                self._sidebar_anim_group.addAnimation(anim)

        self._sidebar_anim_group.finished.connect(lambda: self._apply_sidebar_visual_state(collapsed))
        self._sidebar_anim_group.start()

    def _update_sidebar_toggle_button(self) -> None:
        if not hasattr(self, "sidebar_toggle_btn"):
            return
        if self.sidebar_collapsed:
            self.sidebar_toggle_btn.setArrowType(Qt.RightArrow)
            self.sidebar_toggle_btn.setToolTip("Expand sidebar")
        else:
            self.sidebar_toggle_btn.setArrowType(Qt.LeftArrow)
            self.sidebar_toggle_btn.setToolTip("Collapse sidebar")

    def _apply_sidebar_visual_state(self, collapsed: bool) -> None:
        for btn in self.sidebar_nav_buttons:
            full_label = str(btn.property("fullLabel") or btn.text())
            btn.setText("" if collapsed else full_label)
            btn.setToolTip(full_label)
            btn.setProperty("compact", collapsed)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        if hasattr(self, "sidebar_layout"):
            self.sidebar_layout.setContentsMargins(8, 10, 8, 10) if collapsed else self.sidebar_layout.setContentsMargins(10, 14, 10, 14)
        self._set_active_sidebar(self.page_stack.currentIndex())

    def _build_professional_shell_header(self) -> None:
        header = QWidget()
        header.setObjectName("AppShellHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        title = QLabel("Cafe POS")
        title.setObjectName("AppShellTitle")
        subtitle = QLabel("Retail Operations Console")
        subtitle.setObjectName("AppShellSubtitle")

        # Logo next to title
        logo_label = QLabel()
        logo_path = "app_logo_circular.png"
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            logo_label.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        title_stack = QVBoxLayout()
        title_stack.setContentsMargins(0, 0, 0, 0)
        title_stack.setSpacing(1)
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)

        self.header_role_badge = QLabel("ROLE: CASHIER")
        self.header_role_badge.setObjectName("HeaderRoleBadge")

        layout.addWidget(logo_label)
        layout.addLayout(title_stack)
        layout.addStretch()
        layout.addWidget(self.header_role_badge)

        self.setMenuWidget(header)

    def _apply_professional_shell_theme(self) -> None:
        T = self.THEME
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {T['bg_deep']};
            }}
            QWidget {{
                color: {T['text_primary']};
                font-family: 'Segoe UI Variable', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            }}
            #AppShellRoot {{
                background-color: {T['bg_deep']};
            }}
            #AppShellHeader {{
                background-color: {T['bg_surface']};
                border-bottom: 2px solid {T['border']};
            }}
            #AppShellTitle {{
                font-size: 16px;
                font-weight: 800;
                color: {T['accent_primary']};
            }}
            #AppShellSubtitle {{
                font-size: 11px;
                color: {T['text_medium']};
                letter-spacing: 1px;
            }}
            #HeaderRoleBadge {{
                padding: 4px 12px;
                border: 1px solid {T['accent_primary']};
                border-radius: 12px;
                background-color: transparent;
                color: {T['accent_primary']};
                font-weight: 700;
                font-size: 10px;
            }}
            #AppSidebar {{
                background-color: {T['bg_surface']};
                border-right: 1px solid {T['border']};
            }}
            QToolButton#SidebarToggleButton {{
                background-color: {T['bg_surface_light']};
                color: {T['accent_primary']};
                border: 1px solid {T['border']};
                border-radius: 8px;
                padding: 6px;
                min-width: 28px;
                min-height: 28px;
            }}
            QToolButton#SidebarToggleButton:hover {{
                border-color: {T['accent_primary']};
                background-color: #eaf2ff;
            }}
            QPushButton#SidebarNavButton {{
                text-align: left;
                background-color: transparent;
                color: {T['text_medium']};
                border: 1px solid transparent;
                border-radius: 10px;
                padding: 10px 12px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton#SidebarNavButton[compact="true"] {{
                text-align: center;
                padding: 10px 6px;
            }}
            QPushButton#SidebarNavButton:hover {{
                background-color: {T['bg_surface_light']};
                color: {T['text_primary']};
            }}
            QPushButton#SidebarNavButton:checked {{
                background-color: #dbeafe;
                color: {T['accent_primary']};
                border-color: #bfdbfe;
                font-weight: 800;
            }}
            #AppPageStack {{
                background-color: {T['bg_deep']};
                border: none;
            }}
            QSplitter::handle {{
                background-color: {T['border']};
            }}
            QSplitter::handle:hover {{
                background-color: {T['accent_primary']};
            }}
            QStatusBar {{
                background-color: {T['bg_surface']};
                border-top: 1px solid {T['border']};
                color: {T['text_medium']};
            }}
            QStatusBar QLabel {{
                color: {T['text_medium']};
                padding: 0 10px;
            }}
            
            /* Generic Table Styles */
            QTableWidget {{
                background-color: {T['bg_surface']};
                border: 1.5px solid {T['border_bold']};
                gridline-color: {T['border_bold']};
                border-radius: 8px;
                outline: 0;
                color: {T['text_primary']};
            }}
            QHeaderView::section {{
                background-color: {T['bg_deep']};
                color: {T['text_primary']};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {T['border_bold']};
                font-weight: bold;
                text-transform: uppercase;
                font-size: 11px;
            }}
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {T['border']};
            }}
            QTableWidget::item:selected {{
                background-color: #e2e8f0;
                color: {T['text_primary']};
            }}

            /* ScrollBars */
            QScrollBar:vertical {{
                background: {T['bg_deep']};
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {T['border']};
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}

            /* Buttons - Supporting both Class and ObjectName */
            QPushButton#PayAction, QPushButton.PayAction {{
                background-color: {T['success']};
                color: white;
                font-size: 20px;
                font-weight: 900;
                border-radius: 10px;
                padding: 10px;
            }}
            QPushButton#PayAction:hover, QPushButton.PayAction:hover {{
                background-color: #15803d;
            }}
            
            QPushButton#StandardAction, QPushButton.StandardAction, 
            QPushButton#PrimaryPurchaseButton, QPushButton#SecondaryPurchaseButton,
            QPushButton#PrimaryInventoryButton, QToolButton#StandardAction, QToolButton#PrimaryInventoryButton {{
                background-color: {T['accent_primary']};
                color: white;
                font-size: 13px;
                font-weight: 800;
                border-radius: 8px;
                padding: 6px 14px;
                border: none;
            }}
            QPushButton#StandardAction:hover, QPushButton.StandardAction:hover,
            QPushButton#PrimaryPurchaseButton:hover, QPushButton#SecondaryPurchaseButton:hover,
            QPushButton#PrimaryInventoryButton:hover, QToolButton#StandardAction:hover {{
                background-color: #1d4ed8;
            }}
            
            QPushButton#DangerAction, QPushButton.DangerAction, QToolButton#DangerAction {{
                background-color: {T['danger']};
                color: white;
                font-size: 13px;
                font-weight: 800;
                border-radius: 8px;
                padding: 6px 14px;
                border: none;
            }}
            QPushButton#DangerAction:hover, QPushButton.DangerAction:hover, QToolButton#DangerAction:hover {{
                background-color: #b91c1c;
            }}
            
            QPushButton#CategoryTab, QPushButton.CategoryTab {{
                background-color: {T['bg_surface']};
                color: {T['text_primary']};
                font-size: 13px;
                font-weight: 700;
                border: 1.5px solid {T['border_bold']};
                border-radius: 18px;
                padding: 6px 16px;
                margin: 4px;
            }}
            QPushButton#CategoryTab:checked, QPushButton.CategoryTab:checked {{
                background-color: {T['text_primary']};
                color: white;
                border-color: {T['text_primary']};
            }}
            
            QPushButton#QuickAddItem, QPushButton.QuickAddItem {{
                background-color: {T['bg_surface']};
                color: {T['text_primary']};
                font-size: 13px;
                font-weight: 800;
                border-radius: 14px;
                padding: 10px;
                border: 1.5px solid {T['border_bold']};
            }}
            QPushButton#QuickAddItem:hover, QPushButton.QuickAddItem:hover {{
                background-color: {T['bg_surface_light']};
                border-color: {T['accent_primary']};
                color: {T['accent_primary']};
            }}

            #AppToast {{
                background-color: {T['text_primary']};
                color: white;
                font-size: 16px;
                font-weight: 800;
                border-radius: 20px;
                padding: 12px 30px;
            }}
            
            /* Inputs, Lists & Menus */
            QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QDateEdit, QListWidget {{
                background-color: {T['bg_surface']};
                border: 1.5px solid {T['border_bold']};
                border-radius: 6px;
                padding: 6px;
                color: {T['text_primary']};
            }}
            QComboBox QAbstractItemView {{
                background-color: {T['bg_surface']};
                color: {T['text_primary']};
                selection-background-color: {T['bg_surface_light']};
                selection-color: {T['accent_primary']};
                outline: 0;
                border: 1px solid {T['border_bold']};
            }}
            QCalendarWidget QWidget {{
                background-color: {T['bg_surface']};
                color: {T['text_primary']};
            }}
            QCalendarWidget QAbstractItemView:enabled {{
                background-color: {T['bg_surface']};
                color: {T['text_primary']};
                selection-background-color: {T['accent_primary']};
                selection-color: white;
            }}
            QCalendarWidget QToolButton {{
                color: {T['text_primary']};
                background-color: transparent;
                border: none;
                font-weight: bold;
            }}
            QCalendarWidget QSpinBox {{
                background-color: {T['bg_surface']};
                color: {T['text_primary']};
                border: none;
            }}
            QListWidget::item {{
                padding: 6px;
                border-bottom: 1px solid {T['border']};
            }}
            QListWidget::item:selected {{
                background-color: {T['bg_surface_light']};
                color: {T['accent_primary']};
            }}
            QMenu {{
                background-color: {T['bg_surface']};
                border: 1px solid {T['border_bold']};
                padding: 5px;
                color: {T['text_primary']};
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {T['bg_surface_light']};
                color: {T['accent_primary']};
            }}
            
            QLineEdit:focus {{
                border-color: {T['accent_primary']};
                background-color: {T['bg_surface_light']};
            }}
            
            QGroupBox {{
                font-weight: 800;
                border: 1.5px solid {T['border_bold']};
                border-radius: 12px;
                margin-top: 15px;
                padding-top: 20px;
                color: {T['text_primary']};
                background-color: {T['bg_surface']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {T['text_primary']};
            }}
            
            /* Sub-Tab Styling (Reports) */
            #ReportsSubTabs::pane {{
                border: 1px solid {T['border']};
                background-color: {T['bg_deep']};
                border-radius: 8px;
            }}
            #ReportsSubTabs QTabBar::tab {{
                background-color: {T['bg_surface']};
                color: {T['text_medium']};
                padding: 8px 16px;
                border: 1px solid {T['border']};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 2px;
            }}
            #ReportsSubTabs QTabBar::tab:selected {{
                background-color: {T['bg_deep']};
                color: {T['accent_primary']};
                border-bottom-color: {T['bg_deep']};
                font-weight: bold;
            }}
            
            /* Global Backgrounds & Scroll Areas */
            QMainWindow, QScrollArea, QScrollArea > QWidget {{
                background-color: {T['bg_deep']};
                border: none;
            }}
            #BillingCategoryContainer, #BillingCatalogGroup, #RecipePanel, #InventoryPanel, #PurchasesPanel, #ExpensesPanel, #ReportsPanel {{
                background-color: {T['bg_deep']};
            }}
            #OpsHintLabel {{
                color: {T['text_medium']};
                font-size: 12px;
                font-weight: 600;
                padding: 2px 1px;
            }}
            #OpsFilterBar {{
                border: 1.5px solid {T['border_bold']};
                border-radius: 10px;
                background-color: {T['bg_surface']};
                padding: 8px;
            }}
            #OpsSectionCard {{
                border: 1.5px solid {T['border_bold']};
                border-radius: 12px;
                background-color: {T['bg_surface']};
            }}
            
            /* Global Header View */
            QHeaderView, QHeaderView::section {{
                background-color: {T['bg_deep']};
                border: none;
                color: {T['text_primary']};
            }}

            /* Dialogs & Messages */
            QDialog, QMessageBox, QInputDialog {{
                background-color: {T['bg_surface']};
                color: {T['text_primary']};
            }}
            QMessageBox QLabel, QDialog QLabel {{
                color: {T['text_primary']};
                font-size: 14px;
            }}
            QDialog QPushButton, QMessageBox QPushButton, QInputDialog QPushButton {{
                background-color: {T['bg_surface']};
                color: {T['text_primary']};
                border: 1.5px solid {T['border_bold']};
                border-radius: 8px;
                padding: 6px 18px;
                font-weight: bold;
                min-width: 90px;
            }}
            QDialog QPushButton:hover, QMessageBox QPushButton:hover, QInputDialog QPushButton:hover {{
                background-color: {T['bg_surface_light']};
                border-color: {T['accent_primary']};
                color: {T['accent_primary']};
            }}
            QDialog QLineEdit {{
                min-width: 250px;
            }}
        """ + premium_pos_stylesheet(T))

    def _setup_status_bar(self) -> None:
        self.status_role_label = QLabel()
        self.status_tab_label = QLabel()
        self.status_license_label = QLabel()
        self.status_db_label = QLabel(f"DB: {Path(self.db_path).name}")
        self.status_time_label = QLabel()

        self.statusBar().addPermanentWidget(self.status_role_label)
        self.statusBar().addPermanentWidget(self.status_tab_label)
        self.statusBar().addPermanentWidget(self.status_license_label)
        self.statusBar().addPermanentWidget(self.status_db_label)
        self.statusBar().addPermanentWidget(self.status_time_label)

        # Setup Toast Warning Overlay
        self.toast_label = QLabel(self)
        self.toast_label.setObjectName("AppToast")
        self.toast_label.setAlignment(Qt.AlignCenter)
        self.toast_label.setWindowFlags(Qt.FramelessWindowHint | Qt.ToolTip)
        self.toast_label.hide()

    def show_toast(self, message: str, is_error: bool = False) -> None:
        self.toast_label.setText(message)
        if is_error:
            self.toast_label.setStyleSheet("background-color: #e74c3c; color: white;")
        else:
            self.toast_label.setStyleSheet("background-color: #27ae60; color: white;")
            
        self.toast_label.adjustSize()
        x = self.geometry().center().x() - self.toast_label.width() // 2
        y = self.geometry().center().y() - 100
        self.toast_label.move(x, y)
        self.toast_label.raise_()
        self.toast_label.show()
        QTimer.singleShot(1500, self.toast_label.hide)

    def _update_shell_status(self) -> None:
        role = self.current_role.upper() if self.current_role else "CASHIER"
        self.status_role_label.setText(f"ROLE: {role}")
        if hasattr(self, "header_role_badge"):
            self.header_role_badge.setText(f"ROLE: {role}")

        if hasattr(self, "tabs") and self.tabs.count() > 0:
            current_index = self.tabs.currentIndex()
            tab_name = (
                self.page_titles[current_index]
                if hasattr(self, "page_titles") and 0 <= current_index < len(self.page_titles)
                else f"Module {current_index + 1}"
            )
            self.status_tab_label.setText(f"MODULE: {tab_name}")

        if hasattr(self, "license_service"):
            self.status_license_label.setText(f"LICENSE: {self.license_service.summary_text()}")

        self.status_time_label.setText(datetime.now().strftime("%d %b %Y  %I:%M:%S %p"))

    def _build_placeholder_tab(self, message: str) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        return tab

    def _build_billing_tab(self) -> QWidget:
        return build_billing_tab(self)

        tab = QWidget()
        tab.setObjectName("BillingDashboard")
        root_layout = QVBoxLayout(tab)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(8)

        hero_frame = QFrame()
        hero_frame.setObjectName("BillingHero")
        hero_layout = QHBoxLayout(hero_frame)
        hero_layout.setContentsMargins(12, 8, 12, 8)

        hero_text_layout = QVBoxLayout()
        hero_title = QLabel("Billing Dashboard")
        hero_title.setObjectName("BillingHeroTitle")
        hero_text_layout.addWidget(hero_title)

        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(6)
        lines_card, self.billing_cart_lines_value = self._make_billing_stat_card("LINES")
        qty_card, self.billing_cart_qty_value = self._make_billing_stat_card("UNITS")
        total_card, self.billing_total_value = self._make_billing_stat_card("BILL")
        stats_layout.addWidget(lines_card)
        stats_layout.addWidget(qty_card)
        stats_layout.addWidget(total_card)

        hero_layout.addLayout(hero_text_layout)
        hero_layout.addStretch()
        hero_layout.addLayout(stats_layout)
        hero_frame.setMaximumHeight(100)
        hero_frame.setMinimumHeight(80)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # --- Left Panel: Catalog & Quick Add ---
        catalog_group = QWidget()
        catalog_group.setObjectName("BillingCatalogGroup")
        catalog_layout = QVBoxLayout(catalog_group)
        catalog_layout.setContentsMargins(10, 0, 10, 10)
        catalog_layout.setSpacing(12)

        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search items (Alt+F)...")
        self.search_input.setObjectName("BillingSearch")
        self.search_input.setMinimumHeight(40)
        self.search_input.textChanged.connect(self.apply_billing_filter)
        catalog_layout.addWidget(self.search_input)

        # Tabs Scroll Area
        self.billing_category_tabs_layout = QHBoxLayout()
        self.billing_category_tabs_layout.setSpacing(10)
        self.billing_category_tabs_layout.setAlignment(Qt.AlignLeft)
        category_container = QWidget()
        category_container.setObjectName("BillingCategoryContainer")
        category_container.setLayout(self.billing_category_tabs_layout)
        category_scroll = QScrollArea()
        category_scroll.setWidgetResizable(True)
        category_scroll.setMaximumHeight(65)
        category_scroll.setFrameShape(QFrame.NoFrame)
        category_scroll.setWidget(category_container)
        category_scroll.setFixedHeight(65)
        catalog_layout.addWidget(category_scroll, 0)

        # Grid Scroll Area
        self.billing_quick_grid_layout = QGridLayout()
        self.billing_quick_grid_layout.setSpacing(14)
        self.billing_quick_grid_layout.setContentsMargins(16, 16, 16, 16)
        self.billing_quick_grid_layout.setAlignment(Qt.AlignTop)

        grid_container = QWidget()
        grid_container.setObjectName("BillingGridContainer")
        grid_container.setLayout(self.billing_quick_grid_layout)

        grid_scroll = QScrollArea()
        grid_scroll.setObjectName("BillingGridScroll")
        grid_scroll.setWidgetResizable(True)
        grid_scroll.setFrameShape(QFrame.NoFrame)
        grid_scroll.setWidget(grid_container)
        grid_scroll.setMinimumHeight(400)
        catalog_layout.addWidget(grid_scroll, 1)
        
        self.billing_empty_state_label = QLabel("")
        self.billing_empty_state_label.setVisible(False)

        # --- Right Panel: Cart & Payment ---
        cart_group = QWidget()
        cart_group.setObjectName("BillingCartGroup")
        cart_layout = QVBoxLayout(cart_group)
        cart_layout.setContentsMargins(10, 10, 10, 10)
        cart_layout.setSpacing(10)

        cart_header = QHBoxLayout()
        cart_title = QLabel("Current Bill")
        cart_title.setObjectName("BillingPanelTitle")
        self.cart_summary_label = QLabel("0 lines | 0.00 units")
        self.cart_summary_label.setObjectName("BillingPanelMeta")
        cart_header.addWidget(cart_title)
        cart_header.addStretch()
        cart_header.addWidget(self.cart_summary_label)

        self.cart_table = QTableWidget(0, 4)
        self.cart_table.setHorizontalHeaderLabels(["Item Name", "Qty", "Price", "Total"])
        self.cart_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cart_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cart_table.horizontalHeader().setStretchLastSection(True)
        self.cart_table.verticalHeader().setDefaultSectionSize(48)
        self._style_billing_table(self.cart_table)

        self.cart_empty_label = QLabel("No items in bill")
        self.cart_empty_label.setObjectName("CartEmptyState")
        self.cart_empty_label.setAlignment(Qt.AlignCenter)

        cart_actions_row = QHBoxLayout()
        plus_qty_btn = QPushButton("+ Qty")
        plus_qty_btn.setObjectName("StandardAction")
        plus_qty_btn.clicked.connect(self.increase_selected_cart_item_qty)
        minus_qty_btn = QPushButton("- Qty")
        minus_qty_btn.setObjectName("StandardAction")
        minus_qty_btn.clicked.connect(self.decrease_selected_cart_item_qty)
        remove_selected_btn = QPushButton("Remove")
        remove_selected_btn.setObjectName("DangerAction")
        remove_selected_btn.clicked.connect(self.remove_selected_cart_item)
        clear_btn = QPushButton("Clear Cart")
        clear_btn.setObjectName("DangerAction")
        clear_btn.clicked.connect(self.clear_cart)

        cart_actions_row.addWidget(plus_qty_btn)
        cart_actions_row.addWidget(minus_qty_btn)
        cart_actions_row.addStretch()
        cart_actions_row.addWidget(remove_selected_btn)
        cart_actions_row.addWidget(clear_btn)

        # Payment Panel
        total_panel = QFrame()
        total_panel.setObjectName("BillingTotalPanel")
        total_panel_layout = QVBoxLayout(total_panel)
        total_panel_layout.setContentsMargins(5, 5, 5, 5)
        total_panel_layout.setSpacing(12)

        self.total_label = QLabel("TOTAL: INR 0.00")
        self.total_label.setObjectName("BillingTotalLabel")
        self.total_label.setAlignment(Qt.AlignCenter)
        
        pay_row = QHBoxLayout()
        pay_row.setSpacing(10)
        pay_cash_btn = QPushButton("Pay CASH")
        pay_cash_btn.setObjectName("PayAction")
        pay_cash_btn.setProperty("payment", "cash")
        pay_cash_btn.clicked.connect(lambda: self._trigger_petpooja_checkout("cash"))
        
        pay_upi_btn = QPushButton("Pay UPI")
        pay_upi_btn.setObjectName("PayAction")
        pay_upi_btn.setProperty("payment", "upi")
        pay_upi_btn.clicked.connect(lambda: self._trigger_petpooja_checkout("upi"))
        
        pay_card_btn = QPushButton("Pay CARD")
        pay_card_btn.setObjectName("PayAction")
        pay_card_btn.setProperty("payment", "card")
        pay_card_btn.clicked.connect(lambda: self._trigger_petpooja_checkout("card"))
        
        pay_row.addWidget(pay_cash_btn)
        pay_row.addWidget(pay_upi_btn)
        pay_row.addWidget(pay_card_btn)

        total_panel_layout.addWidget(self.total_label)
        total_panel_layout.addLayout(pay_row)
        
        # Hidden defaults for compatibility with checkout logic
        self.customer_name_input = QLineEdit()
        self.customer_phone_input = QLineEdit()
        self.payment_method_combo = QComboBox()
        self.payment_method_combo.addItem("Cash", "cash")
        self.payment_method_combo.addItem("UPI", "upi")
        self.payment_method_combo.addItem("Card", "card")

        cart_layout.addLayout(cart_header)
        cart_layout.addWidget(self.cart_table, 1)
        cart_layout.addWidget(self.cart_empty_label)
        cart_layout.addLayout(cart_actions_row)
        cart_layout.addWidget(total_panel, 0)

        splitter.addWidget(catalog_group)
        splitter.addWidget(cart_group)
        # Use relative sizes for better scaling
        splitter.setSizes([800, 400])
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)

        root_layout.addWidget(hero_frame, 0)
        root_layout.addWidget(splitter, 1)
        self.billing_root_layout = root_layout
        self.billing_splitter = splitter
        self._apply_billing_dashboard_style(tab)
        self._set_billing_compact_mode(self.width() < 1180)
        self._update_billing_dashboard_metrics(total_amount=0.0)
        return tab

    def _focus_billing_search(self) -> None:
        billing_index = self.tabs.indexOf(self.billing_tab)
        if billing_index >= 0:
            self.tabs.setCurrentIndex(billing_index)
        if hasattr(self, "search_input"):
            self.search_input.setFocus()
            self.search_input.selectAll()

    def _focus_inventory_name(self) -> None:
        if hasattr(self, "item_name_input"):
            self.item_name_input.setFocus()
            self.item_name_input.selectAll()

    def _focus_billing_qty(self) -> None:
        billing_index = self.tabs.indexOf(self.billing_tab)
        if billing_index >= 0:
            self.tabs.setCurrentIndex(billing_index)
        if hasattr(self, "qty_spin"):
            self.qty_spin.setFocus()
            self.qty_spin.selectAll()
        elif hasattr(self, "search_input"):
            self.search_input.setFocus()
            self.search_input.selectAll()

    def _try_checkout_from_enter(self) -> None:
        if self.tabs.currentWidget() is not self.billing_tab:
            return

        focused = self.focusWidget()
        if focused is self.search_input:
            return
        if hasattr(self, "qty_spin") and (
            focused is self.qty_spin or focused is self.qty_spin.lineEdit()
        ):
            return
        self.checkout()

    def _set_billing_compact_mode(self, enabled: bool) -> None:
        if not hasattr(self, "billing_root_layout"):
            return

        compact = bool(enabled)
        # Update vertical spacing
        self.billing_root_layout.setSpacing(4 if compact else 8)
        
        if hasattr(self, "cart_table"):
            self.cart_table.verticalHeader().setDefaultSectionSize(32 if compact else 40)

        if hasattr(self, "billing_splitter"):
            # Ratios 3:2 for catalog:cart
            total_w = self.billing_splitter.width()
            if total_w > 100:
                left = int(total_w * (0.65 if compact else 0.6))
                right = total_w - left
                self.billing_splitter.setSizes([left, right])

    def _make_billing_stat_card(self, heading: str) -> tuple[QFrame, QLabel]:
        return make_billing_stat_card(self, heading)

    def _style_billing_table(self, table: QTableWidget) -> None:
        style_billing_table(table)

    def _apply_billing_dashboard_style(self, tab: QWidget) -> None:
        apply_billing_dashboard_style(self, tab)

    def _apply_recipe_panel_style(self, tab: QWidget) -> None:
        T = self.THEME
        tab.setStyleSheet(f"""
            #RecipePanel {{
                background-color: {T['bg_deep']};
            }}
            #RecipePanel QGroupBox {{
                border: 1.5px solid {T['border_bold']};
                border-radius: 12px;
                background-color: {T['bg_surface']};
                margin-top: 15px;
                padding-top: 15px;
            }}
            #RecipeEmptyState {{
                padding: 24px;
                border: 2px dashed {T['border_bold']};
                border-radius: 12px;
                color: {T['text_medium']};
                background-color: transparent;
                font-weight: 700;
                font-size: 13px;
            }}
            #RecipeStatValue {{
                font-size: 24px;
                font-weight: 900;
                color: {T['accent_primary']};
            }}
            #RecipeStatTitle {{
                font-size: 11px;
                font-weight: 800;
                color: {T['text_medium']};
                text-transform: uppercase;
            }}
            #RecipeBuilderGroup, #RecipeLinesGroup, #RecipeAlertsGroup {{
                border: 1.5px solid {T['border_bold']};
                border-radius: 12px;
                background-color: {T['bg_surface']};
            }}
            #PrimaryRecipeButton {{
                background-color: {T['accent_primary']};
                color: white;
                font-weight: 900;
                font-size: 14px;
                border-radius: 10px;
                padding: 10px 18px;
                border: none;
            }}
            #PrimaryRecipeButton:hover {{
                background-color: #1d4ed8;
            }}
            #RecipeStepBadge {{
                background-color: {T['bg_surface']};
                border: 1.5px solid {T['accent_primary']};
                border-radius: 20px;
                color: {T['accent_primary']};
                font-weight: 800;
                font-size: 12px;
                padding: 4px 14px;
            }}
            #RecipeStepArrow {{
                color: {T['text_low']};
                font-size: 18px;
                font-weight: 700;
            }}
            #RecipeSummaryCard {{
                border: 1.5px solid {T['border_bold']};
                border-radius: 10px;
                background-color: {T['bg_surface']};
                padding: 8px 14px;
                font-weight: 800;
                font-size: 13px;
                color: {T['text_primary']};
            }}
            #RecipeSummaryCardAccent {{
                border: 1.5px solid {T['accent_primary']};
                border-radius: 10px;
                background-color: #eff6ff;
                padding: 8px 14px;
                font-weight: 800;
                font-size: 13px;
                color: {T['accent_primary']};
            }}
            #RecipeDangerBtn {{
                background-color: {T['bg_surface']};
                color: {T['danger']};
                border: 1.5px solid {T['danger']};
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 12px;
            }}
            #RecipeDangerBtn:hover {{
                background-color: #fef2f2;
            }}
            #RecipeRefreshBtn {{
                background-color: {T['bg_surface']};
                color: {T['text_medium']};
                border: 1.5px solid {T['border_bold']};
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 700;
            }}
            #RecipeRefreshBtn:hover {{
                background-color: {T['bg_deep']};
            }}
        """)

    def _apply_inventory_panel_style(self, tab: QWidget) -> None:
        apply_inventory_panel_style(self, tab)

    def _apply_purchases_panel_style(self, tab: QWidget) -> None:
        T = self.THEME
        tab.setStyleSheet(f"""
            #PurchasesPanel {{
                background-color: {T['bg_deep']};
            }}
            #PurchasesPanel QGroupBox {{
                border: 1.5px solid {T['border_bold']};
                border-radius: 12px;
                background-color: {T['bg_surface']};
                margin-top: 15px;
                padding-top: 15px;
            }}
            #PurchaseTotalPanel {{
                background-color: {T['bg_surface']};
                border: 2px solid {T['accent_primary']};
                border-radius: 12px;
                padding: 12px;
            }}
            #PurchaseTotalLabel {{
                font-size: 28px;
                font-weight: 900;
                color: {T['accent_primary']};
            }}
            QPushButton#PurchaseFilterPreset {{
                background-color: {T['bg_surface']};
                color: {T['text_medium']};
                border: 1.5px solid {T['border_bold']};
                border-radius: 15px;
                padding: 6px 15px;
                font-weight: 700;
            }}
            QPushButton#PurchaseFilterPreset:checked {{
                background-color: {T['text_primary']};
                color: white;
                border-color: {T['text_primary']};
            }}
            #PurchaseEmptyState {{
                padding: 24px;
                border: 2px dashed {T['border_bold']};
                border-radius: 12px;
                color: {T['text_medium']};
                background-color: transparent;
                font-weight: 700;
                font-size: 13px;
            }}
            #PurchaseInlineFeedback {{
                color: {T['text_medium']};
                font-size: 12px;
                font-weight: 600;
            }}
            #PurchaseStepBadge {{
                background-color: {T['bg_surface']};
                border: 1.5px solid {T['accent_primary']};
                border-radius: 20px;
                color: {T['accent_primary']};
                font-weight: 800;
                font-size: 12px;
                padding: 4px 14px;
            }}
            #PurchaseStepArrow {{
                color: {T['text_low']};
                font-size: 18px;
                font-weight: 700;
            }}
            #PurchaseSummaryCard {{
                border: 1.5px solid {T['border_bold']};
                border-radius: 10px;
                background-color: {T['bg_surface']};
                padding: 6px 12px;
                font-weight: 800;
                font-size: 12px;
                color: {T['text_primary']};
            }}
            #PurchaseDangerBtn {{
                background-color: {T['bg_surface']};
                color: {T['danger']};
                border: 1.5px solid {T['danger']};
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 12px;
            }}
            #PurchaseDangerBtn:hover {{
                background-color: #fef2f2;
            }}
            #PurchaseActionBtn {{
                background-color: {T['bg_surface']};
                color: {T['accent_primary']};
                border: 1.5px solid {T['accent_primary']};
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 12px;
            }}
            #PurchaseActionBtn:hover {{
                background-color: #eff6ff;
            }}
        """)

    def _show_selected_purchase_details(self, _item: QTableWidgetItem | None = None) -> None:
        selected = self.purchase_history_table.currentRow()
        if selected < 0:
            return

        supplier = self.purchase_history_table.item(selected, 1).text() if self.purchase_history_table.item(selected, 1) else "-"
        date_text = self.purchase_history_table.item(selected, 2).text() if self.purchase_history_table.item(selected, 2) else "-"
        lines = self.purchase_history_table.item(selected, 3).text() if self.purchase_history_table.item(selected, 3) else "0"
        total = self.purchase_history_table.item(selected, 4).text() if self.purchase_history_table.item(selected, 4) else "0.00"
        notes = self.purchase_history_table.item(selected, 5).text() if self.purchase_history_table.item(selected, 5) else ""

        QMessageBox.information(
            self,
            "Purchase Details",
            f"Supplier: {supplier}\nDate: {date_text}\nLines: {lines}\nTotal: INR {total}\nNotes: {notes or '-'}",
        )

    def _set_purchase_filter_button_state(self, preset: str) -> None:
        buttons = [
            getattr(self, "purchase_filter_today_btn", None),
            getattr(self, "purchase_filter_7d_btn", None),
            getattr(self, "purchase_filter_month_btn", None),
            getattr(self, "purchase_filter_custom_btn", None),
        ]
        for btn in buttons:
            if btn is not None:
                btn.setChecked(False)

        mapping = {
            "today": getattr(self, "purchase_filter_today_btn", None),
            "last7": getattr(self, "purchase_filter_7d_btn", None),
            "month": getattr(self, "purchase_filter_month_btn", None),
            "custom": getattr(self, "purchase_filter_custom_btn", None),
        }
        active_btn = mapping.get(preset)
        if active_btn is not None:
            active_btn.setChecked(True)

    def _set_purchase_filter_preset(self, preset: str) -> None:
        if preset in ("today", "last7", "month"):
            self._apply_quick_range(
                self.purchase_from_date,
                self.purchase_to_date,
                preset,
                self.refresh_purchases_tab,
            )
        else:
            self.refresh_purchases_tab()
        self._set_purchase_filter_button_state(preset)

    def duplicate_selected_purchase(self) -> None:
        selected = self.purchase_history_table.currentRow()
        if selected < 0:
            QMessageBox.information(self, "Duplicate Purchase", "Please select a purchase from history.")
            return

        id_cell = self.purchase_history_table.item(selected, 0)
        if id_cell is None:
            return

        purchase_id = int(id_cell.text())
        pin = self._require_admin_access("Duplicate Purchase")
        if pin is None:
            return

        try:
            purchase = self.bookkeeping_service.get_purchase_for_edit(purchase_id=purchase_id, admin_pin=pin)
        except ValueError as exc:
            QMessageBox.warning(self, "Duplicate Purchase", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Duplicate Purchase", str(exc))
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
        self._set_purchase_mode(False)
        if hasattr(self, "purchase_feedback_label"):
            self.purchase_feedback_label.setText(f"Purchase #{purchase_id} duplicated into builder.")
            self.purchase_feedback_label.setVisible(True)
            QTimer.singleShot(2200, lambda: self.purchase_feedback_label.setVisible(False))

    def _sync_inventory_add_button_state(self) -> None:
        if not hasattr(self, "inventory_add_btn"):
            return
        is_valid = (
            bool(self.item_name_input.text().strip())
            and float(self.sell_price_spin.value()) > 0
            and float(self.stock_spin.value()) >= 0
            and float(self.reorder_spin.value()) >= 0
        )
        self.inventory_add_btn.setEnabled(is_valid)

    def _on_inventory_edit_started(self, item: QTableWidgetItem) -> None:
        item.setBackground(QColor("#e2e8f0"))
        item.setForeground(QColor(self.THEME['text_primary']))
        if hasattr(self, "inventory_inline_status_label"):
            self.inventory_inline_status_label.setText("Editing inline... press Enter to save.")
            self.inventory_inline_status_label.setVisible(True)

    def _inventory_id_for_row(self, row: int) -> int | None:
        if row < 0:
            return None
        name_cell = self.inventory_items_table.item(row, 0)
        if name_cell is None:
            return None
        item_id = name_cell.data(Qt.UserRole)
        if item_id is None:
            return None
        return int(item_id)

    def _update_low_stock_panel(self, items: list[dict]) -> None:
        if not hasattr(self, "inventory_low_stock_banner"):
            return

        low_stock_items = [
            i for i in items if float(i.get("stock_quantity", 0)) <= float(i.get("reorder_level", 0))
        ]
        
        if not low_stock_items:
            self.inventory_low_stock_banner.setVisible(False)
            return

        out_of_stock = sum(1 for i in low_stock_items if float(i.get("stock_quantity", 0)) <= 0)
        low_stock = len(low_stock_items) - out_of_stock
        
        alerts = []
        if out_of_stock > 0:
            alerts.append(f"\U0001f534 {out_of_stock} items PREPARE TO 86 (Out of Stock!)")
        if low_stock > 0:
            alerts.append(f"\U0001f7e1 {low_stock} items LOW STOCK")
            
        alert_text = "   |   ".join(alerts)
        self.inventory_low_stock_banner.setText(f"\u26a0\ufe0f ACTION REQUIRED: {alert_text}")
        self.inventory_low_stock_banner.setVisible(True)

    def _on_low_stock_item_clicked(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.UserRole)
        if not name:
            return
        self.inventory_search_input.setText(str(name))
        self.inventory_low_stock_only_checkbox.setChecked(True)

    def _update_inventory_summary(self, items: list[dict]) -> None:
        if not hasattr(self, "inventory_summary_total"):
            return

        total_count = len(items)
        counts = self.inventory_controller.summary_counts(items)
        low_stock_count = counts["low"]
        out_of_stock_count = counts["out"]
        reorder_alerts_count = counts["reorder"]

        self.inventory_summary_total.setText(f"Total Items: {total_count}")
        self.inventory_summary_low.setText(f"Low Stock: {low_stock_count}")
        self.inventory_summary_oos.setText(f"Out of Stock: {out_of_stock_count}")
        if hasattr(self, "inventory_summary_reorder"):
            self.inventory_summary_reorder.setText(f"Reorder Alerts: {reorder_alerts_count}")

    def apply_inventory_filter(self) -> None:
        if not hasattr(self, "inventory_items_cache"):
            return

        query = self.inventory_search_input.text().strip().lower()
        category_id = self.inventory_filter_category_combo.currentData()
        low_stock_only = self.inventory_low_stock_only_checkbox.isChecked()

        filtered: list[dict] = []
        for item in self.inventory_items_cache:
            name = item.get("name", "")
            item_category_id = item.get("category_id")
            stock = self._f(item.get("stock_quantity"))
            reorder = self._f(item.get("reorder_level"))

            if query and query not in name.lower():
                continue
            if category_id is not None and int(item_category_id or -1) != int(category_id):
                continue
            if low_stock_only and stock > reorder:
                continue
            filtered.append(item)

        table = self.inventory_items_table
        self._updating_inventory_table = True
        table.setSortingEnabled(False)
        table.setRowCount(len(filtered))

        for row_index, item in enumerate(filtered):
            name_item = QTableWidgetItem(item["name"])
            name_item.setData(Qt.UserRole, int(item["id"]))
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row_index, 0, name_item)

            category_item = QTableWidgetItem(item.get("category_name") or "-")
            category_item.setFlags(category_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row_index, 1, category_item)

            kind_text = "Ingredient" if (item.get("item_kind") or "sellable") == "ingredient" else "Sellable"
            kind_item = QTableWidgetItem(kind_text)
            kind_item.setFlags(kind_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row_index, 2, kind_item)

            costing_raw = item.get("costing_mode") or "manual"
            costing_text = "Recipe" if costing_raw == "recipe" else "Manual"
            costing_item = QTableWidgetItem(costing_text)
            costing_item.setFlags(costing_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row_index, 3, costing_item)

            sell_item = QTableWidgetItem(f"{self._f(item.get('selling_price')):.2f}")
            sell_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(row_index, 4, sell_item)

            stock_value = self._f(item.get("stock_quantity"))
            reorder_value = self._f(item.get("reorder_level"))
            
            stock_text, _, _ = self.inventory_controller.stock_status(stock_value, reorder_value)
                
            stock_item = QTableWidgetItem(stock_text)
            stock_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            stock_item.setFlags(stock_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row_index, 5, stock_item)

            reorder_item = QTableWidgetItem(f"{reorder_value:.2f}")
            reorder_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(row_index, 6, reorder_item)

            actions_cell = QWidget()
            actions_layout = QHBoxLayout(actions_cell)
            actions_layout.setContentsMargins(2, 1, 2, 1)
            actions_layout.setSpacing(4)

            restock_btn = QToolButton()
            restock_btn.setObjectName("StandardAction")
            restock_btn.setText("Stock +")
            restock_btn.setMinimumWidth(84)
            restock_btn.setToolTip("Quick stock adjust")
            restock_btn.clicked.connect(lambda _, item_id=int(item["id"]): self._quick_restock_inventory_item(item_id))

            edit_btn = QToolButton()
            edit_btn.setObjectName("StandardAction")
            edit_btn.setText("Edit")
            edit_btn.setMinimumWidth(64)
            edit_btn.clicked.connect(lambda _, item_id=int(item["id"]): self._edit_inventory_item_by_id(item_id))

            delete_btn = QToolButton()
            delete_btn.setObjectName("DangerAction")
            delete_btn.setText("Delete")
            delete_btn.setMinimumWidth(72)
            delete_btn.clicked.connect(lambda _, item_id=int(item["id"]): self._delete_inventory_item_by_id(item_id))

            actions_layout.addWidget(restock_btn)
            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(delete_btn)
            actions_layout.addStretch()
            table.setCellWidget(row_index, 7, actions_cell)

            self.inventory_controller.apply_stock_status(stock_item, stock_value, reorder_value)

        table.setSortingEnabled(True)

        self._updating_inventory_table = False
        if hasattr(self, "inventory_empty_state_label"):
            self.inventory_empty_state_label.setVisible(len(filtered) == 0)
        self._update_inventory_summary(self.inventory_items_cache)
        self._update_low_stock_panel(self.inventory_items_cache)

    def _select_inventory_row_by_item_id(self, item_id: int) -> bool:
        for row in range(self.inventory_items_table.rowCount()):
            row_item_id = self._inventory_id_for_row(row)
            if row_item_id == int(item_id):
                self.inventory_items_table.selectRow(row)
                self.inventory_items_table.scrollToItem(self.inventory_items_table.item(row, 0))
                return True
        return False

    def _edit_inventory_item_by_id(self, item_id: int) -> None:
        if self._select_inventory_row_by_item_id(item_id):
            self.update_selected_item_price()

    def _delete_inventory_item_by_id(self, item_id: int) -> None:
        if self._select_inventory_row_by_item_id(item_id):
            self.delete_selected_item()

    def _quick_restock_inventory_item(self, item_id: int) -> None:
        if not self._select_inventory_row_by_item_id(item_id):
            return

        item = self._selected_inventory_item()
        if item is None:
            return

        pin = self._require_admin_access("Quick Restock")
        if pin is None:
            return

        add_qty, ok_qty = QInputDialog.getDouble(
            self,
            "Quick Restock",
            f"Add stock quantity for {item['name']}:",
            value=1.0,
            minValue=0.01,
            decimals=2,
        )
        if not ok_qty:
            return

        try:
            self.inventory_service.manual_stock_adjustment(
                item_id=item["item_id"],
                quantity_delta=float(add_qty),
                admin_pin=pin,
                notes="Quick restock from inventory table",
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Quick Restock", str(exc))
            return

        self.inventory_inline_status_label.setText(f"Restocked {item['name']} +{add_qty:.2f}")
        self.inventory_inline_status_label.setVisible(True)
        QTimer.singleShot(2200, lambda: self.inventory_inline_status_label.setVisible(False))
        self.refresh_inventory()
        self.refresh_billing_items()

    def _build_recipe_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("RecipeTabRoot")
        root_layout = QVBoxLayout(tab)
        root_layout.setContentsMargins(0, 0, 0, 0)

        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setFrameShape(QFrame.NoFrame)
        
        main_content = QWidget()
        main_content.setObjectName("RecipePanel")
        content_layout = QVBoxLayout(main_content)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(15)

        # --- Step Badges ---
        steps_row = QHBoxLayout()
        steps_row.setSpacing(6)
        for idx, (label, icon) in enumerate([
            ("1  Select Product", "📦"),
            ("2  Add Ingredients", "🧪"),
            ("3  Save Recipe", "💾"),
        ]):
            badge = QLabel(f"{icon}  {label}")
            badge.setObjectName("RecipeStepBadge")
            badge.setAlignment(Qt.AlignCenter)
            badge.setMinimumHeight(32)
            steps_row.addWidget(badge)
            if idx < 2:
                arrow = QLabel("→")
                arrow.setObjectName("RecipeStepArrow")
                arrow.setAlignment(Qt.AlignCenter)
                steps_row.addWidget(arrow)
        steps_row.addStretch()

        # --- Top Section: Recipe Builder ---
        builder_box = QGroupBox("Recipe Builder")
        builder_box.setObjectName("RecipeBuilderGroup")
        builder_layout = QGridLayout(builder_box)
        builder_layout.setHorizontalSpacing(10)
        builder_layout.setVerticalSpacing(8)

        self.recipe_product_combo = QComboBox()
        self.recipe_product_combo.currentIndexChanged.connect(self.load_selected_recipe_in_tab)
        self.recipe_product_combo.setMinimumHeight(34)
        
        self.recipe_yield_spin = QDoubleSpinBox()
        self.recipe_yield_spin.setDecimals(3)
        self.recipe_yield_spin.setMinimum(0.001)
        self.recipe_yield_spin.setMaximum(100000)
        self.recipe_yield_spin.setValue(1.0)
        self.recipe_yield_spin.setMaximumWidth(130)
        self.recipe_yield_spin.setMinimumHeight(34)

        recipe_refresh_btn = QPushButton("↻ Refresh")
        recipe_refresh_btn.setObjectName("RecipeRefreshBtn")
        recipe_refresh_btn.setMinimumHeight(34)
        recipe_refresh_btn.clicked.connect(self.refresh_recipe_tab)

        self.recipe_builder_ingredient_combo = QComboBox()
        self.recipe_builder_ingredient_combo.setMinimumHeight(34)
        self.recipe_builder_qty_spin = QDoubleSpinBox()
        self.recipe_builder_qty_spin.setDecimals(4)
        self.recipe_builder_qty_spin.setMinimum(0.0001)
        self.recipe_builder_qty_spin.setMaximum(100000)
        self.recipe_builder_qty_spin.setValue(1.0)
        self.recipe_builder_qty_spin.setMaximumWidth(130)
        self.recipe_builder_qty_spin.setMinimumHeight(34)
        
        self.recipe_builder_waste_spin = QDoubleSpinBox()
        self.recipe_builder_waste_spin.setDecimals(2)
        self.recipe_builder_waste_spin.setMinimum(0)
        self.recipe_builder_waste_spin.setMaximum(100)
        self.recipe_builder_waste_spin.setValue(0.0)
        self.recipe_builder_waste_spin.setMaximumWidth(130)
        self.recipe_builder_waste_spin.setMinimumHeight(34)

        add_line_btn = QPushButton("+ Add Ingredient to Recipe")
        add_line_btn.setObjectName("PrimaryRecipeButton")
        add_line_btn.setMinimumHeight(42)
        add_line_btn.setMinimumWidth(260)
        add_line_btn.clicked.connect(lambda: self._add_recipe_line_row())

        builder_layout.addWidget(QLabel("<b>Sellable Product</b>"), 0, 0)
        builder_layout.addWidget(self.recipe_product_combo, 0, 1, 1, 3)
        builder_layout.addWidget(QLabel("<b>Yield Qty</b>"), 0, 4)
        builder_layout.addWidget(self.recipe_yield_spin, 0, 5)
        builder_layout.addWidget(recipe_refresh_btn, 0, 6)
        
        builder_layout.addWidget(QLabel("<b>Ingredient</b>"), 1, 0)
        builder_layout.addWidget(self.recipe_builder_ingredient_combo, 1, 1, 1, 3)
        builder_layout.addWidget(QLabel("<b>Qty Used</b>"), 1, 4)
        builder_layout.addWidget(self.recipe_builder_qty_spin, 1, 5)
        builder_layout.addWidget(QLabel("<b>Waste %</b>"), 1, 6)
        builder_layout.addWidget(self.recipe_builder_waste_spin, 1, 7)

        add_line_row = QHBoxLayout()
        add_line_row.addStretch()
        add_line_row.addWidget(add_line_btn)
        builder_layout.addLayout(add_line_row, 2, 0, 1, 8)
        builder_box.setMaximumHeight(220)

        # --- Table Section ---
        recipe_lines_box = QGroupBox("Recipe Ingredients")
        recipe_lines_box.setObjectName("RecipeLinesGroup")
        recipe_lines_layout = QVBoxLayout(recipe_lines_box)
        recipe_lines_layout.setContentsMargins(10, 10, 10, 10)
        recipe_lines_layout.setSpacing(8)

        self.recipe_lines_table = QTableWidget(0, 5)
        self.recipe_lines_table.setHorizontalHeaderLabels(["Ingredient", "Qty Used", "Waste %", "Unit Cost", "Line Cost"])
        self.recipe_lines_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.recipe_lines_table.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.SelectedClicked | QTableWidget.EditKeyPressed
        )
        self.recipe_lines_table.setAlternatingRowColors(True)
        self.recipe_lines_table.itemChanged.connect(self._on_recipe_line_item_changed)
        self.recipe_lines_table.horizontalHeader().setStretchLastSection(True)
        self.recipe_lines_table.setMinimumHeight(245)
        self.recipe_lines_table.verticalHeader().setDefaultSectionSize(40)
        self.recipe_lines_table.verticalHeader().setVisible(False)
        for col in (1, 2, 3, 4):
            hdr = self.recipe_lines_table.horizontalHeaderItem(col)
            if hdr:
                hdr.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        # --- Actions and State ---
        self.recipe_empty_state_label = QLabel(
            "🧪  No ingredients added yet.\nSelect an ingredient above and click '+ Add Ingredient to Recipe'."
        )
        self.recipe_empty_state_label.setObjectName("RecipeEmptyState")
        self.recipe_empty_state_label.setAlignment(Qt.AlignCenter)
        
        self.remove_recipe_line_btn = QPushButton("✕ Remove Selected")
        self.remove_recipe_line_btn.setObjectName("RecipeDangerBtn")
        self.remove_recipe_line_btn.setMinimumHeight(32)
        self.remove_recipe_line_btn.clicked.connect(self.remove_selected_recipe_line)
        
        self.clear_recipe_lines_btn = QPushButton("🗑 Clear All")
        self.clear_recipe_lines_btn.setObjectName("RecipeDangerBtn")
        self.clear_recipe_lines_btn.setMinimumHeight(32)
        self.clear_recipe_lines_btn.clicked.connect(self.clear_recipe_lines)
        
        table_actions_row = QHBoxLayout()
        table_actions_row.setContentsMargins(0, 0, 0, 0)
        table_actions_row.setSpacing(8)
        table_actions_row.addWidget(self.remove_recipe_line_btn)
        table_actions_row.addWidget(self.clear_recipe_lines_btn)
        table_actions_row.addStretch()

        save_recipe_btn = QPushButton("💾  Save Recipe (Admin PIN)")
        save_recipe_btn.setObjectName("PrimaryRecipeButton")
        save_recipe_btn.setMinimumHeight(44)
        save_recipe_btn.clicked.connect(self.save_recipe_from_tab)

        # --- Recipe Cost Summary Cards ---
        summary_row = QHBoxLayout()
        summary_row.setSpacing(10)
        self.recipe_line_count_card = QLabel("Lines: 0")
        self.recipe_line_count_card.setObjectName("RecipeSummaryCard")
        self.recipe_line_count_card.setAlignment(Qt.AlignCenter)
        self.recipe_est_cost_card = QLabel("Est. Unit Cost: INR 0.00")
        self.recipe_est_cost_card.setObjectName("RecipeSummaryCard")
        self.recipe_est_cost_card.setAlignment(Qt.AlignCenter)
        self.recipe_est_margin_card = QLabel("Est. Margin/Unit: INR 0.00")
        self.recipe_est_margin_card.setObjectName("RecipeSummaryCardAccent")
        self.recipe_est_margin_card.setAlignment(Qt.AlignCenter)
        summary_row.addWidget(self.recipe_line_count_card)
        summary_row.addWidget(self.recipe_est_cost_card)
        summary_row.addWidget(self.recipe_est_margin_card)
        summary_row.addStretch()

        total_panel = QFrame()
        total_panel.setObjectName("PurchaseTotalPanel")
        total_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        total_panel.setMinimumHeight(58)
        total_layout = QHBoxLayout(total_panel)
        total_layout.setContentsMargins(10, 6, 10, 6)
        total_layout.addWidget(save_recipe_btn)
        total_layout.addStretch()

        self.recipe_status_label = QLabel("")
        self.recipe_status_label.setObjectName("OpsHintLabel")
        self.recipe_status_label.setVisible(False)
        
        recipe_hint = QLabel("Tip: Double-click Qty/Waste cells to edit inline before saving.")
        recipe_hint.setObjectName("OpsHintLabel")
        recipe_hint.setMaximumHeight(20)

        # --- Right Panel (Alerts) ---
        alerts_box = QGroupBox("Low Ingredient Alerts")
        alerts_box.setObjectName("RecipeAlertsGroup")
        alerts_layout = QVBoxLayout(alerts_box)
        self.recipe_low_ingredients_list = QListWidget()
        alerts_layout.addWidget(self.recipe_low_ingredients_list)

        right_footer = QHBoxLayout()
        right_footer.addWidget(recipe_refresh_btn)
        right_footer.addStretch()

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        recipe_lines_layout.addWidget(self.recipe_lines_table)
        recipe_lines_layout.addLayout(table_actions_row)
        recipe_lines_layout.addWidget(self.recipe_empty_state_label)
        left_layout.addWidget(recipe_lines_box)
        left_layout.addWidget(total_panel)
        left_layout.addWidget(self.recipe_status_label)
        left_layout.addWidget(recipe_hint)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        right_layout.addWidget(alerts_box)
        right_layout.addLayout(right_footer)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.addWidget(left_panel)
        split.addWidget(right_panel)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setHandleWidth(6)
        
        content_layout.addLayout(steps_row)
        content_layout.addWidget(builder_box)
        content_layout.addLayout(summary_row)
        content_layout.addWidget(split)

        main_scroll.setWidget(main_content)
        root_layout.addWidget(main_scroll)

        self._apply_recipe_panel_style(tab)
        return tab

    def _add_recipe_line_row(
        self,
        ingredient_item_id: int | None = None,
        quantity_used: float | None = None,
        waste_percent: float | None = None,
        ingredient_display_name: str | None = None,
    ) -> None:
        if not hasattr(self, "recipe_lines_table"):
            return

        # If it's a manual add from the builder UI
        if ingredient_item_id is None:
            ingredient_item_id = self.recipe_builder_ingredient_combo.currentData()
            if ingredient_item_id is None:
                QMessageBox.warning(self, "Recipe", "Select an ingredient from the dropdown.")
                return
            quantity_used = self.recipe_builder_qty_spin.value()
            waste_percent = self.recipe_builder_waste_spin.value()
            ingredient_display_name = self.recipe_builder_ingredient_combo.currentText()
            
            # Check if already added
            for i in range(self.recipe_lines_table.rowCount()):
                if self.recipe_lines_table.item(i, 0).data(Qt.UserRole) == ingredient_item_id:
                    self.recipe_status_label.setText("Ingredient already exists in recipe.")
                    self.recipe_status_label.setVisible(True)
                    QTimer.singleShot(2000, lambda: self.recipe_status_label.setVisible(False))
                    return

        if ingredient_item_id is None or quantity_used is None or waste_percent is None or ingredient_display_name is None:
            return  # Safety

        row = self.recipe_lines_table.rowCount()
        self.recipe_lines_table.insertRow(row)

        name_item = QTableWidgetItem(ingredient_display_name)
        name_item.setData(Qt.UserRole, int(ingredient_item_id))
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)

        qty_item = QTableWidgetItem(f"{float(quantity_used):.4f}")
        qty_item.setData(Qt.UserRole, float(quantity_used))

        waste_item = QTableWidgetItem(f"{float(waste_percent):.2f}")
        waste_item.setData(Qt.UserRole, float(waste_percent))

        # Look up ingredient cost from cache for Unit Cost and Line Cost columns
        ing_cost = 0.0
        if hasattr(self, "recipe_ingredients_cache"):
            cached_ing = next(
                (i for i in self.recipe_ingredients_cache if int(i["id"]) == int(ingredient_item_id)),
                None,
            )
            if cached_ing:
                ing_cost = float(cached_ing.get("cost_price") or 0)

        waste_multiplier = 1.0 + (float(waste_percent) / 100.0)
        effective_unit_cost = ing_cost * waste_multiplier
        line_cost = effective_unit_cost * float(quantity_used)

        unit_cost_item = QTableWidgetItem(f"{effective_unit_cost:.2f}")
        unit_cost_item.setData(Qt.UserRole, effective_unit_cost)
        unit_cost_item.setFlags(unit_cost_item.flags() & ~Qt.ItemIsEditable)
        unit_cost_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

        line_cost_item = QTableWidgetItem(f"{line_cost:.2f}")
        line_cost_item.setData(Qt.UserRole, line_cost)
        line_cost_item.setFlags(line_cost_item.flags() & ~Qt.ItemIsEditable)
        line_cost_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.recipe_lines_table.blockSignals(True)
        self.recipe_lines_table.setItem(row, 0, name_item)
        self.recipe_lines_table.setItem(row, 1, qty_item)
        self.recipe_lines_table.setItem(row, 2, waste_item)
        self.recipe_lines_table.setItem(row, 3, unit_cost_item)
        self.recipe_lines_table.setItem(row, 4, line_cost_item)
        self.recipe_lines_table.blockSignals(False)
        
        self.recipe_empty_state_label.setVisible(False)
        self.recipe_builder_qty_spin.setValue(1.0)
        self.recipe_builder_waste_spin.setValue(0.0)
        self._update_recipe_cost_summary()

    def _on_recipe_line_item_changed(self, item: QTableWidgetItem) -> None:
        col = item.column()
        if col not in (1, 2):
            return

        text = item.text().strip()
        try:
            val = float(text)
            if val < 0:
                raise ValueError("Cannot be negative")
            item.setData(Qt.UserRole, val)
        except ValueError:
            # Revert
            old_val = item.data(Qt.UserRole)
            self.recipe_lines_table.blockSignals(True)
            if old_val is not None:
                item.setText(f"{old_val:.4f}" if col == 1 else f"{old_val:.2f}")
            self.recipe_lines_table.blockSignals(False)
            return

        self.recipe_lines_table.blockSignals(True)
        item.setText(f"{val:.4f}" if col == 1 else f"{val:.2f}")

        # Recalculate cost columns for this row
        row = item.row()
        qty_item = self.recipe_lines_table.item(row, 1)
        waste_item = self.recipe_lines_table.item(row, 2)
        unit_cost_item = self.recipe_lines_table.item(row, 3)
        line_cost_item = self.recipe_lines_table.item(row, 4)
        if qty_item and waste_item and unit_cost_item and line_cost_item:
            base_unit_cost = float(unit_cost_item.data(Qt.UserRole) or 0)
            # If waste changed, recompute effective unit cost from base
            if col == 2:
                # Need to derive base cost (without waste) from current effective cost
                old_waste = float(waste_item.data(Qt.UserRole) or 0)
                # We stored effective cost in UserRole; recompute from base
                # base = effective / (1 + old_waste/100) — but old_waste already updated
                # Simpler: use the stored base cost from the ingredient cache
                ing_id = self.recipe_lines_table.item(row, 0)
                if ing_id:
                    ing_cost = 0.0
                    if hasattr(self, "recipe_ingredients_cache"):
                        cached_ing = next(
                            (i for i in self.recipe_ingredients_cache if int(i["id"]) == int(ing_id.data(Qt.UserRole))),
                            None,
                        )
                        if cached_ing:
                            ing_cost = float(cached_ing.get("cost_price") or 0)
                    waste_multiplier = 1.0 + (val / 100.0)
                    effective_unit_cost = ing_cost * waste_multiplier
                else:
                    effective_unit_cost = base_unit_cost
            else:
                effective_unit_cost = base_unit_cost

            qty = float(qty_item.data(Qt.UserRole) or 0)
            line_cost = effective_unit_cost * qty

            unit_cost_item.setText(f"{effective_unit_cost:.2f}")
            unit_cost_item.setData(Qt.UserRole, effective_unit_cost)
            line_cost_item.setText(f"{line_cost:.2f}")
            line_cost_item.setData(Qt.UserRole, line_cost)

        self.recipe_lines_table.blockSignals(False)
        self._update_recipe_cost_summary()

    def remove_selected_recipe_line(self) -> None:
        if not hasattr(self, "recipe_lines_table"):
            return
        row = self.recipe_lines_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Recipe", "Select a line to remove.")
            return
        self.recipe_lines_table.removeRow(row)
        if self.recipe_lines_table.rowCount() == 0:
            self.recipe_empty_state_label.setVisible(True)
        self._update_recipe_cost_summary()

    def clear_recipe_lines(self) -> None:
        if not hasattr(self, "recipe_lines_table"):
            return
        self.recipe_lines_table.setRowCount(0)
        self.recipe_empty_state_label.setVisible(True)
        self._update_recipe_cost_summary()

    def _update_recipe_cost_summary(self) -> None:
        if not hasattr(self, "recipe_line_count_card"):
            return

        line_count = self.recipe_lines_table.rowCount()
        total_line_cost = 0.0
        for row in range(line_count):
            lc_item = self.recipe_lines_table.item(row, 4)
            if lc_item:
                total_line_cost += float(lc_item.data(Qt.UserRole) or 0)

        yield_qty = float(self.recipe_yield_spin.value()) if hasattr(self, "recipe_yield_spin") else 1.0
        if yield_qty <= 0:
            yield_qty = 1.0
        unit_cost = total_line_cost / yield_qty

        # Look up selling price of selected product for margin calculation
        sell_price = 0.0
        product_id = self.recipe_product_combo.currentData() if hasattr(self, "recipe_product_combo") else None
        if product_id is not None and hasattr(self, "inventory_items_cache"):
            prod = next((i for i in self.inventory_items_cache if int(i["id"]) == int(product_id)), None)
            if prod:
                sell_price = float(prod.get("selling_price") or 0)

        margin_per_unit = sell_price - unit_cost

        self.recipe_line_count_card.setText(f"🧾 Lines: {line_count}")
        self.recipe_est_cost_card.setText(f"💰 Est. Unit Cost: INR {unit_cost:.2f}")
        margin_color = self.THEME["success"] if margin_per_unit >= 0 else self.THEME["danger"]
        self.recipe_est_margin_card.setText(f"📈 Margin/Unit: INR {margin_per_unit:.2f}")
        self.recipe_est_margin_card.setStyleSheet(
            f"color: {margin_color}; font-weight: 800; border: 1.5px solid {margin_color}; "
            f"border-radius: 10px; background-color: {'#f0fdf4' if margin_per_unit >= 0 else '#fef2f2'}; "
            f"padding: 8px 14px;"
        )

    def load_selected_recipe_in_tab(self) -> None:
        if not hasattr(self, "recipe_product_combo") or not hasattr(self, "recipe_lines_table"):
            return

        product_id = self.recipe_product_combo.currentData()
        if product_id is None:
            self.recipe_lines_table.setRowCount(0)
            self.recipe_empty_state_label.setVisible(True)
            return

        existing = self.inventory_service.get_recipe(int(product_id))
        self.recipe_lines_table.setRowCount(0)
        
        if existing is None:
            self.recipe_yield_spin.setValue(1.0)
            self.recipe_empty_state_label.setVisible(True)
            return

        self.recipe_yield_spin.setValue(float(existing.get("yield_qty", 1.0) or 1.0))
        lines = existing.get("lines", [])
        if not lines:
            self.recipe_empty_state_label.setVisible(True)
        else:
            self.recipe_empty_state_label.setVisible(False)
            for line in lines:
                name_str = f"{line.get('ingredient_name', 'Unknown')} ({line.get('unit_name', 'unit')}) | Stock {float(line.get('stock_quantity') or 0):.2f}"
                self._add_recipe_line_row(
                    ingredient_item_id=int(line["ingredient_item_id"]),
                    quantity_used=float(line["quantity_used"]),
                    waste_percent=float(line.get("waste_percent", 0.0)),
                    ingredient_display_name=name_str
                )

    def save_recipe_from_tab(self) -> None:
        if not hasattr(self, "recipe_product_combo") or not hasattr(self, "recipe_lines_table"):
            return

        product_id = self.recipe_product_combo.currentData()
        if product_id is None:
            QMessageBox.warning(self, "Recipe", "Select a sellable product first.")
            return
            
        pin = self._require_admin_access("Save Recipe")
        if pin is None:
            return

        lines: list[dict] = []
        for row in range(self.recipe_lines_table.rowCount()):
            ing_item = self.recipe_lines_table.item(row, 0)
            qty_item = self.recipe_lines_table.item(row, 1)
            waste_item = self.recipe_lines_table.item(row, 2)
            if not ing_item or not qty_item or not waste_item:
                continue

            lines.append(
                {
                    "ingredient_item_id": int(ing_item.data(Qt.UserRole)),
                    "quantity_used": float(qty_item.data(Qt.UserRole)),
                    "waste_percent": float(waste_item.data(Qt.UserRole)),
                }
            )

        if not lines:
            QMessageBox.warning(self, "Recipe", "Recipe must include at least one ingredient line.")
            return

        try:
            self.inventory_service.save_recipe(
                sellable_item_id=int(product_id),
                lines=lines,
                yield_qty=float(self.recipe_yield_spin.value()),
                admin_pin=pin,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Recipe", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Recipe Error", str(exc))
            return

        self.recipe_status_label.setText("Recipe saved successfully.")
        self.recipe_status_label.setVisible(True)
        QTimer.singleShot(2200, lambda: self.recipe_status_label.setVisible(False))
        self.refresh_recipe_tab()
        self.refresh_billing_items()
        self.refresh_reports()
        self._log_audit("recipe_save_tab", "item", str(product_id), f"lines={len(lines)}")

    def refresh_recipe_tab(self) -> None:
        if not hasattr(self, "recipe_product_combo"):
            return

        all_items = self.inventory_service.list_items()
        self.recipe_ingredients_cache = self.inventory_service.list_ingredients()
        sellables = [i for i in all_items if (i.get("item_kind") or "sellable") == "sellable"]

        selected_product = self.recipe_product_combo.currentData()
        self.recipe_product_combo.blockSignals(True)
        self.recipe_product_combo.clear()
        for item in sellables:
            self.recipe_product_combo.addItem(item["name"], int(item["id"]))
        if sellables:
            index = self.recipe_product_combo.findData(selected_product)
            self.recipe_product_combo.setCurrentIndex(index if index >= 0 else 0)
        self.recipe_product_combo.blockSignals(False)
        
        if hasattr(self, "recipe_builder_ingredient_combo"):
            selected_ing = self.recipe_builder_ingredient_combo.currentData()
            self.recipe_builder_ingredient_combo.blockSignals(True)
            self.recipe_builder_ingredient_combo.clear()
            for ing in self.recipe_ingredients_cache:
                self.recipe_builder_ingredient_combo.addItem(
                    f"{ing['name']} ({ing.get('unit_name') or 'unit'}) | Stock {float(ing.get('stock_quantity') or 0):.2f}",
                    int(ing["id"]),
                )
            if self.recipe_ingredients_cache:
                index = self.recipe_builder_ingredient_combo.findData(selected_ing)
                self.recipe_builder_ingredient_combo.setCurrentIndex(index if index >= 0 else 0)
            self.recipe_builder_ingredient_combo.blockSignals(False)

        if sellables:
            self.load_selected_recipe_in_tab()
        else:
            self.recipe_lines_table.setRowCount(0)
            self.recipe_empty_state_label.setVisible(True)

        low_ingredients = self.inventory_service.low_ingredient_items()
        self.recipe_low_ingredients_list.clear()
        if not low_ingredients:
            self.recipe_low_ingredients_list.addItem("All ingredient stock is healthy.")
        else:
            for row in low_ingredients:
                self.recipe_low_ingredients_list.addItem(
                    f"{row['name']} | Stock {float(row['stock_quantity']):.2f} / Reorder {float(row['reorder_level']):.2f} {row.get('unit_name') or ''}"
                )

    def _build_inventory_tab(self) -> QWidget:
        return build_inventory_tab(self)

    def _build_purchases_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("PurchasesTabRoot")
        root_layout = QVBoxLayout(tab)
        root_layout.setContentsMargins(0, 0, 0, 0)

        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setFrameShape(QFrame.NoFrame)
        
        main_content = QWidget()
        main_content.setObjectName("PurchasesPanel")
        content_layout = QVBoxLayout(main_content)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(15)

        # --- Step Badges ---
        p_steps_row = QHBoxLayout()
        p_steps_row.setSpacing(6)
        for idx, (label, icon) in enumerate([
            ("1  Add Items", "📦"),
            ("2  Build List", "📋"),
            ("3  Save Purchase", "💾"),
        ]):
            badge = QLabel(f"{icon}  {label}")
            badge.setObjectName("PurchaseStepBadge")
            badge.setAlignment(Qt.AlignCenter)
            badge.setMinimumHeight(32)
            p_steps_row.addWidget(badge)
            if idx < 2:
                arrow = QLabel("→")
                arrow.setObjectName("PurchaseStepArrow")
                arrow.setAlignment(Qt.AlignCenter)
                p_steps_row.addWidget(arrow)
        p_steps_row.addStretch()

        entry_box = QGroupBox("Purchase Builder")
        entry_layout = QGridLayout(entry_box)
        entry_layout.setHorizontalSpacing(10)
        entry_layout.setVerticalSpacing(8)

        self.purchase_supplier_input = QLineEdit()
        self.purchase_supplier_input.setPlaceholderText("Supplier name")
        self.purchase_supplier_input.setMinimumHeight(34)
        self.purchase_notes_input = QLineEdit()
        self.purchase_notes_input.setPlaceholderText("Optional notes")
        self.purchase_notes_input.setMinimumHeight(34)
        self.purchase_item_combo = QComboBox()
        self.purchase_item_combo.currentIndexChanged.connect(self._on_purchase_item_changed)
        self.purchase_item_combo.setMinimumHeight(34)
        self.purchase_qty_spin = QDoubleSpinBox()
        self.purchase_qty_spin.setDecimals(2)
        self.purchase_qty_spin.setMinimum(0.01)
        self.purchase_qty_spin.setMaximum(100000)
        self.purchase_qty_spin.setValue(1)
        self.purchase_qty_spin.valueChanged.connect(self._update_purchase_stock_preview)
        self.purchase_qty_spin.setMinimumHeight(34)

        self.purchase_cost_spin = QDoubleSpinBox()
        self.purchase_cost_spin.setDecimals(2)
        self.purchase_cost_spin.setMinimum(0)
        self.purchase_cost_spin.setMaximum(100000)
        self.purchase_cost_spin.setPrefix("INR ")
        self.purchase_cost_spin.setMinimumHeight(34)
        self.purchase_item_combo.setMaximumWidth(460)
        self.purchase_qty_spin.setMaximumWidth(130)
        self.purchase_cost_spin.setMaximumWidth(180)

        self.add_line_btn = QPushButton("+ Add Item to Purchase")
        self.add_line_btn.setObjectName("PrimaryPurchaseButton")
        self.add_line_btn.setMinimumHeight(42)
        self.add_line_btn.setMinimumWidth(260)
        self.add_line_btn.clicked.connect(self.add_purchase_line)

        save_purchase_btn = QPushButton("💾  Save Purchase")
        save_purchase_btn.setObjectName("PrimaryPurchaseButton")
        save_purchase_btn.setMinimumHeight(38)
        self.save_purchase_btn = save_purchase_btn
        save_purchase_btn.clicked.connect(self.save_purchase)

        cancel_edit_btn = QPushButton("✕ Cancel Edit")
        cancel_edit_btn.setObjectName("PurchaseDangerBtn")
        self.cancel_purchase_edit_btn = cancel_edit_btn
        self.cancel_purchase_edit_btn.setVisible(False)
        self.cancel_purchase_edit_btn.setEnabled(False)
        cancel_edit_btn.clicked.connect(self.cancel_purchase_edit)

        self.clear_purchase_lines_btn = QPushButton("🗑 Clear All")
        self.clear_purchase_lines_btn.setObjectName("PurchaseDangerBtn")
        self.clear_purchase_lines_btn.setMinimumHeight(32)
        self.clear_purchase_lines_btn.clicked.connect(self.clear_purchase_lines)

        self.remove_purchase_line_btn = QPushButton("✕ Remove Selected")
        self.remove_purchase_line_btn.setObjectName("PurchaseDangerBtn")
        self.remove_purchase_line_btn.setMinimumHeight(32)
        self.remove_purchase_line_btn.clicked.connect(self.remove_selected_purchase_line)

        modify_saved_btn = QPushButton("✎ Modify (Admin PIN)")
        modify_saved_btn.setObjectName("PurchaseActionBtn")
        modify_saved_btn.setMinimumHeight(32)
        modify_saved_btn.clicked.connect(self.load_selected_purchase_for_edit)

        duplicate_saved_btn = QPushButton("⧉ Duplicate")
        duplicate_saved_btn.setObjectName("PurchaseActionBtn")
        duplicate_saved_btn.setMinimumHeight(32)
        duplicate_saved_btn.clicked.connect(self.duplicate_selected_purchase)

        entry_layout.addWidget(QLabel("<b>Supplier</b>"), 0, 0)
        entry_layout.addWidget(self.purchase_supplier_input, 0, 1, 1, 2)
        entry_layout.addWidget(QLabel("<b>Notes</b>"), 0, 3)
        entry_layout.addWidget(self.purchase_notes_input, 0, 4, 1, 2)

        entry_layout.addWidget(QLabel("<b>Item</b>"), 1, 0)
        entry_layout.addWidget(self.purchase_item_combo, 1, 1, 1, 2)
        entry_layout.addWidget(QLabel("<b>Qty</b>"), 1, 3)
        entry_layout.addWidget(self.purchase_qty_spin, 1, 4)

        entry_layout.addWidget(QLabel("<b>Cost Price</b>"), 2, 0)
        entry_layout.addWidget(self.purchase_cost_spin, 2, 1)

        self.purchase_stock_preview_label = QLabel("")
        self.purchase_stock_preview_label.setObjectName("PurchaseStockPreview")
        entry_layout.addWidget(self.purchase_stock_preview_label, 2, 2, 1, 2)

        # Stock preview card (visual indicator)
        self.purchase_stock_card = QLabel("📦 Stock: --")
        self.purchase_stock_card.setObjectName("PurchaseStockCard")
        self.purchase_stock_card.setAlignment(Qt.AlignCenter)
        entry_layout.addWidget(self.purchase_stock_card, 2, 4, 1, 2)

        add_line_row = QHBoxLayout()
        add_line_row.addStretch()
        add_line_row.addWidget(self.add_line_btn)
        entry_layout.addLayout(add_line_row, 3, 0, 1, 6)

        purchase_builder_hint = QLabel(
            "Tip: Select item → set qty & cost → add line → repeat → save purchase."
        )
        purchase_builder_hint.setObjectName("PurchaseInlineFeedback")
        purchase_builder_hint.setMaximumHeight(20)
        entry_box.setMaximumHeight(220)

        self.purchase_lines_table = QTableWidget(0, 4)
        self.purchase_lines_table.setHorizontalHeaderLabels(
            ["Name", "Qty", "Cost", "Line Total"]
        )
        self.purchase_lines_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.purchase_lines_table.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.SelectedClicked | QTableWidget.EditKeyPressed
        )
        self.purchase_lines_table.setAlternatingRowColors(True)
        self.purchase_lines_table.itemChanged.connect(self._on_purchase_line_item_changed)
        self.purchase_lines_table.setSortingEnabled(True)
        self.purchase_lines_table.horizontalHeader().setStretchLastSection(True)
        self.purchase_lines_table.verticalHeader().setDefaultSectionSize(36)
        self.purchase_lines_table.setMinimumHeight(230)
        self.purchase_lines_table.horizontalHeaderItem(1).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.purchase_lines_table.horizontalHeaderItem(2).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.purchase_lines_table.horizontalHeaderItem(3).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.purchase_empty_state_label = QLabel(
            "📦  No purchase lines yet.\nSelect an item above and click '+ Add Item to Purchase'."
        )
        self.purchase_empty_state_label.setObjectName("PurchaseEmptyState")
        self.purchase_empty_state_label.setAlignment(Qt.AlignCenter)
        self.purchase_empty_state_label.setVisible(True)

        table_actions_row = QHBoxLayout()
        table_actions_row.setContentsMargins(0, 0, 0, 0)
        table_actions_row.setSpacing(8)
        table_actions_row.addWidget(self.remove_purchase_line_btn)
        table_actions_row.addWidget(self.clear_purchase_lines_btn)
        table_actions_row.addStretch()

        # Purchase line count badge
        self.purchase_line_count_card = QLabel("🧾 Lines: 0")
        self.purchase_line_count_card.setObjectName("PurchaseSummaryCard")
        self.purchase_line_count_card.setAlignment(Qt.AlignCenter)

        total_panel = QFrame()
        total_panel.setObjectName("PurchaseTotalPanel")
        total_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        total_panel.setMinimumHeight(118)
        total_layout = QVBoxLayout(total_panel)
        total_layout.setContentsMargins(12, 10, 12, 10)
        total_layout.setSpacing(6)

        self.purchase_total_label = QLabel("TOTAL: INR 0.00")
        self.purchase_total_label.setObjectName("PurchaseTotalLabel")
        self.purchase_total_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.purchase_total_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.purchase_total_label.setMinimumHeight(34)

        self.purchase_line_count_card.setMinimumWidth(120)
        self.purchase_line_count_card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.purchase_line_count_card.setMinimumHeight(34)

        total_top_row = QHBoxLayout()
        total_top_row.setContentsMargins(0, 0, 0, 0)
        total_top_row.setSpacing(8)
        total_top_row.addWidget(self.purchase_total_label, 1)
        total_top_row.addWidget(self.purchase_line_count_card, 0, Qt.AlignRight | Qt.AlignVCenter)

        actions_row = QHBoxLayout()
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(8)
        actions_row.addStretch()
        actions_row.addWidget(self.cancel_purchase_edit_btn)
        actions_row.addWidget(save_purchase_btn)

        footer_hint_row = QHBoxLayout()
        footer_hint_row.setContentsMargins(0, 0, 0, 0)
        footer_hint_row.setSpacing(0)
        footer_hint_row.addStretch()

        total_layout.addLayout(total_top_row)
        total_layout.addLayout(actions_row)
        total_layout.addLayout(footer_hint_row)

        self.purchase_mode_label = QLabel("Mode: New Purchase")
        self.purchase_mode_label.setObjectName("PurchaseInlineFeedback")
        self.purchase_mode_label.setMaximumHeight(20)
        self.purchase_feedback_label = QLabel("")
        self.purchase_feedback_label.setObjectName("PurchaseInlineFeedback")
        self.purchase_feedback_label.setVisible(False)
        purchase_hint = QLabel("Tip: Double-click Qty/Cost in a line to edit inline before saving purchase.")
        purchase_hint.setObjectName("PurchaseInlineFeedback")
        purchase_hint.setMaximumHeight(20)

        history_box = QGroupBox("Recent Purchases")
        history_layout = QVBoxLayout(history_box)

        history_filter_row = QHBoxLayout()
        self.purchase_history_table = QTableWidget(0, 6)
        self.purchase_history_table.setHorizontalHeaderLabels(
            ["ID", "Supplier", "Date", "Lines", "Total", "Notes"]
        )
        self.purchase_history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.purchase_history_table.setSortingEnabled(True)
        self.purchase_history_table.setAlternatingRowColors(True)
        self.purchase_history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.purchase_history_table.setMinimumHeight(230)
        self.purchase_history_table.itemDoubleClicked.connect(self._show_selected_purchase_details)
        self.purchase_history_table.horizontalHeader().setStretchLastSection(True)
        self.purchase_history_table.horizontalHeaderItem(3).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.purchase_history_table.horizontalHeaderItem(4).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

        history_actions = QHBoxLayout()
        history_actions.addWidget(modify_saved_btn)
        history_actions.addWidget(duplicate_saved_btn)
        history_actions.addStretch()

        self.purchase_from_date = QDateEdit()
        self.purchase_from_date.setCalendarPopup(True)
        self.purchase_from_date.setDisplayFormat("yyyy-MM-dd")
        self.purchase_from_date.setDate(QDate.currentDate())

        self.purchase_to_date = QDateEdit()
        self.purchase_to_date.setCalendarPopup(True)
        self.purchase_to_date.setDisplayFormat("yyyy-MM-dd")
        self.purchase_to_date.setDate(QDate.currentDate())

        self.purchase_filter_today_btn = QPushButton("Today")
        self.purchase_filter_today_btn.setObjectName("PurchaseFilterPreset")
        self.purchase_filter_today_btn.setCheckable(True)
        self.purchase_filter_today_btn.clicked.connect(lambda: self._set_purchase_filter_preset("today"))

        self.purchase_filter_7d_btn = QPushButton("Last 7 Days")
        self.purchase_filter_7d_btn.setObjectName("PurchaseFilterPreset")
        self.purchase_filter_7d_btn.setCheckable(True)
        self.purchase_filter_7d_btn.clicked.connect(lambda: self._set_purchase_filter_preset("last7"))

        self.purchase_filter_month_btn = QPushButton("This Month")
        self.purchase_filter_month_btn.setObjectName("PurchaseFilterPreset")
        self.purchase_filter_month_btn.setCheckable(True)
        self.purchase_filter_month_btn.clicked.connect(lambda: self._set_purchase_filter_preset("month"))

        self.purchase_filter_custom_btn = QPushButton("Custom")
        self.purchase_filter_custom_btn.setObjectName("PurchaseFilterPreset")
        self.purchase_filter_custom_btn.setCheckable(True)
        self.purchase_filter_custom_btn.clicked.connect(lambda: self._set_purchase_filter_preset("custom"))

        p_apply_btn = QPushButton("Apply")
        p_apply_btn.setObjectName("PurchaseFilterPreset")
        p_apply_btn.clicked.connect(lambda: self._set_purchase_filter_preset("custom"))

        history_filter_row.addWidget(QLabel("<b>From</b>"))
        history_filter_row.addWidget(self.purchase_from_date)
        history_filter_row.addWidget(QLabel("<b>To</b>"))
        history_filter_row.addWidget(self.purchase_to_date)
        history_filter_row.addWidget(self.purchase_filter_today_btn)
        history_filter_row.addWidget(self.purchase_filter_7d_btn)
        history_filter_row.addWidget(self.purchase_filter_month_btn)
        history_filter_row.addWidget(self.purchase_filter_custom_btn)
        history_filter_row.addWidget(p_apply_btn)
        history_filter_row.addStretch()

        history_layout.addLayout(history_filter_row)
        history_layout.addWidget(self.purchase_history_table)
        history_layout.addLayout(history_actions)

        refresh_btn = QPushButton("Refresh Purchases")
        refresh_btn.setObjectName("SecondaryPurchaseButton")
        refresh_btn.clicked.connect(self.refresh_purchases_tab)

        export_purchases_btn = QPushButton("Export CSV")
        export_purchases_btn.setObjectName("SecondaryPurchaseButton")
        export_purchases_btn.clicked.connect(self.export_purchases_csv)

        footer_row = QHBoxLayout()
        footer_row.addWidget(export_purchases_btn)
        footer_row.addWidget(refresh_btn)
        footer_row.addStretch()

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        left_layout.addWidget(self.purchase_lines_table)
        left_layout.addLayout(table_actions_row)
        left_layout.addWidget(self.purchase_empty_state_label)
        left_layout.addWidget(total_panel)
        left_layout.addWidget(purchase_hint)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        right_layout.addWidget(history_box)
        right_layout.addLayout(footer_row)

        workspace_splitter = QSplitter(Qt.Horizontal)
        workspace_splitter.setChildrenCollapsible(False)
        workspace_splitter.addWidget(left_panel)
        workspace_splitter.addWidget(right_panel)
        workspace_splitter.setStretchFactor(0, 3)
        workspace_splitter.setStretchFactor(1, 2)

        content_layout.addLayout(p_steps_row)
        content_layout.addWidget(entry_box)
        content_layout.addWidget(purchase_builder_hint)
        content_layout.addWidget(self.purchase_mode_label)
        content_layout.addWidget(self.purchase_feedback_label)
        content_layout.addWidget(workspace_splitter)

        main_scroll.setWidget(main_content)
        root_layout.addWidget(main_scroll)

        self.purchase_qty_spin.lineEdit().returnPressed.connect(self.add_purchase_line)
        self.purchase_cost_spin.lineEdit().returnPressed.connect(self.add_purchase_line)
        self._apply_purchases_panel_style(tab)
        self._update_purchase_stock_preview()
        self._set_purchase_filter_button_state("custom")
        return tab

    def _build_expenses_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("ExpensesTabRoot")
        root_layout = QVBoxLayout(tab)
        root_layout.setContentsMargins(0, 0, 0, 0)

        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setFrameShape(QFrame.NoFrame)
        
        main_content = QWidget()
        main_content.setObjectName("ExpensesPanel")
        content_layout = QVBoxLayout(main_content)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(15)

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
        self.expense_notes_input.setPlaceholderText("Optional notes")

        add_expense_btn = QPushButton("Add Expense")
        add_expense_btn.setObjectName("PrimaryExpenseButton")
        add_expense_btn.clicked.connect(self.add_expense)

        form_layout.addWidget(QLabel("<b>Type</b>"), 0, 0)
        form_layout.addWidget(self.expense_type_combo, 0, 1)
        form_layout.addWidget(QLabel("<b>Amount</b>"), 0, 2)
        form_layout.addWidget(self.expense_amount_spin, 0, 3)
        form_layout.addWidget(QLabel("<b>Notes</b>"), 1, 0)
        form_layout.addWidget(self.expense_notes_input, 1, 1, 1, 3)
        form_layout.addWidget(add_expense_btn, 2, 3)

        history_box = QGroupBox("Recent Expenses")
        history_layout = QVBoxLayout(history_box)
        self.expense_history_table = QTableWidget(0, 5)
        self.expense_history_table.setHorizontalHeaderLabels(["ID", "Type", "Amount", "Date", "Notes"])
        self.expense_history_table.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.SelectedClicked | QTableWidget.EditKeyPressed
        )
        self.expense_history_table.setAlternatingRowColors(True)
        self.expense_history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.expense_history_table.verticalHeader().setVisible(False)
        self.expense_history_table.verticalHeader().setDefaultSectionSize(34)
        self.expense_history_table.itemChanged.connect(self._on_expense_item_changed)
        self.expense_history_table.horizontalHeader().setStretchLastSection(True)
        history_layout.addWidget(self.expense_history_table)

        expense_hint = QLabel("Tip: Double-click Type, Amount, or Notes in Recent Expenses to edit inline.")
        expense_hint.setObjectName("OpsHintLabel")

        filter_box = QGroupBox("Expense Date Filter")
        filter_box.setObjectName("OpsSectionCard")
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
        e_today_btn.setObjectName("ExpenseFilterPreset")
        e_today_btn.clicked.connect(
            lambda: self._apply_quick_range(
                self.expense_from_date,
                self.expense_to_date,
                "today",
                self.refresh_expenses_tab,
            )
        )
        e_7d_btn = QPushButton("Last 7 Days")
        e_7d_btn.setObjectName("ExpenseFilterPreset")
        e_7d_btn.clicked.connect(
            lambda: self._apply_quick_range(
                self.expense_from_date,
                self.expense_to_date,
                "last7",
                self.refresh_expenses_tab,
            )
        )
        e_month_btn = QPushButton("This Month")
        e_month_btn.setObjectName("ExpenseFilterPreset")
        e_month_btn.clicked.connect(
            lambda: self._apply_quick_range(
                self.expense_from_date,
                self.expense_to_date,
                "month",
                self.refresh_expenses_tab,
            )
        )
        e_custom_btn = QPushButton("Custom")
        e_custom_btn.setObjectName("ExpenseFilterPreset")
        e_custom_btn.clicked.connect(self.refresh_expenses_tab)
        e_apply_btn = QPushButton("Apply")
        e_apply_btn.setObjectName("ExpenseFilterPreset")
        e_apply_btn.clicked.connect(self.refresh_expenses_tab)

        filter_layout.addWidget(QLabel("<b>From</b>"))
        filter_layout.addWidget(self.expense_from_date)
        filter_layout.addWidget(QLabel("<b>To</b>"))
        filter_layout.addWidget(self.expense_to_date)
        filter_layout.addWidget(e_today_btn)
        filter_layout.addWidget(e_7d_btn)
        filter_layout.addWidget(e_month_btn)
        filter_layout.addWidget(e_custom_btn)
        filter_layout.addWidget(e_apply_btn)
        filter_layout.addStretch()

        refresh_btn = QPushButton("Refresh Expenses")
        refresh_btn.setObjectName("SecondaryExpenseButton")
        refresh_btn.clicked.connect(self.refresh_expenses_tab)

        export_expenses_btn = QPushButton("Export CSV")
        export_expenses_btn.setObjectName("SecondaryExpenseButton")
        export_expenses_btn.clicked.connect(self.export_expenses_csv)

        expenses_actions_row = QHBoxLayout()
        expenses_actions_row.setContentsMargins(0, 0, 0, 0)
        expenses_actions_row.setSpacing(8)
        expenses_actions_row.addWidget(export_expenses_btn)
        expenses_actions_row.addWidget(refresh_btn)
        expenses_actions_row.addStretch()

        content_layout.addWidget(entry_box)
        content_layout.addWidget(expense_hint)
        content_layout.addWidget(filter_box)
        content_layout.addWidget(history_box)
        content_layout.addLayout(expenses_actions_row)

        main_scroll.setWidget(main_content)
        root_layout.addWidget(main_scroll)

        self._apply_expenses_panel_style(tab)
        return tab

    def _apply_expenses_panel_style(self, tab: QWidget) -> None:
        T = self.THEME
        tab.setStyleSheet(f"""
            #ExpensesPanel {{
                background-color: {T['bg_deep']};
            }}
            #ExpensesPanel QGroupBox {{
                border: 1.5px solid {T['border_bold']};
                border-radius: 12px;
                background-color: {T['bg_surface']};
                margin-top: 15px;
                padding-top: 15px;
            }}
            QPushButton#ExpenseFilterPreset {{
                background-color: {T['bg_surface']};
                color: {T['text_medium']};
                border: 1.5px solid {T['border_bold']};
                border-radius: 15px;
                padding: 6px 15px;
                font-weight: 700;
            }}
            QPushButton#ExpenseFilterPreset:checked {{
                background-color: {T['text_primary']};
                color: white;
                border-color: {T['text_primary']};
            }}
            QPushButton#PrimaryExpenseButton {{
                background-color: {T['accent_primary']};
                color: white;
                font-weight: 800;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
            }}
            QPushButton#SecondaryExpenseButton {{
                background-color: {T['bg_surface']};
                color: {T['text_primary']};
                border: 1.5px solid {T['border_bold']};
                font-weight: 700;
                border-radius: 8px;
                padding: 10px;
            }}
        """)

    def _build_reports_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("ReportsPanel")
        root_layout = QVBoxLayout(tab)

        title = QLabel("Operations Dashboard")
        title.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {self.THEME['text_primary']};")

        subtitle = QLabel("Live performance snapshot for sales, stock, and profitability")
        subtitle.setStyleSheet(f"color: {self.THEME['text_medium']};")

        cards_grid = QGridLayout()
        cards_grid.setHorizontalSpacing(10)
        cards_grid.setVerticalSpacing(10)

        sales_card, self.sales_value = self._make_report_metric_card("Sales", "#4caf50")
        cogs_card, self.cogs_value = self._make_report_metric_card("COGS", "#ffb74d")
        gross_card, self.gross_profit_value = self._make_report_metric_card("Gross Profit", "#64b5f6")
        purchases_card, self.purchases_value = self._make_report_metric_card("Purchases", "#9575cd")
        expenses_card, self.expenses_value = self._make_report_metric_card("Expenses", "#ef5350")
        fixed_daily_card, self.fixed_daily_value = self._make_report_metric_card("Period Fixed Cost", "#ff7043")
        net_card, self.net_value = self._make_report_metric_card("Net Profit", "#26c6da")

        self.metric_cards = [
            sales_card,
            cogs_card,
            gross_card,
            purchases_card,
            expenses_card,
            fixed_daily_card,
            net_card,
        ]
        self.reports_cards_grid = cards_grid
        # Arrangement is handled by _apply_adaptive_layout via resizeEvent

        fixed_cost_box = QGroupBox("Monthly Fixed Costs (Auto-divided daily)")
        fixed_cost_box.setObjectName("DataOpsSectionBox")
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
        save_fixed_btn.setObjectName("DataOpsPrimaryButton")
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

        daily_overhead_box = QGroupBox("Daily Variable Overhead (for Recipe Costing)")
        daily_overhead_box.setObjectName("DataOpsSectionBox")
        daily_overhead_layout = QGridLayout(daily_overhead_box)
        self.overhead_date_edit = QDateEdit()
        self.overhead_date_edit.setCalendarPopup(True)
        self.overhead_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.overhead_date_edit.setDate(QDate.currentDate())
        self.overhead_date_edit.dateChanged.connect(self.refresh_reports)

        self.overhead_gas_spin = QDoubleSpinBox()
        self.overhead_gas_spin.setPrefix("INR ")
        self.overhead_gas_spin.setMaximum(100000000)
        self.overhead_labor_spin = QDoubleSpinBox()
        self.overhead_labor_spin.setPrefix("INR ")
        self.overhead_labor_spin.setMaximum(100000000)
        self.overhead_misc_spin = QDoubleSpinBox()
        self.overhead_misc_spin.setPrefix("INR ")
        self.overhead_misc_spin.setMaximum(100000000)
        self.overhead_units_spin = QDoubleSpinBox()
        self.overhead_units_spin.setMaximum(100000000)

        save_overhead_btn = QPushButton("Save Daily Overhead")
        save_overhead_btn.setObjectName("DataOpsPrimaryButton")
        save_overhead_btn.clicked.connect(self.save_daily_overhead)

        self.overhead_per_unit_label = QLabel("Overhead / Unit: INR 0.00")
        self.overhead_per_unit_label.setStyleSheet("font-weight: bold;")

        daily_overhead_layout.addWidget(QLabel("Date"), 0, 0)
        daily_overhead_layout.addWidget(self.overhead_date_edit, 0, 1)
        daily_overhead_layout.addWidget(QLabel("Gas"), 0, 2)
        daily_overhead_layout.addWidget(self.overhead_gas_spin, 0, 3)
        daily_overhead_layout.addWidget(QLabel("Labor"), 1, 0)
        daily_overhead_layout.addWidget(self.overhead_labor_spin, 1, 1)
        daily_overhead_layout.addWidget(QLabel("Misc"), 1, 2)
        daily_overhead_layout.addWidget(self.overhead_misc_spin, 1, 3)
        daily_overhead_layout.addWidget(QLabel("Expected Units"), 2, 0)
        daily_overhead_layout.addWidget(self.overhead_units_spin, 2, 1)
        daily_overhead_layout.addWidget(self.overhead_per_unit_label, 2, 2)
        daily_overhead_layout.addWidget(save_overhead_btn, 2, 3)

        backup_automation_box = QGroupBox("Backup Automation")
        backup_auto_layout = QHBoxLayout(backup_automation_box)
        self.auto_backup_enabled_checkbox = QCheckBox("Enable scheduled backup")
        self.auto_backup_interval_spin = QSpinBox()
        self.auto_backup_interval_spin.setRange(5, 1440)
        self.auto_backup_interval_spin.setSuffix(" min")
        auto_backup_save_btn = QPushButton("Save Backup Schedule")
        auto_backup_save_btn.setObjectName("DataOpsPrimaryButton")
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
        self.sales_trend_table.setMinimumHeight(240)
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
        self.top_items_table.setMinimumHeight(240)
        self.top_items_table.setColumnWidth(0, 220)
        top_items_layout.addWidget(self.top_items_table)

        payment_box = QGroupBox("Payment Breakdown")
        payment_layout = QVBoxLayout(payment_box)
        self.payment_breakdown_table = QTableWidget(0, 3)
        self.payment_breakdown_table.setHorizontalHeaderLabels(["Method", "Bills", "Amount"])
        self._style_report_table(self.payment_breakdown_table)
        self._apply_report_column_modes(
            self.payment_breakdown_table,
            [
                QHeaderView.Stretch,
                QHeaderView.ResizeToContents,
                QHeaderView.ResizeToContents,
            ],
        )
        self.payment_breakdown_table.setMinimumHeight(160)
        payment_layout.addWidget(self.payment_breakdown_table)

        recent_sales_box = QGroupBox("Recent Sales")
        recent_sales_layout = QVBoxLayout(recent_sales_box)
        self.recent_sales_table = QTableWidget(0, 6)
        self.recent_sales_table.setHorizontalHeaderLabels(
            ["Invoice", "Time", "Payment", "Customer", "Phone", "Amount"]
        )
        self._style_report_table(self.recent_sales_table)
        self._apply_report_column_modes(
            self.recent_sales_table,
            [
                QHeaderView.ResizeToContents,
                QHeaderView.ResizeToContents,
                QHeaderView.ResizeToContents,
                QHeaderView.Stretch,
                QHeaderView.ResizeToContents,
                QHeaderView.ResizeToContents,
            ],
        )
        self.recent_sales_table.setMinimumHeight(170)
        recent_sales_layout.addWidget(self.recent_sales_table)

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
        refresh_reports_btn.setObjectName("PrimaryReportButton")
        refresh_reports_btn.clicked.connect(self.refresh_reports)

        close_day_btn = QPushButton("Close Day (Ctrl+L)")
        close_day_btn.setObjectName("DataOpsWarningButton")
        close_day_btn.clicked.connect(self.close_day)

        backup_btn = QPushButton("Backup Now")
        backup_btn.setObjectName("DataOpsPrimaryButton")
        backup_btn.clicked.connect(self.backup_now)

        export_btn = QPushButton("Export DB Backup")
        export_btn.setObjectName("DataOpsExportButton")
        export_btn.clicked.connect(self.export_backup_dialog)

        restore_btn = QPushButton("Restore DB Backup")
        restore_btn.setObjectName("DataOpsDangerButton")
        restore_btn.clicked.connect(self.restore_backup_dialog)

        license_btn = QPushButton("Manage License")
        license_btn.setObjectName("DataOpsExportButton")
        license_btn.clicked.connect(self.manage_license)

        export_reports_btn = QPushButton("Export CSV")
        export_reports_btn.setObjectName("DataOpsExportButton")
        export_reports_btn.clicked.connect(self.export_reports_csv)

        export_reports_xlsx_btn = QPushButton("Export XLSX")
        export_reports_xlsx_btn.setObjectName("DataOpsExportButton")
        export_reports_xlsx_btn.clicked.connect(self.export_reports_xlsx)

        export_all_btn = QPushButton("Export All CSV")
        export_all_btn.setObjectName("DataOpsExportButton")
        export_all_btn.clicked.connect(self.export_all_csv)

        print_summary_btn = QPushButton("Print Summary")
        print_summary_btn.setObjectName("DataOpsExportButton")
        print_summary_btn.clicked.connect(self.export_printable_summary)

        self.report_from_date = QDateEdit()
        self.report_from_date.setCalendarPopup(True)
        self.report_from_date.setDisplayFormat("yyyy-MM-dd")
        self.report_from_date.setDate(QDate.currentDate().addDays(-6))
        self.report_from_date.setMinimumWidth(132)

        self.report_to_date = QDateEdit()
        self.report_to_date.setCalendarPopup(True)
        self.report_to_date.setDisplayFormat("yyyy-MM-dd")
        self.report_to_date.setDate(QDate.currentDate())
        self.report_to_date.setMinimumWidth(132)

        r_today_btn = QPushButton("Today")
        r_today_btn.setObjectName("ReportFilterPreset")
        r_today_btn.clicked.connect(
            lambda: self._apply_quick_range(
                self.report_from_date,
                self.report_to_date,
                "today",
                self.refresh_reports,
            )
        )
        r_7d_btn = QPushButton("Last 7 Days")
        r_7d_btn.setObjectName("ReportFilterPreset")
        r_7d_btn.clicked.connect(
            lambda: self._apply_quick_range(
                self.report_from_date,
                self.report_to_date,
                "last7",
                self.refresh_reports,
            )
        )
        r_month_btn = QPushButton("This Month")
        r_month_btn.setObjectName("ReportFilterPreset")
        r_month_btn.clicked.connect(
            lambda: self._apply_quick_range(
                self.report_from_date,
                self.report_to_date,
                "month",
                self.refresh_reports,
            )
        )
        r_custom_btn = QPushButton("Custom")
        r_custom_btn.setObjectName("ReportFilterPreset")
        r_custom_btn.clicked.connect(self.refresh_reports)

        self.top_items_limit_spin = QSpinBox()
        self.top_items_limit_spin.setRange(5, 100)
        self.top_items_limit_spin.setValue(20)
        self.recent_sales_limit_spin = QSpinBox()
        self.recent_sales_limit_spin.setRange(10, 500)
        self.recent_sales_limit_spin.setValue(80)
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
        reports_tabs.setObjectName("ReportsSubTabs")
        reports_tabs.setDocumentMode(True)
        reports_tabs.setMovable(False)
        reports_tabs.setUsesScrollButtons(False)
        self.reports_tabs = reports_tabs

        overview_tab = QWidget()
        overview_tab.setObjectName("ReportsOverviewTab")
        overview_layout = QVBoxLayout(overview_tab)
        overview_filters_box = QGroupBox("Overview Filters")
        overview_filters_layout = QGridLayout(overview_filters_box)
        overview_filters_layout.setHorizontalSpacing(10)
        overview_filters_layout.setVerticalSpacing(8)
        overview_filters_layout.addWidget(QLabel("<b>From</b>"), 0, 0)
        overview_filters_layout.addWidget(self.report_from_date, 0, 1)
        overview_filters_layout.addWidget(QLabel("<b>To</b>"), 0, 2)
        overview_filters_layout.addWidget(self.report_to_date, 0, 3)
        overview_filters_layout.addWidget(r_today_btn, 0, 4)
        overview_filters_layout.addWidget(r_7d_btn, 0, 5)
        overview_filters_layout.addWidget(r_month_btn, 0, 6)
        overview_filters_layout.addWidget(r_custom_btn, 0, 7)
        overview_filters_layout.addWidget(QLabel("<b>Top Items</b>"), 1, 0)
        overview_filters_layout.addWidget(self.top_items_limit_spin, 1, 1)
        overview_filters_layout.addWidget(QLabel("<b>Recent Sales</b>"), 1, 3)
        overview_filters_layout.addWidget(self.recent_sales_limit_spin, 1, 4)
        overview_filters_layout.addWidget(refresh_reports_btn, 1, 2)
        overview_filters_layout.setColumnStretch(8, 1)

        overview_tables_splitter = QSplitter(Qt.Horizontal)
        overview_tables_splitter.setChildrenCollapsible(False)
        overview_tables_splitter.addWidget(trend_box)
        sales_ops_splitter = QSplitter(Qt.Vertical)
        sales_ops_splitter.setChildrenCollapsible(False)
        sales_ops_splitter.addWidget(top_items_box)
        sales_ops_splitter.addWidget(payment_box)
        sales_ops_splitter.addWidget(recent_sales_box)
        overview_tables_splitter.addWidget(sales_ops_splitter)
        overview_tables_splitter.setStretchFactor(0, 3)
        overview_tables_splitter.setStretchFactor(1, 2)

        self.waste_summary_label = QLabel("Waste in range: Qty 0.00 | Estimated Cost INR 0.00")
        self.waste_summary_label.setStyleSheet("font-weight: 600; color: #f4d36a;")

        overview_layout.addWidget(overview_filters_box)
        overview_layout.addWidget(overview_tables_splitter)

        stock_tab = QWidget()
        stock_tab.setObjectName("ReportsStockTab")
        stock_layout = QVBoxLayout(stock_tab)
        stock_refresh_btn = QPushButton("Refresh Stock and Audit")
        stock_refresh_btn.setObjectName("PrimaryReportButton")
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
        refresh_audit_btn.setObjectName("PrimaryReportButton")
        refresh_audit_btn.clicked.connect(self.refresh_reports)
        export_audit_csv_btn = QPushButton("Export Audit CSV")
        export_audit_csv_btn.setObjectName("DataOpsExportButton")
        export_audit_csv_btn.clicked.connect(self.export_audit_csv)
        export_audit_xlsx_btn = QPushButton("Export Audit XLSX")
        export_audit_xlsx_btn.setObjectName("DataOpsExportButton")
        export_audit_xlsx_btn.clicked.connect(self.export_audit_xlsx)
        audit_actions = QHBoxLayout()
        audit_actions.addWidget(refresh_audit_btn)
        audit_actions.addWidget(export_audit_csv_btn)
        audit_actions.addWidget(export_audit_xlsx_btn)
        audit_actions.addStretch()
        audit_box_layout.addWidget(self.audit_log_table)
        audit_box_layout.addLayout(audit_actions)

        costing_exceptions_box = QGroupBox("Costing Exceptions")
        costing_exceptions_layout = QVBoxLayout(costing_exceptions_box)
        self.costing_exceptions_table = QTableWidget(0, 6)
        self.costing_exceptions_table.setHorizontalHeaderLabels(
            ["Time", "Type", "Item", "Sale ID", "Item ID", "Details"]
        )
        self._style_report_table(self.costing_exceptions_table)
        self._apply_report_column_modes(
            self.costing_exceptions_table,
            [
                QHeaderView.ResizeToContents,
                QHeaderView.ResizeToContents,
                QHeaderView.ResizeToContents,
                QHeaderView.ResizeToContents,
                QHeaderView.ResizeToContents,
                QHeaderView.Stretch,
            ],
        )
        costing_exceptions_layout.addWidget(self.costing_exceptions_table)

        stock_layout.addWidget(audit_box)
        stock_layout.addWidget(costing_exceptions_box)

        data_ops_tab = QWidget()
        data_ops_tab.setObjectName("ReportsDataOpsTab")
        data_ops_layout = QVBoxLayout(data_ops_tab)
        data_ops_layout.setSpacing(8)

        data_ops_buttons = [
            close_day_btn,
            backup_btn,
            export_btn,
            restore_btn,
            license_btn,
            export_reports_btn,
            export_reports_xlsx_btn,
            export_all_btn,
            print_summary_btn,
            auto_backup_save_btn,
            save_fixed_btn,
        ]
        for button in data_ops_buttons:
            button.setMinimumHeight(38)
            button.setMaximumHeight(38)



        role_and_close_box = QGroupBox("Access and Closing")
        role_and_close_box.setObjectName("DataOpsSectionBox")
        role_and_close_layout = QHBoxLayout(role_and_close_box)
        role_and_close_layout.addWidget(QLabel("Role"))
        role_and_close_layout.addWidget(self.role_combo)
        role_and_close_layout.addWidget(close_day_btn)
        role_and_close_layout.addStretch()

        backup_actions_box = QGroupBox("Backup and Restore")
        backup_actions_box.setObjectName("DataOpsSectionBox")
        backup_actions_layout = QHBoxLayout(backup_actions_box)
        backup_actions_layout.addWidget(backup_btn)
        backup_actions_layout.addWidget(export_btn)
        backup_actions_layout.addWidget(restore_btn)
        backup_actions_layout.addWidget(license_btn)
        backup_actions_layout.addStretch()

        report_exports_box = QGroupBox("Reporting Exports")
        report_exports_box.setObjectName("DataOpsSectionBox")
        report_exports_layout = QHBoxLayout(report_exports_box)
        report_exports_layout.addWidget(export_reports_btn)
        report_exports_layout.addWidget(export_reports_xlsx_btn)
        report_exports_layout.addWidget(export_all_btn)
        report_exports_layout.addWidget(print_summary_btn)
        report_exports_layout.addWidget(self.open_after_export_checkbox)
        report_exports_layout.addStretch()

        backup_automation_box.setObjectName("DataOpsSectionBox")
        fixed_cost_box.setObjectName("DataOpsSectionBox")
        daily_overhead_box.setObjectName("DataOpsSectionBox")

        separator_one = QFrame()
        separator_one.setFrameShape(QFrame.HLine)
        separator_one.setStyleSheet(f"color: {self.THEME['border']};")

        separator_two = QFrame()
        separator_two.setFrameShape(QFrame.HLine)
        separator_two.setStyleSheet(f"color: {self.THEME['border']};")

        separator_three = QFrame()
        separator_three.setFrameShape(QFrame.HLine)
        separator_three.setStyleSheet(f"color: {self.THEME['border']};")

        separator_four = QFrame()
        separator_four.setFrameShape(QFrame.HLine)
        separator_four.setStyleSheet(f"color: {self.THEME['border']};")

        separator_five = QFrame()
        separator_five.setFrameShape(QFrame.HLine)
        separator_five.setStyleSheet(f"color: {self.THEME['border']};")

        data_ops_layout.addWidget(role_and_close_box)
        data_ops_layout.addWidget(separator_one)
        data_ops_layout.addWidget(backup_actions_box)
        data_ops_layout.addWidget(separator_two)
        data_ops_layout.addWidget(backup_automation_box)
        data_ops_layout.addWidget(separator_three)
        data_ops_layout.addWidget(fixed_cost_box)
        data_ops_layout.addWidget(separator_four)
        data_ops_layout.addWidget(daily_overhead_box)
        data_ops_layout.addWidget(separator_five)
        data_ops_layout.addWidget(report_exports_box)
        data_ops_layout.addStretch()

        reports_tabs.addTab(overview_tab, "Overview")
        reports_tabs.addTab(stock_tab, "Stock & Audit")
        reports_tabs.addTab(data_ops_tab, "Data Ops")

        # Wrap everything in the reports tab in a single ScrollArea for perfect adaptability
        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setFrameShape(QFrame.NoFrame)
        
        main_container = QWidget()
        main_container.setObjectName("ReportsContent")
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addLayout(cards_grid)
        main_layout.addWidget(self.waste_summary_label)
        main_layout.addWidget(reports_tabs)
        
        main_scroll.setWidget(main_container)
        root_layout.addWidget(main_scroll)

        self._apply_report_table_width_profiles()
        self._apply_reports_panel_style(tab)

        return tab

    def _apply_reports_panel_style(self, tab: QWidget) -> None:
        T = self.THEME
        tab.setStyleSheet(f"""
            #ReportsPanel, #ReportsOverviewTab, #ReportsContent, #ReportsDataOpsTab, #ReportsStockTab, QWidget#ReportsDataOpsTab, QWidget#ReportsStockTab {{
                background-color: {T['bg_deep']};
            }}
            QGroupBox {{
                background-color: {T['bg_surface']};
                color: {T['text_primary']};
            }}
            #ReportsPanel QGroupBox, #ReportsOverviewTab QGroupBox, #ReportsStockTab QGroupBox, #ReportsDataOpsTab QGroupBox {{
                border: 1.5px solid {T['border_bold']};
                border-radius: 12px;
                background-color: {T['bg_surface']};
                margin-top: 15px;
                padding-top: 20px;
                color: {T['text_primary']};
            }}
            #ReportsPanel QGroupBox::title, #ReportsOverviewTab QGroupBox::title, #ReportsStockTab QGroupBox::title, #ReportsDataOpsTab QGroupBox::title {{
                color: {T['text_primary']};
                font-weight: bold;
            }}
            #ReportsPanel QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            #ReportsPanel QScrollArea > QWidget {{
                background-color: transparent;
            }}
            QPushButton#ReportFilterPreset {{
                background-color: {T['bg_surface']};
                color: {T['text_medium']};
                border: 1.5px solid {T['border_bold']};
                border-radius: 15px;
                padding: 6px 15px;
                font-weight: 700;
            }}
            QPushButton#ReportFilterPreset:checked {{
                background-color: {T['text_primary']};
                color: white;
                border-color: {T['text_primary']};
            }}
            
            /* Data Ops & Primary Buttons */
            #PrimaryReportButton, #DataOpsPrimaryButton {{
                background-color: {T['accent_primary']};
                color: white;
                font-weight: 900;
                border-radius: 8px;
                padding: 10px 20px;
                border: none;
            }}
            #DataOpsExportButton {{
                background-color: {T['bg_surface']};
                color: {T['text_primary']};
                border: 1.5px solid {T['border_bold']};
                font-weight: 700;
                border-radius: 8px;
                padding: 10px 20px;
            }}
            #DataOpsWarningButton {{
                background-color: {T['accent_gold']};
                color: white;
                font-weight: 800;
                border-radius: 8px;
                padding: 10px 20px;
                border: none;
            }}
            #DataOpsDangerButton {{
                background-color: {T['danger']};
                color: white;
                font-weight: 800;
                border-radius: 8px;
                padding: 10px 20px;
                border: none;
            }}
            
            #ReportsPanel QHeaderView, #ReportsPanel QHeaderView::section {{
                background-color: {T['bg_deep']};
                color: {T['text_primary']};
            }}
        """)

    def _make_report_metric_card(self, heading: str, accent_color: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet(f"""
            QFrame {{
                border: 1.5px solid {self.THEME['border_bold']};
                border-radius: 12px;
                background-color: {self.THEME['bg_surface']};
                padding: 12px;
            }}
        """)

        layout = QVBoxLayout(card)
        title = QLabel(heading)
        title.setStyleSheet(f"color: {accent_color}; font-weight: bold;")

        value = QLabel("INR 0.00")
        value.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {self.THEME['text_primary']};")

        layout.addWidget(title)
        layout.addWidget(value)
        layout.addStretch()
        return card, value

    def _style_report_table(self, table: QTableWidget) -> None:
        T = self.THEME
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
        table.setStyleSheet(f"""
            QTableWidget {{
                gridline-color: {T['border_bold']};
                alternate-background-color: {T['bg_surface_light']};
                background-color: {T['bg_surface']};
                border: 1.5px solid {T['border_bold']};
                border-radius: 8px;
                selection-background-color: #e2e8f0;
                selection-color: {T['text_primary']};
                color: {T['text_primary']};
            }}
            QHeaderView::section {{
                background-color: {T['bg_deep']};
                color: {T['text_primary']};
                padding: 8px 10px;
                border: none;
                border-right: 1px solid {T['border_bold']};
                border-bottom: 2px solid {T['border_bold']};
                font-weight: 800;
                text-transform: uppercase;
                font-size: 11px;
            }}
        """)

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
        return table_rows_for_csv(table)

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
        write_csv_file(path, rows)

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
        rows.append(["Period Fixed Cost", self.fixed_daily_value.text().replace("INR ", "")])
        rows.append(["Net Profit", self.net_value.text().replace("INR ", "")])
        rows.append(["Monthly Fixed Total", self.monthly_fixed_total_label.text().replace("Monthly Fixed Total: INR ", "")])
        if hasattr(self, "waste_summary_label"):
            rows.append(["Waste", self.waste_summary_label.text().replace("Waste in range: ", "")])
        rows.append([])

        rows.append(["Sales Trend"])
        rows.extend(self._table_rows_for_csv(self.sales_trend_table))
        rows.append([])

        rows.append(["Top Selling Items"])
        rows.extend(self._table_rows_for_csv(self.top_items_table))
        rows.append([])

        if hasattr(self, "payment_breakdown_table"):
            rows.append(["Payment Breakdown"])
            rows.extend(self._table_rows_for_csv(self.payment_breakdown_table))
            rows.append([])

        if hasattr(self, "recent_sales_table"):
            rows.append(["Recent Sales"])
            rows.extend(self._table_rows_for_csv(self.recent_sales_table))
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

    def save_daily_overhead(self) -> None:
        pin = self._require_admin_access("Save Daily Overhead")
        if pin is None:
            return

        try:
            self.bookkeeping_service.set_daily_overhead(
                overhead_date=self.overhead_date_edit.date().toString("yyyy-MM-dd"),
                gas_cost=float(self.overhead_gas_spin.value()),
                labor_cost=float(self.overhead_labor_spin.value()),
                misc_cost=float(self.overhead_misc_spin.value()),
                expected_units=float(self.overhead_units_spin.value()),
                admin_pin=pin,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Daily Overhead", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Daily Overhead Error", str(exc))
            return

        QMessageBox.information(self, "Daily Overhead", "Daily overhead saved.")
        self.refresh_reports()

    def refresh_all(self) -> None:
        self.refresh_categories()
        self.refresh_recipe_tab()
        self.refresh_inventory()
        self.refresh_billing_items()
        self.refresh_purchases_tab()
        self.refresh_expenses_tab()
        self.refresh_reports()
        self._apply_role_permissions()

    def refresh_categories(self) -> None:
        categories = self.inventory_service.list_categories()
        self.category_combo.clear()
        self.category_combo.addItem("Uncategorized", None)
        for category in categories:
            self.category_combo.addItem(category["name"], category["id"])

        if hasattr(self, "inventory_filter_category_combo"):
            current = self.inventory_filter_category_combo.currentData()
            self.inventory_filter_category_combo.blockSignals(True)
            self.inventory_filter_category_combo.clear()
            self.inventory_filter_category_combo.addItem("All Categories", None)
            for category in categories:
                self.inventory_filter_category_combo.addItem(category["name"], category["id"])
            index = self.inventory_filter_category_combo.findData(current)
            if index >= 0:
                self.inventory_filter_category_combo.setCurrentIndex(index)
            self.inventory_filter_category_combo.blockSignals(False)

    def refresh_inventory(self) -> None:
        self.inventory_items_cache = self.inventory_service.list_items()
        self.apply_inventory_filter()
        if hasattr(self, "inventory_inline_status_label"):
            self.inventory_inline_status_label.setVisible(False)

    def _on_inventory_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_inventory_table:
            return

        column = item.column()
        if column not in (4, 6):
            return

        row = item.row()
        item_id = self._inventory_id_for_row(row)
        sell_cell = self.inventory_items_table.item(row, 4)
        reorder_cell = self.inventory_items_table.item(row, 6)
        if item_id is None or sell_cell is None or reorder_cell is None:
            return

        pin = self._require_admin_access("Inventory Edit")
        if pin is None:
            self.refresh_inventory()
            return

        try:
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
        self.inventory_inline_status_label.setText(
            f"Saved inline edit for item #{item_id}: Sell={selling_price:.2f}, Reorder={reorder_level:.2f}"
        )
        self.inventory_inline_status_label.setVisible(True)
        QTimer.singleShot(2200, lambda: self.inventory_inline_status_label.setVisible(False))
        self._log_audit("inventory_inline_edit", "item", str(item_id), f"sell={selling_price}, reorder={reorder_level}")

    def refresh_purchases_tab(self) -> None:
        items = self.inventory_service.list_items()
        
        # Only include items that are purchased (ingredients or manual-costing packed goods).
        # Items with 'recipe' costing mode are made in-house and cannot be directly purchased.
        purchasable_items = [
            item for item in items 
            if item.get("costing_mode", "manual") == "manual"
        ]
        
        self.purchase_item_cache = {int(item["id"]): item for item in purchasable_items}

        self.purchase_item_combo.clear()
        for item in purchasable_items:
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
            lines_item = QTableWidgetItem(str(purchase["line_items"]))
            lines_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.purchase_history_table.setItem(row_index, 3, lines_item)
            self.purchase_history_table.setItem(
                row_index,
                4,
                QTableWidgetItem(f"{float(purchase['total_cost']):.2f}"),
            )
            total_item = self.purchase_history_table.item(row_index, 4)
            if total_item is not None:
                total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
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
        self._update_purchase_stock_preview()

    def _update_purchase_stock_preview(self) -> None:
        if not hasattr(self, "purchase_stock_preview_label"):
            return

        item_id = self.purchase_item_combo.currentData()
        if item_id is None:
            self.purchase_stock_preview_label.setText("")
            if hasattr(self, "purchase_stock_card"):
                self.purchase_stock_card.setText("📦 Stock: --")
                self.purchase_stock_card.setStyleSheet("")
            return

        item = self.purchase_item_cache.get(int(item_id))
        if item is None:
            self.purchase_stock_preview_label.setText("")
            if hasattr(self, "purchase_stock_card"):
                self.purchase_stock_card.setText("📦 Stock: --")
                self.purchase_stock_card.setStyleSheet("")
            return

        current_stock = float(item.get("stock_quantity") or 0)
        reorder = float(item.get("reorder_level") or 0)
        added_qty = float(self.purchase_qty_spin.value())
        projected_stock = current_stock + added_qty
        self.purchase_stock_preview_label.setText(
            f"Stock after purchase: {current_stock:.2f} → {projected_stock:.2f}"
        )

        # Update visual stock card
        if hasattr(self, "purchase_stock_card"):
            T = self.THEME
            if current_stock <= 0:
                color, bg = T["danger"], "#fef2f2"
                icon = "🔴"
            elif current_stock <= reorder:
                color, bg = T["accent_gold"], "#fff9eb"
                icon = "🟡"
            else:
                color, bg = T["success"], "#f0fdf4"
                icon = "🟢"
            self.purchase_stock_card.setText(f"{icon} Stock: {current_stock:.1f}")
            self.purchase_stock_card.setStyleSheet(
                f"color: {color}; font-weight: 800; border: 1.5px solid {color}; "
                f"border-radius: 8px; background-color: {bg}; padding: 4px 10px; font-size: 12px;"
            )

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
        if cost_price <= 0:
            QMessageBox.warning(self, "Purchase", "Cost price must be greater than zero.")
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
        self.purchase_qty_spin.setValue(1)
        self.purchase_item_combo.setFocus()
        if hasattr(self, "purchase_feedback_label"):
            self.purchase_feedback_label.setText(f"Added {item['name']} (Qty {quantity:.2f})")
            self.purchase_feedback_label.setVisible(True)
            QTimer.singleShot(1800, lambda: self.purchase_feedback_label.setVisible(False))

    def remove_selected_purchase_line(self) -> None:
        selected = self.purchase_lines_table.currentRow()
        if selected < 0:
            QMessageBox.information(self, "Purchase", "Please select a purchase line.")
            return

        name_item = self.purchase_lines_table.item(selected, 0)
        if name_item is None:
            return
        item_id = int(name_item.data(Qt.UserRole))
        self.purchase_cart = [line for line in self.purchase_cart if int(line["item_id"]) != item_id]
        self.refresh_purchase_lines_table()

    def clear_purchase_lines(self) -> None:
        self.purchase_cart = []
        self.refresh_purchase_lines_table()

    def _set_purchase_mode(self, editing: bool, purchase_id: int | None = None) -> None:
        if editing and purchase_id is not None:
            self.editing_purchase_id = int(purchase_id)
            self.save_purchase_btn.setText("Update Purchase")
            self.cancel_purchase_edit_btn.setVisible(True)
            self.cancel_purchase_edit_btn.setEnabled(True)
            self.purchase_mode_label.setText(f"Mode: Editing Purchase #{purchase_id}")
        else:
            self.editing_purchase_id = None
            self.save_purchase_btn.setText("Save Purchase")
            self.cancel_purchase_edit_btn.setVisible(False)
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
        self.purchase_lines_table.setSortingEnabled(False)
        total = 0.0
        for row_index, line in enumerate(self.purchase_cart):
            line_total = float(line["quantity"]) * float(line["cost_price"])
            total += line_total
            name_item = QTableWidgetItem(line["name"])
            name_item.setData(Qt.UserRole, int(line["item_id"]))
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.purchase_lines_table.setItem(row_index, 0, name_item)

            qty_item = QTableWidgetItem(f"{line['quantity']:.2f}")
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.purchase_lines_table.setItem(row_index, 1, qty_item)

            cost_item = QTableWidgetItem(f"{line['cost_price']:.2f}")
            cost_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.purchase_lines_table.setItem(row_index, 2, cost_item)

            total_item = QTableWidgetItem(f"{line_total:.2f}")
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
            self.purchase_lines_table.setItem(row_index, 3, total_item)

        self.purchase_lines_table.setSortingEnabled(True)
        self._updating_purchase_table = False
        self.purchase_empty_state_label.setVisible(len(self.purchase_cart) == 0)

        self.purchase_total_label.setText(f"TOTAL: INR {total:.2f}")
        if hasattr(self, "purchase_line_count_card"):
            self.purchase_line_count_card.setText(f"🧾 Lines: {len(self.purchase_cart)}")

    def _on_purchase_line_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_purchase_table:
            return

        row = item.row()
        column = item.column()
        if column not in (1, 2):
            return

        name_cell = self.purchase_lines_table.item(row, 0)
        if name_cell is None:
            return

        item_id = int(name_cell.data(Qt.UserRole))
        target = next((line for line in self.purchase_cart if int(line["item_id"]) == item_id), None)
        if target is None:
            return

        try:
            value = float(item.text().strip())
            if column == 1 and value <= 0:
                raise ValueError("Quantity must be greater than zero.")
            if column == 2 and value <= 0:
                raise ValueError("Cost must be greater than zero.")
        except ValueError as exc:
            QMessageBox.warning(self, "Purchase Line", str(exc))
            self.refresh_purchase_lines_table()
            return

        if column == 1:
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
        items = self.inventory_service.list_items()
        self.billing_items_cache = [i for i in items if (i.get("item_kind") or "sellable") == "sellable"]
        self.current_category_filter = getattr(self, 'current_category_filter', None)
        self._petpooja_render_categories_and_grid(self.current_category_filter)
        self._refresh_billing_low_ingredient_alerts()
        self._refresh_cost_preview_panel()
        self._update_billing_dashboard_metrics()

    def _petpooja_render_categories_and_grid(self, filter_category_id: int | None = None) -> None:
        self.billing_controller.render_categories_and_grid(filter_category_id)
        return

        if not hasattr(self, "billing_category_tabs_layout"):
            return
            
        self.current_category_filter = filter_category_id
        
        # Only show categories that have at least one sellable item in our cache
        sellable_cat_ids = {i.get("category_id") for i in self.billing_items_cache if i.get("category_id")}
        categories = [c for c in self.inventory_service.list_categories() if c["id"] in sellable_cat_ids]
        
        while self.billing_category_tabs_layout.count():
            child = self.billing_category_tabs_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        all_btn = QPushButton("All Items")
        all_btn.setObjectName("CategoryTab")
        all_btn.setCheckable(True)
        all_btn.setChecked(filter_category_id is None)
        all_btn.clicked.connect(lambda: self._petpooja_render_categories_and_grid(None))
        self.billing_category_tabs_layout.addWidget(all_btn)
        
        for c in categories:
            btn = QPushButton(c["name"])
            btn.setObjectName("CategoryTab")
            btn.setCheckable(True)
            btn.setChecked(filter_category_id == c["id"])
            btn.clicked.connect(lambda _, cid=c["id"]: self._petpooja_render_categories_and_grid(cid))
            self.billing_category_tabs_layout.addWidget(btn)
            
        self.billing_category_tabs_layout.addStretch()

        while self.billing_quick_grid_layout.count():
            child = self.billing_quick_grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        query = ""
        if hasattr(self, "search_input"):
            query = self.search_input.text().strip().lower()

        filtered = self.billing_items_cache
        if filter_category_id is not None:
            filtered = [i for i in filtered if i.get("category_id") == filter_category_id]
        if query:
            filtered = [i for i in filtered if query in i["name"].lower()]

        if not filtered:
            self.billing_empty_state_label.setText("No items match. Try searching something else.")
            self.billing_empty_state_label.setVisible(True)
        else:
            self.billing_empty_state_label.setVisible(False)
            width = max(self.width(), 1000)
            cols = 5 if width >= 1600 else 4 if width >= 1280 else 3 if width >= 1020 else 2
            row, col = 0, 0
            for item in filtered:
                btn = QPushButton(f"{item['name']}\n₹{item['selling_price']:.0f}")
                btn.setObjectName("QuickAddItem")
                btn.setMinimumHeight(82)
                btn.setMinimumWidth(112)
                tint = self._category_tint(item.get("category_id"))
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {tint['bg']};
                        border: 1.5px solid {tint['border']};
                        border-radius: 14px;
                        color: {self.THEME['text_primary']};
                        font-weight: 800;
                        font-size: 12px;
                        padding: 6px;
                    }}
                    QPushButton:hover {{
                        background-color: {tint['border']};
                        color: white;
                    }}
                """)
                btn.clicked.connect(lambda _, iid=item["id"]: self._handle_quick_add(iid))
                self.billing_quick_grid_layout.addWidget(btn, row, col)
                col += 1
                if col >= cols:
                    col = 0
                    row += 1

    def _handle_quick_add(self, item_id: int) -> None:
        self.add_item_to_cart_by_id(item_id, quantity=1.0)

    def _category_tint(self, category_id: int | None) -> dict[str, str]:
        palette = [
            {"bg": "#fff7ed", "border": "#f59e0b", "hover": "#ffedd5"},
            {"bg": "#eff6ff", "border": "#3b82f6", "hover": "#dbeafe"},
            {"bg": "#ecfdf5", "border": "#10b981", "hover": "#d1fae5"},
            {"bg": "#fff1f2", "border": "#f43f5e", "hover": "#ffe4e6"},
            {"bg": "#f8fafc", "border": "#64748b", "hover": "#e2e8f0"},
            {"bg": "#f0fdfa", "border": "#14b8a6", "hover": "#ccfbf1"},
        ]
        if category_id is None:
            return {
                "bg": self.THEME["bg_surface"],
                "border": self.THEME["border_bold"],
                "hover": self.THEME["bg_surface_light"],
            }
        return palette[int(category_id) % len(palette)]

    def apply_billing_filter(self) -> None:
        self._petpooja_render_categories_and_grid(getattr(self, 'current_category_filter', None))

    def _update_billing_dashboard_metrics(self, total_amount: float | None = None) -> None:
        self.billing_controller.update_metrics(total_amount)
        return

        if not hasattr(self, "billing_cart_lines_value"):
            return

        cart_lines = len(self.cart)
        cart_qty = sum(float(item.get("quantity", 0)) for item in self.cart.values())

        self.billing_cart_lines_value.setText(str(cart_lines))
        self.billing_cart_qty_value.setText(f"{cart_qty:.2f}")

        if total_amount is None:
            total_text = self.total_label.text().replace("TOTAL: INR ", "").strip()
            try:
                total_amount = float(total_text)
            except ValueError:
                total_amount = 0.0
        self.billing_total_value.setText(f"INR {total_amount:.2f}")
        self.total_label.setText(f"TOTAL: INR {total_amount:.2f}")

    def _refresh_billing_low_ingredient_alerts(self) -> None:
        if not hasattr(self, "billing_low_ingredients_list"):
            return
        low_ingredients = self.inventory_service.low_ingredient_items()
        self.billing_low_ingredients_list.clear()
        if not low_ingredients:
            self.billing_low_ingredients_list.addItem("All ingredient stock is healthy.")
            return
        for row in low_ingredients:
            self.billing_low_ingredients_list.addItem(
                f"{row['name']} | Stock {float(row['stock_quantity']):.2f} / Reorder {float(row['reorder_level']):.2f}"
            )

    def _refresh_cost_preview_panel(self) -> None:
        if not hasattr(self, "cost_preview_table"):
            return

        cart_items = [
            {"item_id": item["item_id"], "quantity": item["quantity"]}
            for item in self.cart.values()
        ]
        if not cart_items:
            self.cost_preview_table.setRowCount(0)
            self.cost_preview_label.setText("Estimated COGS: INR 0.00 | Estimated Margin: INR 0.00")
            return

        preview = self.sales_service.preview_cart_costing(cart_items)
        rows = preview.get("rows", [])
        self.cost_preview_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            self.cost_preview_table.setItem(row_index, 0, QTableWidgetItem(str(row.get("name") or "")))
            qty_item = QTableWidgetItem(f"{float(row.get('quantity') or 0):.2f}")
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.cost_preview_table.setItem(row_index, 1, qty_item)
            unit_cost_item = QTableWidgetItem(f"{float(row.get('est_unit_cost') or 0):.2f}")
            unit_cost_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.cost_preview_table.setItem(row_index, 2, unit_cost_item)
            line_cost_item = QTableWidgetItem(f"{float(row.get('est_line_cost') or 0):.2f}")
            line_cost_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.cost_preview_table.setItem(row_index, 3, line_cost_item)
            margin_item = QTableWidgetItem(f"{float(row.get('est_margin') or 0):.2f}")
            margin_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.cost_preview_table.setItem(row_index, 4, margin_item)

        warnings = preview.get("warnings", [])
        warning_suffix = f" | Warnings: {len(warnings)}" if warnings else ""
        self.cost_preview_label.setText(
            f"Estimated COGS: INR {float(preview.get('total_est_cost') or 0):.2f} | "
            f"Estimated Margin: INR {float(preview.get('est_margin') or 0):.2f}"
            f"{warning_suffix}"
        )

    def _on_item_kind_changed(self) -> None:
        kind = self.item_kind_combo.currentData() if hasattr(self, "item_kind_combo") else "sellable"
        if kind == "ingredient":
            self.costing_mode_combo.setCurrentIndex(self.costing_mode_combo.findData("manual"))
            self.costing_mode_combo.setEnabled(False)
            self.stock_tracked_checkbox.setChecked(True)
            self.stock_tracked_checkbox.setEnabled(False)
        else:
            self.costing_mode_combo.setEnabled(True)
            self.stock_tracked_checkbox.setEnabled(True)

    def add_inventory_item(self) -> None:
        try:
            self.inventory_service.add_item(
                name=self.item_name_input.text(),
                category_id=self.category_combo.currentData(),
                selling_price=float(self.sell_price_spin.value()),
                cost_price=float(self.cost_price_spin.value()),
                stock_quantity=float(self.stock_spin.value()),
                reorder_level=float(self.reorder_spin.value()),
                item_kind=str(self.item_kind_combo.currentData() or "sellable"),
                costing_mode=str(self.costing_mode_combo.currentData() or "manual"),
                unit_name=self.unit_name_input.text().strip() or "pcs",
                is_stock_tracked=self.stock_tracked_checkbox.isChecked(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Validation Error", str(exc))
            return

        self.item_name_input.clear()
        self.sell_price_spin.setValue(0)
        self.cost_price_spin.setValue(0)
        self.stock_spin.setValue(0)
        self.reorder_spin.setValue(0)
        self.item_kind_combo.setCurrentIndex(self.item_kind_combo.findData("sellable"))
        self.costing_mode_combo.setCurrentIndex(self.costing_mode_combo.findData("manual"))
        self.unit_name_input.setText("pcs")
        self.stock_tracked_checkbox.setChecked(True)
        self._on_item_kind_changed()
        self._sync_inventory_add_button_state()
        self._focus_inventory_name()
        self.refresh_inventory()
        self.refresh_billing_items()
        self.refresh_reports()
        if hasattr(self, "inventory_inline_status_label"):
            self.inventory_inline_status_label.setText("Item added successfully.")
            self.inventory_inline_status_label.setVisible(True)
            QTimer.singleShot(2200, lambda: self.inventory_inline_status_label.setVisible(False))

    def _selected_inventory_item(self) -> dict | None:
        selected = self.inventory_items_table.currentRow()
        if selected < 0:
            QMessageBox.information(self, "Select Item", "Please select an item from inventory.")
            return None

        item_id = self._inventory_id_for_row(selected)
        if item_id is None:
            QMessageBox.warning(self, "Select Item", "Could not resolve selected inventory item.")
            return None

        return {
            "item_id": item_id,
            "name": self.inventory_items_table.item(selected, 0).text(),
            "selling_price": float(self.inventory_items_table.item(selected, 4).text()),
        }

    def _log_audit(
        self,
        action_type: str,
        entity_type: str = "",
        entity_id: str = "",
        details: str = "",
    ) -> None:
        self.ops_controller.log_audit(action_type, entity_type, entity_id, details)

    def _ask_admin_pin(self) -> str | None:
        return self.ops_controller.ask_admin_pin()

    def _require_admin_access(self, action_name: str) -> str | None:
        return self.ops_controller.require_admin_access(action_name)

    def on_role_changed(self, role_name: str) -> None:
        self.ops_controller.on_role_changed(role_name)

    def _apply_role_permissions(self) -> None:
        self.ops_controller.apply_role_permissions()

    def _configure_auto_backup_timer(self) -> None:
        self.ops_controller.configure_auto_backup_timer()

    def save_backup_preferences(self) -> None:
        self.ops_controller.save_backup_preferences()

    def _run_scheduled_backup(self) -> None:
        self.ops_controller.run_scheduled_backup()

    def manage_license(self) -> None:
        self.ops_controller.manage_license()

    @staticmethod
    def _format_restore_preview(current_counts: dict, backup_counts: dict, backup_file: str) -> str:
        return MainWindowOpsController.format_restore_preview(current_counts, backup_counts, backup_file)

    def export_reports_xlsx(self) -> None:
        self.ops_controller.export_reports_xlsx()

    def export_printable_summary(self) -> None:
        self.ops_controller.export_printable_summary()

    def export_audit_csv(self) -> None:
        self.ops_controller.export_audit_csv()

    def export_audit_xlsx(self) -> None:
        self.ops_controller.export_audit_xlsx()

    def manage_selected_item_recipe(self) -> None:
        item = self._selected_inventory_item()
        if item is None:
            return

        selected_full = next(
            (row for row in self.inventory_items_cache if int(row["id"]) == int(item["item_id"])),
            None,
        )
        if selected_full is None:
            QMessageBox.warning(self, "Recipe", "Selected item could not be resolved.")
            return
        if (selected_full.get("item_kind") or "sellable") != "sellable":
            QMessageBox.warning(self, "Recipe", "Recipes can be configured only for sellable items.")
            return

        pin = self._require_admin_access("Manage Recipe")
        if pin is None:
            return

        ingredients = self.inventory_service.list_ingredients()
        if not ingredients:
            QMessageBox.warning(self, "Recipe", "No ingredient items found. Create ingredients first.")
            return

        existing = self.inventory_service.get_recipe(int(item["item_id"]))

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Recipe - {item['name']}")
        dialog.resize(760, 460)
        layout = QVBoxLayout(dialog)

        header = QLabel("Define ingredient usage per recipe batch. Sale-time cost will be derived from these lines.")
        header.setWordWrap(True)
        layout.addWidget(header)

        meta_form = QFormLayout()
        yield_spin = QDoubleSpinBox()
        yield_spin.setDecimals(3)
        yield_spin.setMinimum(0.001)
        yield_spin.setMaximum(100000)
        yield_spin.setValue(float(existing.get("yield_qty", 1.0)) if existing else 1.0)
        meta_form.addRow("Recipe Yield Qty", yield_spin)
        layout.addLayout(meta_form)

        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Ingredient", "Qty Used", "Waste %"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layout.addWidget(table)

        def add_line(
            ingredient_item_id: int | None = None,
            quantity_used: float = 1.0,
            waste_percent: float = 0.0,
        ) -> None:
            row = table.rowCount()
            table.insertRow(row)

            ingredient_combo = QComboBox()
            for ing in ingredients:
                ingredient_combo.addItem(
                    f"{ing['name']} ({ing.get('unit_name') or 'unit'})",
                    int(ing["id"]),
                )
            if ingredient_item_id is not None:
                idx = ingredient_combo.findData(int(ingredient_item_id))
                if idx >= 0:
                    ingredient_combo.setCurrentIndex(idx)
            table.setCellWidget(row, 0, ingredient_combo)

            qty_spin = QDoubleSpinBox()
            qty_spin.setDecimals(4)
            qty_spin.setMinimum(0.0001)
            qty_spin.setMaximum(100000)
            qty_spin.setValue(float(quantity_used))
            table.setCellWidget(row, 1, qty_spin)

            waste_spin = QDoubleSpinBox()
            waste_spin.setDecimals(2)
            waste_spin.setMinimum(0)
            waste_spin.setMaximum(100)
            waste_spin.setValue(float(waste_percent))
            table.setCellWidget(row, 2, waste_spin)

        if existing and existing.get("lines"):
            for line in existing["lines"]:
                add_line(
                    ingredient_item_id=int(line["ingredient_item_id"]),
                    quantity_used=float(line["quantity_used"]),
                    waste_percent=float(line.get("waste_percent", 0.0)),
                )
        else:
            add_line()

        line_actions = QHBoxLayout()
        add_btn = QPushButton("Add Ingredient Line")
        remove_btn = QPushButton("Remove Selected Line")
        add_btn.clicked.connect(lambda: add_line())
        remove_btn.clicked.connect(
            lambda: table.removeRow(table.currentRow()) if table.currentRow() >= 0 else None
        )
        line_actions.addWidget(add_btn)
        line_actions.addWidget(remove_btn)
        line_actions.addStretch()
        layout.addLayout(line_actions)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return

        lines: list[dict] = []
        for row in range(table.rowCount()):
            ingredient_combo = table.cellWidget(row, 0)
            qty_spin = table.cellWidget(row, 1)
            waste_spin = table.cellWidget(row, 2)
            if not isinstance(ingredient_combo, QComboBox):
                continue
            if not isinstance(qty_spin, QDoubleSpinBox):
                continue
            if not isinstance(waste_spin, QDoubleSpinBox):
                continue
            lines.append(
                {
                    "ingredient_item_id": int(ingredient_combo.currentData()),
                    "quantity_used": float(qty_spin.value()),
                    "waste_percent": float(waste_spin.value()),
                }
            )

        if not lines:
            QMessageBox.warning(self, "Recipe", "Recipe must include at least one ingredient line.")
            return

        try:
            self.inventory_service.save_recipe(
                sellable_item_id=int(item["item_id"]),
                lines=lines,
                yield_qty=float(yield_spin.value()),
                admin_pin=pin,
            )
            self.inventory_service.set_item_classification(
                item_id=int(item["item_id"]),
                item_kind="sellable",
                costing_mode="recipe",
                is_stock_tracked=bool(int(selected_full.get("is_stock_tracked", 1))),
                unit_name=(selected_full.get("unit_name") or "pcs"),
                admin_pin=pin,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Recipe", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Recipe Error", str(exc))
            return

        QMessageBox.information(self, "Recipe", "Recipe saved successfully.")
        self.refresh_inventory()
        self.refresh_billing_items()
        self.refresh_reports()
        self._log_audit("recipe_save", "item", str(item["item_id"]), f"lines={len(lines)}")

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

        cached = next(
            (i for i in self.inventory_items_cache if int(i["id"]) == int(item["item_id"])),
            None,
        )
        current_cost = float(cached["cost_price"]) if cached else 0.0

        new_cost, ok_cost = QInputDialog.getDouble(
            self,
            "Update Cost Price",
            f"New cost price for {item['name']}",
            value=current_cost,
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

    def record_selected_item_waste(self) -> None:
        item = self._selected_inventory_item()
        if item is None:
            return

        pin = self._require_admin_access("Record Waste")
        if pin is None:
            return

        quantity, ok_qty = QInputDialog.getDouble(
            self,
            "Record Waste",
            "Waste quantity:",
            value=1.0,
            minValue=0.01,
            decimals=2,
        )
        if not ok_qty:
            return

        notes, ok_notes = QInputDialog.getText(self, "Waste Reason", "Reason for waste:")
        if not ok_notes:
            return

        try:
            self.inventory_service.record_waste(
                item_id=item["item_id"],
                quantity=float(quantity),
                admin_pin=pin,
                notes=notes,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Record Waste", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Record Waste", str(exc))
            return

        self.refresh_inventory()
        self.refresh_billing_items()
        self.refresh_reports()
        self._log_audit("waste_record", "item", str(item["item_id"]), f"qty={float(quantity):.2f}, notes={notes}")

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

    def add_item_to_cart_by_id(self, item_id: int, quantity: float = 1.0) -> None:
        self.billing_controller.add_item_to_cart_by_id(item_id, quantity)
        return

        item = next((i for i in self.billing_items_cache if int(i["id"]) == int(item_id)), None)
        if item is None:
            QMessageBox.warning(self, "Item Missing", "Selected item is no longer available.")
            return

        qty = float(quantity)
        existing_qty = float(self.cart.get(item_id, {}).get("quantity", 0))
        stock_tracked = int(item.get("is_stock_tracked", 1)) == 1
        recipe_costed = (item.get("costing_mode") or "manual") == "recipe"
        if stock_tracked and not recipe_costed:
            available_stock = float(item["stock_quantity"])
            if qty + existing_qty > available_stock:
                self.show_toast(f"Insufficient Stock ({available_stock:.0f} max)", is_error=True)
                return

        self.cart[item_id] = {
            "item_id": item_id,
            "name": item["name"],
            "quantity": qty + existing_qty,
            "unit_price": float(item["selling_price"]),
        }
        self.refresh_cart_table()
        QApplication.beep()

    def _selected_cart_item_id(self) -> int | None:
        selected = self.cart_table.currentRow()
        if selected < 0:
            self.show_toast("Select an item in the cart first", is_error=True)
            return None

        cell = self.cart_table.item(selected, 0)
        return int(cell.data(Qt.UserRole)) if cell else None

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

        self.add_item_to_cart_by_id(item_id, quantity=1.0)

    def decrease_selected_cart_item_qty(self) -> None:
        item_id = self._selected_cart_item_id()
        if item_id is None:
            return

        current_qty = self.cart[item_id]["quantity"]
        if current_qty > 1:
            self.cart[item_id]["quantity"] = current_qty - 1
        else:
            self.cart.pop(item_id)
        self.refresh_cart_table()

    def refresh_cart_table(self) -> None:
        self.billing_controller.refresh_cart_table()
        return

        items = list(self.cart.values())
        self.cart_table.setRowCount(len(items))

        total = 0.0
        for row_index, item in enumerate(items):
            line_total = item["quantity"] * item["unit_price"]
            total += line_total

            name_item = QTableWidgetItem(item["name"])
            name_item.setData(Qt.UserRole, int(item["item_id"]))
            self.cart_table.setItem(row_index, 0, name_item)
            self.cart_table.setItem(row_index, 1, QTableWidgetItem(f"{item['quantity']:.2f}"))
            self.cart_table.setItem(row_index, 2, QTableWidgetItem(f"{item['unit_price']:.2f}"))
            self.cart_table.setItem(row_index, 3, QTableWidgetItem(f"{line_total:.2f}"))

        if hasattr(self, "_refresh_cost_preview_panel"):
            self._refresh_cost_preview_panel()
        self._update_billing_dashboard_metrics(total_amount=total)

    def clear_cart(self) -> None:
        self.cart.clear()
        self.refresh_cart_table()
        if self.cart_file.exists():
            self.cart_file.unlink(missing_ok=True)

    def _trigger_petpooja_checkout(self, method: str) -> None:
        idx = self.payment_method_combo.findData(method)
        if idx >= 0:
            self.payment_method_combo.setCurrentIndex(idx)
        self.checkout()

    def checkout(self) -> None:
        if not self.cart:
            self.show_toast("Cart is empty!", is_error=True)
            return

        cart_items = [
            {"item_id": item["item_id"], "quantity": item["quantity"]}
            for item in self.cart.values()
        ]

        payment_method = str(self.payment_method_combo.currentData() or "cash")
        customer_name = self.customer_name_input.text().strip()
        customer_phone = self.customer_phone_input.text().strip()

        try:
            sale_result = self.sales_service.checkout(
                cart_items,
                payment_method=payment_method,
                customer_name=customer_name,
                customer_phone=customer_phone,
            )
            sale = self.sales_service.sale_details(int(sale_result["sale_id"]))
            self.show_toast("Bill Generated! Checkout Successful \u2705")
        except ValueError as exc:
            self.show_toast(str(exc), is_error=True)
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
        self.customer_name_input.clear()
        self.customer_phone_input.clear()
        cash_index = self.payment_method_combo.findData("cash")
        self.payment_method_combo.setCurrentIndex(cash_index if cash_index >= 0 else 0)
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
        self.sales_value.setText(self.reports_controller.money(summary["sales"]))
        self.cogs_value.setText(self.reports_controller.money(summary["cogs"]))
        self.gross_profit_value.setText(self.reports_controller.money(summary["gross_profit"]))
        self.purchases_value.setText(self.reports_controller.money(summary["purchases"]))
        self.expenses_value.setText(self.reports_controller.money(summary["expenses"]))
        self.fixed_daily_value.setText(self.reports_controller.money(summary["selected_fixed_overhead"]))
        self.net_value.setText(self.reports_controller.money(summary["net_profit"]))
        self.reports_controller.apply_profit_state(self.gross_profit_value, summary["gross_profit"])
        self.reports_controller.apply_profit_state(self.net_value, summary["net_profit"])

        fixed = summary.get("fixed_costs", {})
        self.rent_spin.setValue(float(fixed.get("rent", 0)))
        self.salary_spin.setValue(float(fixed.get("salary", 0)))
        self.maintenance_spin.setValue(float(fixed.get("maintenance", 0)))
        self.electricity_spin.setValue(float(fixed.get("electricity", 0)))
        self.monthly_fixed_total_label.setText(
            f"Monthly Fixed Total: INR {summary['monthly_fixed_total']:.2f}"
        )

        if hasattr(self, "overhead_date_edit"):
            overhead_date = self.overhead_date_edit.date().toString("yyyy-MM-dd")
            overhead = self.report_service.daily_overhead(overhead_date)
            self.overhead_gas_spin.setValue(float(overhead.get("gas_cost", 0)))
            self.overhead_labor_spin.setValue(float(overhead.get("labor_cost", 0)))
            self.overhead_misc_spin.setValue(float(overhead.get("misc_cost", 0)))
            self.overhead_units_spin.setValue(float(overhead.get("expected_units", 0)))
            total_overhead = (
                float(overhead.get("gas_cost", 0))
                + float(overhead.get("labor_cost", 0))
                + float(overhead.get("misc_cost", 0))
            )
            expected_units = float(overhead.get("expected_units", 0))
            per_unit = total_overhead / expected_units if expected_units > 0 else 0.0
            self.overhead_per_unit_label.setText(f"Overhead / Unit: INR {per_unit:.2f}")

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

        if hasattr(self, "payment_breakdown_table"):
            payment_rows = self.report_service.payment_breakdown_between(start_date=start_date, end_date=end_date)
            self.payment_breakdown_table.setRowCount(len(payment_rows))
            for row_index, row in enumerate(payment_rows):
                self.payment_breakdown_table.setItem(
                    row_index,
                    0,
                    self._report_item(str(row.get("payment_method") or "cash").upper()),
                )
                self.payment_breakdown_table.setItem(
                    row_index,
                    1,
                    self._report_item(str(int(row.get("bill_count") or 0)), True),
                )
                self.payment_breakdown_table.setItem(
                    row_index,
                    2,
                    self._report_item(f"{float(row.get('amount_total') or 0):.2f}", True),
                )

        if hasattr(self, "recent_sales_table"):
            sales_limit = int(self.recent_sales_limit_spin.value()) if hasattr(self, "recent_sales_limit_spin") else 80
            recent_sales = self.report_service.recent_sales_between(
                start_date=start_date,
                end_date=end_date,
                limit=sales_limit,
            )
            self.recent_sales_table.setRowCount(len(recent_sales))
            for row_index, row in enumerate(recent_sales):
                self.recent_sales_table.setItem(row_index, 0, self._report_item(str(row.get("invoice_number") or "")))
                self.recent_sales_table.setItem(row_index, 1, self._report_item(str(row.get("sold_at") or "")))
                self.recent_sales_table.setItem(
                    row_index,
                    2,
                    self._report_item(str(row.get("payment_method") or "cash").upper()),
                )
                self.recent_sales_table.setItem(row_index, 3, self._report_item(str(row.get("customer_name") or "-")))
                self.recent_sales_table.setItem(row_index, 4, self._report_item(str(row.get("customer_phone") or "-")))
                self.recent_sales_table.setItem(
                    row_index,
                    5,
                    self._report_item(f"{float(row.get('total_amount') or 0):.2f}", True),
                )

        if hasattr(self, "waste_summary_label"):
            waste = self.report_service.waste_summary_between(start_date=start_date, end_date=end_date)
            self.waste_summary_label.setText(
                f"Waste in range: Qty {self._f(waste.get('waste_qty')):.2f} | "
                f"Estimated Cost INR {self._f(waste.get('waste_cost')):.2f}"
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

        if hasattr(self, "costing_exceptions_table"):
            exceptions = self.report_service.costing_exceptions(limit=400)
            self.costing_exceptions_table.setRowCount(len(exceptions))
            for row_index, ex in enumerate(exceptions):
                self.costing_exceptions_table.setItem(row_index, 0, self._report_item(ex.get("created_at", "")))
                self.costing_exceptions_table.setItem(row_index, 1, self._report_item(ex.get("exception_type", "")))
                self.costing_exceptions_table.setItem(
                    row_index,
                    2,
                    self._report_item(ex.get("item_name") or "-"),
                )
                self.costing_exceptions_table.setItem(
                    row_index,
                    3,
                    self._report_item(str(ex.get("sale_id")) if ex.get("sale_id") else "-"),
                )
                self.costing_exceptions_table.setItem(
                    row_index,
                    4,
                    self._report_item(str(ex.get("item_id")) if ex.get("item_id") else "-"),
                )
                self.costing_exceptions_table.setItem(row_index, 5, self._report_item(ex.get("details", "")))

    def close_day(self) -> None:
        self.ops_controller.close_day()

    def backup_now(self) -> None:
        self.ops_controller.backup_now()

    def export_backup_dialog(self) -> None:
        self.ops_controller.export_backup_dialog()

    def restore_backup_dialog(self) -> None:
        self.ops_controller.restore_backup_dialog()

    def _save_pending_cart(self) -> None:
        self.ops_controller.save_pending_cart()

    def _load_pending_cart(self) -> None:
        self.ops_controller.load_pending_cart()
