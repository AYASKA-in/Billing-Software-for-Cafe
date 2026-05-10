from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)


def build_billing_tab(w) -> QWidget:
    tab = QWidget()
    tab.setObjectName("BillingDashboard")
    root_layout = QVBoxLayout(tab)
    root_layout.setContentsMargins(10, 10, 10, 10)
    root_layout.setSpacing(8)

    hero_frame = QFrame()
    hero_frame.setObjectName("BillingHero")
    hero_layout = QHBoxLayout(hero_frame)
    hero_layout.setContentsMargins(12, 8, 12, 8)

    hero_title = QLabel("Billing Dashboard")
    hero_title.setObjectName("BillingHeroTitle")
    hero_layout.addWidget(hero_title)
    hero_layout.addStretch()

    stats_layout = QHBoxLayout()
    stats_layout.setSpacing(6)
    lines_card, w.billing_cart_lines_value = make_billing_stat_card(w, "LINES")
    qty_card, w.billing_cart_qty_value = make_billing_stat_card(w, "UNITS")
    total_card, w.billing_total_value = make_billing_stat_card(w, "BILL")
    stats_layout.addWidget(lines_card)
    stats_layout.addWidget(qty_card)
    stats_layout.addWidget(total_card)
    hero_layout.addLayout(stats_layout)
    hero_frame.setMaximumHeight(100)
    hero_frame.setMinimumHeight(80)

    splitter = QSplitter(Qt.Horizontal)
    splitter.setChildrenCollapsible(False)

    catalog_group = QWidget()
    catalog_group.setObjectName("BillingCatalogGroup")
    catalog_layout = QVBoxLayout(catalog_group)
    catalog_layout.setContentsMargins(10, 0, 10, 10)
    catalog_layout.setSpacing(12)

    w.search_input = QLineEdit()
    w.search_input.setPlaceholderText("Search items (Alt+F)...")
    w.search_input.setObjectName("BillingSearch")
    w.search_input.setMinimumHeight(40)
    w.search_input.textChanged.connect(w.apply_billing_filter)
    catalog_layout.addWidget(w.search_input)

    w.billing_category_tabs_layout = QHBoxLayout()
    w.billing_category_tabs_layout.setSpacing(10)
    w.billing_category_tabs_layout.setAlignment(Qt.AlignLeft)
    category_container = QWidget()
    category_container.setObjectName("BillingCategoryContainer")
    category_container.setLayout(w.billing_category_tabs_layout)

    category_scroll = QScrollArea()
    category_scroll.setWidgetResizable(True)
    category_scroll.setMaximumHeight(65)
    category_scroll.setFrameShape(QFrame.NoFrame)
    category_scroll.setWidget(category_container)
    category_scroll.setFixedHeight(65)
    catalog_layout.addWidget(category_scroll, 0)

    w.billing_quick_grid_layout = QGridLayout()
    w.billing_quick_grid_layout.setSpacing(14)
    w.billing_quick_grid_layout.setContentsMargins(16, 16, 16, 16)
    w.billing_quick_grid_layout.setAlignment(Qt.AlignTop)

    grid_container = QWidget()
    grid_container.setObjectName("BillingGridContainer")
    grid_container.setLayout(w.billing_quick_grid_layout)

    grid_scroll = QScrollArea()
    grid_scroll.setObjectName("BillingGridScroll")
    grid_scroll.setWidgetResizable(True)
    grid_scroll.setFrameShape(QFrame.NoFrame)
    grid_scroll.setWidget(grid_container)
    grid_scroll.setMinimumHeight(400)
    catalog_layout.addWidget(grid_scroll, 1)

    w.billing_empty_state_label = QLabel("")
    w.billing_empty_state_label.setObjectName("BillingEmptyState")
    w.billing_empty_state_label.setAlignment(Qt.AlignCenter)
    w.billing_empty_state_label.setVisible(False)

    cart_group = QWidget()
    cart_group.setObjectName("BillingCartGroup")
    cart_layout = QVBoxLayout(cart_group)
    cart_layout.setContentsMargins(10, 10, 10, 10)
    cart_layout.setSpacing(10)

    cart_header = QHBoxLayout()
    cart_title = QLabel("Current Bill")
    cart_title.setObjectName("BillingPanelTitle")
    w.cart_summary_label = QLabel("0 lines | 0.00 units")
    w.cart_summary_label.setObjectName("BillingPanelMeta")
    cart_header.addWidget(cart_title)
    cart_header.addStretch()
    cart_header.addWidget(w.cart_summary_label)

    w.cart_table = QTableWidget(0, 4)
    w.cart_table.setHorizontalHeaderLabels(["Item Name", "Qty", "Price", "Total"])
    w.cart_table.setSelectionBehavior(QTableWidget.SelectRows)
    w.cart_table.setEditTriggers(QTableWidget.NoEditTriggers)
    w.cart_table.horizontalHeader().setStretchLastSection(True)
    w.cart_table.verticalHeader().setDefaultSectionSize(48)
    style_billing_table(w.cart_table)

    w.cart_empty_label = QLabel("No items in bill")
    w.cart_empty_label.setObjectName("CartEmptyState")
    w.cart_empty_label.setAlignment(Qt.AlignCenter)

    cart_actions_row = QHBoxLayout()
    plus_qty_btn = QPushButton("+ Qty")
    plus_qty_btn.setObjectName("StandardAction")
    plus_qty_btn.clicked.connect(w.increase_selected_cart_item_qty)
    minus_qty_btn = QPushButton("- Qty")
    minus_qty_btn.setObjectName("StandardAction")
    minus_qty_btn.clicked.connect(w.decrease_selected_cart_item_qty)
    remove_selected_btn = QPushButton("Remove")
    remove_selected_btn.setObjectName("DangerAction")
    remove_selected_btn.clicked.connect(w.remove_selected_cart_item)
    clear_btn = QPushButton("Clear Cart")
    clear_btn.setObjectName("DangerAction")
    clear_btn.clicked.connect(w.clear_cart)

    cart_actions_row.addWidget(plus_qty_btn)
    cart_actions_row.addWidget(minus_qty_btn)
    cart_actions_row.addStretch()
    cart_actions_row.addWidget(remove_selected_btn)
    cart_actions_row.addWidget(clear_btn)

    total_panel = QFrame()
    total_panel.setObjectName("BillingTotalPanel")
    total_panel_layout = QVBoxLayout(total_panel)
    total_panel_layout.setContentsMargins(5, 5, 5, 5)
    total_panel_layout.setSpacing(12)

    w.total_label = QLabel("TOTAL: INR 0.00")
    w.total_label.setObjectName("BillingTotalLabel")
    w.total_label.setAlignment(Qt.AlignCenter)

    pay_row = QHBoxLayout()
    pay_row.setSpacing(10)
    for label, method in (("Pay CASH", "cash"), ("Pay UPI", "upi"), ("Pay CARD", "card")):
        btn = QPushButton(label)
        btn.setObjectName("PayAction")
        btn.setProperty("payment", method)
        btn.clicked.connect(lambda _, m=method: w._trigger_petpooja_checkout(m))
        pay_row.addWidget(btn)

    total_panel_layout.addWidget(w.total_label)
    total_panel_layout.addLayout(pay_row)

    w.customer_name_input = QLineEdit()
    w.customer_phone_input = QLineEdit()
    w.payment_method_combo = QComboBox()
    w.payment_method_combo.addItem("Cash", "cash")
    w.payment_method_combo.addItem("UPI", "upi")
    w.payment_method_combo.addItem("Card", "card")

    cart_layout.addLayout(cart_header)
    cart_layout.addWidget(w.cart_table, 1)
    cart_layout.addWidget(w.cart_empty_label)
    cart_layout.addLayout(cart_actions_row)
    cart_layout.addWidget(total_panel, 0)

    splitter.addWidget(catalog_group)
    splitter.addWidget(cart_group)
    splitter.setSizes([800, 400])
    splitter.setStretchFactor(0, 5)
    splitter.setStretchFactor(1, 4)

    root_layout.addWidget(hero_frame, 0)
    root_layout.addWidget(splitter, 1)
    w.billing_root_layout = root_layout
    w.billing_splitter = splitter
    apply_billing_dashboard_style(w, tab)
    w._set_billing_compact_mode(w.width() < 1180)
    w._update_billing_dashboard_metrics(total_amount=0.0)
    return tab


def make_billing_stat_card(w, heading: str) -> tuple[QFrame, QLabel]:
    card = QFrame()
    card.setObjectName("BillingStatCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(2)

    title = QLabel(heading)
    title.setObjectName("BillingStatTitle")
    value = QLabel("0")
    value.setObjectName("BillingStatValue")

    layout.addWidget(title)
    layout.addWidget(value)
    return card, value


def style_billing_table(table: QTableWidget) -> None:
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    table.setWordWrap(False)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    table.horizontalHeader().setMinimumSectionSize(72)
    table.horizontalHeader().setDefaultSectionSize(132)
    table.verticalHeader().setDefaultSectionSize(38)


def apply_billing_dashboard_style(w, tab: QWidget) -> None:
    T = w.THEME
    tab.setStyleSheet(f"""
        #BillingDashboard {{
            background-color: {T['bg_deep']};
        }}
        #BillingSearch {{
            background-color: {T['bg_surface']};
            border: 2px solid {T['border_bold']};
            border-radius: 12px;
            padding: 10px 15px;
            color: {T['text_primary']};
            font-size: 16px;
            font-weight: 600;
        }}
        #BillingSearch:focus {{
            border-color: {T['accent_primary']};
            background-color: {T['bg_surface_light']};
        }}
        #BillingHero {{
            border: 1px solid {T['border']};
            border-radius: 10px;
            background-color: {T['bg_surface']};
        }}
        #BillingHeroTitle {{
            font-size: 22px;
            font-weight: 800;
            color: {T['text_primary']};
        }}
        #BillingPanelTitle {{
            font-size: 16px;
            font-weight: 900;
            color: {T['text_primary']};
        }}
        #BillingPanelMeta {{
            color: {T['text_medium']};
            font-weight: 800;
            padding: 4px 8px;
            background-color: {T['bg_surface_light']};
            border-radius: 6px;
        }}
        #CartEmptyState {{
            color: {T['text_low']};
            background-color: {T['bg_surface_light']};
            border: 1px dashed {T['border']};
            border-radius: 8px;
            padding: 10px;
            font-weight: 800;
        }}
        #BillingEmptyState {{
            padding: 20px;
            border: 1px dashed {T['border_bold']};
            border-radius: 10px;
            color: {T['text_medium']};
            background-color: transparent;
            font-weight: 700;
        }}
        #BillingStatCard {{
            border: 1px solid {T['border']};
            border-radius: 8px;
            background-color: {T['bg_surface_light']};
            min-width: 100px;
        }}
        #BillingStatTitle {{
            font-size: 10px;
            font-weight: 900;
            text-transform: uppercase;
            color: {T['text_medium']};
            letter-spacing: 1px;
        }}
        #BillingStatValue {{
            font-size: 18px;
            font-weight: 900;
            color: {T['accent_primary']};
        }}
        #BillingTotalPanel {{
            background-color: {T['bg_surface']};
            border: 1px solid {T['border']};
            border-radius: 10px;
            padding: 12px;
        }}
        #BillingTotalLabel {{
            font-size: 34px;
            font-weight: 900;
            color: {T['accent_primary']};
        }}
        #BillingGridScroll {{
            background-color: {T['bg_surface_light']};
            border: 1px solid {T['border']};
            border-radius: 10px;
        }}
        #BillingGridContainer {{
            background-color: {T['bg_surface_light']};
            border-radius: 10px;
        }}
        #CartPanel, #BillingCartGroup {{
            background-color: {T['bg_surface']};
            border: 1px solid {T['border']};
            border-radius: 10px;
            padding: 8px;
        }}
        QPushButton#PayAction {{
            border-radius: 8px;
            min-height: 42px;
            color: white;
            font-size: 18px;
            font-weight: 900;
        }}
        QPushButton#PayAction[payment="cash"] {{
            background-color: {T['success']};
        }}
        QPushButton#PayAction[payment="upi"] {{
            background-color: #0f766e;
        }}
        QPushButton#PayAction[payment="card"] {{
            background-color: #2879b9;
        }}
    """)
