from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


def build_inventory_tab(w) -> QWidget:
    tab = QWidget()
    tab.setObjectName("InventoryTabRoot")
    root_layout = QVBoxLayout(tab)
    root_layout.setContentsMargins(0, 0, 0, 0)

    main_scroll = QScrollArea()
    main_scroll.setWidgetResizable(True)
    main_scroll.setFrameShape(QFrame.NoFrame)

    main_content = QWidget()
    main_content.setObjectName("InventoryPanel")
    content_layout = QVBoxLayout(main_content)
    content_layout.setContentsMargins(15, 15, 15, 15)
    content_layout.setSpacing(15)

    content_layout.addWidget(_build_inventory_form(w))
    content_layout.addWidget(_build_inventory_hint())
    content_layout.addWidget(_build_inventory_filter_bar(w))
    content_layout.addLayout(_build_inventory_summary_row(w))

    w.inventory_low_stock_banner = QLabel("")
    w.inventory_low_stock_banner.setObjectName("DangerAction")
    w.inventory_low_stock_banner.setAlignment(Qt.AlignCenter)
    w.inventory_low_stock_banner.setStyleSheet(
        "font-weight: bold; font-size: 14px; padding: 10px; border-radius: 8px;"
    )
    w.inventory_low_stock_banner.setVisible(False)
    content_layout.addWidget(w.inventory_low_stock_banner)

    table_panel = QFrame()
    table_panel.setObjectName("InventoryTablePanel")
    table_panel_layout = QVBoxLayout(table_panel)
    table_panel_layout.setContentsMargins(0, 0, 0, 0)
    table_panel_layout.setSpacing(0)
    table_panel_layout.addWidget(_build_inventory_table(w), 1)
    content_layout.addWidget(table_panel, 1)

    w.inventory_empty_state_label = QLabel("No items found. Click '+ Add Item' to get started.")
    w.inventory_empty_state_label.setObjectName("InventoryEmptyState")
    w.inventory_empty_state_label.setVisible(False)
    content_layout.addWidget(w.inventory_empty_state_label)

    w.inventory_inline_status_label = QLabel("")
    w.inventory_inline_status_label.setObjectName("InventoryInlineStatus")
    w.inventory_inline_status_label.setVisible(False)
    content_layout.addWidget(w.inventory_inline_status_label)

    content_layout.addLayout(_build_inventory_action_row(w))

    main_scroll.setWidget(main_content)
    root_layout.addWidget(main_scroll)

    w.item_name_input.textChanged.connect(w._sync_inventory_add_button_state)
    w.sell_price_spin.valueChanged.connect(w._sync_inventory_add_button_state)
    w.stock_spin.valueChanged.connect(w._sync_inventory_add_button_state)
    w.reorder_spin.valueChanged.connect(w._sync_inventory_add_button_state)
    w.category_combo.currentIndexChanged.connect(w._sync_inventory_add_button_state)
    w.item_kind_combo.currentIndexChanged.connect(w._on_item_kind_changed)
    w._on_item_kind_changed()
    w._sync_inventory_add_button_state()
    apply_inventory_panel_style(w, tab)

    return tab


def _build_inventory_form(w) -> QGroupBox:
    form_group = QGroupBox("Add Item")
    form_layout = QGridLayout(form_group)
    form_layout.setHorizontalSpacing(10)
    form_layout.setVerticalSpacing(8)

    basic_group = QGroupBox("Basic Info")
    basic_layout = QGridLayout(basic_group)

    pricing_group = QGroupBox("Pricing")
    pricing_layout = QGridLayout(pricing_group)

    stock_group = QGroupBox("Stock")
    stock_layout = QGridLayout(stock_group)

    w.item_name_input = QLineEdit()
    w.item_name_input.setPlaceholderText("Item name")
    w.item_name_input.returnPressed.connect(w.add_inventory_item)

    w.category_combo = QComboBox()

    w.item_kind_combo = QComboBox()
    w.item_kind_combo.addItem("Sellable", "sellable")
    w.item_kind_combo.addItem("Ingredient", "ingredient")

    w.costing_mode_combo = QComboBox()
    w.costing_mode_combo.addItem("Manual Cost", "manual")
    w.costing_mode_combo.addItem("Recipe Cost", "recipe")

    w.unit_name_input = QLineEdit("pcs")
    w.unit_name_input.setPlaceholderText("Unit (pcs, g, ml, etc.)")

    w.stock_tracked_checkbox = QCheckBox("Track stock")
    w.stock_tracked_checkbox.setChecked(True)

    w.sell_price_spin = QDoubleSpinBox()
    w.sell_price_spin.setMaximum(100000)
    w.sell_price_spin.setPrefix("INR ")

    w.cost_price_spin = QDoubleSpinBox()
    w.cost_price_spin.setMaximum(100000)
    w.cost_price_spin.setPrefix("INR ")

    w.stock_spin = QDoubleSpinBox()
    w.stock_spin.setMaximum(100000)

    w.reorder_spin = QDoubleSpinBox()
    w.reorder_spin.setMaximum(100000)

    w.inventory_add_btn = QPushButton("+ Add Item")
    w.inventory_add_btn.setObjectName("PrimaryInventoryButton")
    w.inventory_add_btn.setMinimumHeight(40)
    w.inventory_add_btn.setMinimumWidth(126)
    w.inventory_add_btn.clicked.connect(w.add_inventory_item)

    basic_layout.addWidget(QLabel("<b>Name</b>"), 0, 0)
    basic_layout.addWidget(w.item_name_input, 0, 1)
    basic_layout.addWidget(QLabel("<b>Category</b>"), 1, 0)
    basic_layout.addWidget(w.category_combo, 1, 1)
    basic_layout.addWidget(QLabel("<b>Kind</b>"), 2, 0)
    basic_layout.addWidget(w.item_kind_combo, 2, 1)
    basic_layout.addWidget(QLabel("<b>Unit</b>"), 3, 0)
    basic_layout.addWidget(w.unit_name_input, 3, 1)

    pricing_layout.addWidget(QLabel("<b>Selling Price</b>"), 0, 0)
    pricing_layout.addWidget(w.sell_price_spin, 0, 1)
    pricing_layout.addWidget(QLabel("<b>Cost Price</b>"), 1, 0)
    pricing_layout.addWidget(w.cost_price_spin, 1, 1)
    pricing_layout.addWidget(QLabel("<b>Costing</b>"), 2, 0)
    pricing_layout.addWidget(w.costing_mode_combo, 2, 1)
    pricing_layout.addWidget(w.stock_tracked_checkbox, 3, 1)

    stock_layout.addWidget(QLabel("<b>Opening Stock</b>"), 0, 0)
    stock_layout.addWidget(w.stock_spin, 0, 1)
    stock_layout.addWidget(QLabel("<b>Reorder Level</b>"), 1, 0)
    stock_layout.addWidget(w.reorder_spin, 1, 1)

    divider = QFrame()
    divider.setFrameShape(QFrame.HLine)
    divider.setFrameShadow(QFrame.Sunken)

    add_row = QHBoxLayout()
    add_row.setContentsMargins(0, 4, 0, 0)
    add_row.addStretch()
    add_row.addWidget(w.inventory_add_btn)

    form_layout.addWidget(basic_group, 0, 0)
    form_layout.addWidget(pricing_group, 0, 1)
    form_layout.addWidget(stock_group, 0, 2)
    form_layout.addWidget(divider, 1, 0, 1, 3)
    form_layout.addLayout(add_row, 2, 0, 1, 3)
    return form_group


def _build_inventory_hint() -> QLabel:
    inventory_hint = QLabel(
        "Tip: Double-click Sell/Reorder to edit inline. Red=out of stock, Yellow=below reorder."
    )
    inventory_hint.setObjectName("OpsHintLabel")
    return inventory_hint


def _build_inventory_filter_bar(w) -> QFrame:
    filter_box = QFrame()
    filter_box.setObjectName("OpsFilterBar")
    filter_box_layout = QHBoxLayout(filter_box)
    filter_box_layout.setContentsMargins(10, 8, 10, 8)
    filter_box_layout.setSpacing(8)

    filter_row = QHBoxLayout()
    filter_row.setContentsMargins(0, 0, 0, 0)
    filter_row.setSpacing(8)

    w.inventory_search_input = QLineEdit()
    w.inventory_search_input.setPlaceholderText("Search item (name, category)...")
    w.inventory_search_input.setClearButtonEnabled(True)
    w.inventory_search_input.setMinimumHeight(34)
    w.inventory_search_input.textChanged.connect(w.apply_inventory_filter)

    w.inventory_filter_category_combo = QComboBox()
    w.inventory_filter_category_combo.addItem("All Categories", None)
    w.inventory_filter_category_combo.setMinimumWidth(220)
    w.inventory_filter_category_combo.setMinimumHeight(34)
    w.inventory_filter_category_combo.currentIndexChanged.connect(w.apply_inventory_filter)

    w.inventory_low_stock_only_checkbox = QCheckBox("Low Stock Only")
    w.inventory_low_stock_only_checkbox.toggled.connect(w.apply_inventory_filter)

    filter_row.addWidget(w.inventory_search_input, 2)
    filter_row.addWidget(QLabel("<b>Category</b>"))
    filter_row.addWidget(w.inventory_filter_category_combo, 1)
    filter_row.addWidget(w.inventory_low_stock_only_checkbox)
    filter_box_layout.addLayout(filter_row)
    return filter_box


def _build_inventory_summary_row(w) -> QHBoxLayout:
    summary_row = QHBoxLayout()
    w.inventory_summary_total = QLabel("Total Items: 0")
    w.inventory_summary_total.setObjectName("InventorySummaryCard")
    w.inventory_summary_low = QLabel("Low Stock: 0")
    w.inventory_summary_low.setObjectName("InventorySummaryLow")
    w.inventory_summary_oos = QLabel("Out of Stock: 0")
    w.inventory_summary_oos.setObjectName("InventorySummaryOOS")
    w.inventory_summary_reorder = QLabel("Reorder Alerts: 0")
    w.inventory_summary_reorder.setObjectName("InventorySummaryReorder")
    summary_row.addWidget(w.inventory_summary_total)
    summary_row.addWidget(w.inventory_summary_low)
    summary_row.addWidget(w.inventory_summary_oos)
    summary_row.addWidget(w.inventory_summary_reorder)
    summary_row.addStretch()
    return summary_row


def _build_inventory_table(w) -> QTableWidget:
    w.inventory_items_table = QTableWidget(0, 8)
    w.inventory_items_table.setHorizontalHeaderLabels(
        ["Name", "Category", "Kind", "Costing", "Sell", "Stock", "Reorder", "Actions"]
    )
    w.inventory_items_table.setEditTriggers(
        QTableWidget.DoubleClicked | QTableWidget.SelectedClicked | QTableWidget.EditKeyPressed
    )
    w.inventory_items_table.setSelectionBehavior(QTableWidget.SelectRows)
    w.inventory_items_table.itemChanged.connect(w._on_inventory_item_changed)
    w.inventory_items_table.itemDoubleClicked.connect(w._on_inventory_edit_started)
    w.inventory_items_table.setSortingEnabled(True)
    w.inventory_items_table.horizontalHeader().setStretchLastSection(False)
    w.inventory_items_table.horizontalHeader().setMinimumSectionSize(90)
    w.inventory_items_table.verticalHeader().setDefaultSectionSize(44)
    w.inventory_items_table.setAlternatingRowColors(True)
    w.inventory_items_table.setMinimumHeight(340)
    w.inventory_items_table.setVerticalScrollMode(QTableWidget.ScrollPerPixel)
    w.inventory_items_table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
    w.inventory_items_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    w.inventory_items_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    header = w.inventory_items_table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.Stretch)
    header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(7, QHeaderView.Interactive)
    w.inventory_items_table.setColumnWidth(7, 250)
    w.inventory_items_table.horizontalHeaderItem(4).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    w.inventory_items_table.horizontalHeaderItem(5).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    w.inventory_items_table.horizontalHeaderItem(6).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return w.inventory_items_table


def _build_inventory_action_row(w) -> QHBoxLayout:
    action_row = QHBoxLayout()

    refresh_btn = QPushButton("Refresh Inventory")
    refresh_btn.setObjectName("PrimaryInventoryButton")
    refresh_btn.clicked.connect(w.refresh_inventory)

    actions_menu_btn = QToolButton()
    actions_menu_btn.setObjectName("PrimaryInventoryButton")
    actions_menu_btn.setText("Inventory Actions")
    actions_menu_btn.setMinimumHeight(36)
    actions_menu_btn.setMinimumWidth(150)
    actions_menu_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
    actions_menu_btn.setPopupMode(QToolButton.InstantPopup)
    actions_menu = QMenu(actions_menu_btn)
    actions_menu.addAction("Export CSV", w.export_inventory_csv)
    actions_menu.addAction("Update Price (Admin PIN)", w.update_selected_item_price)
    actions_menu.addAction("Manual Stock Adjust (Admin PIN)", w.adjust_selected_item_stock)
    actions_menu.addAction("Record Waste (Admin PIN)", w.record_selected_item_waste)
    actions_menu.addAction("Manage Recipe (Admin PIN)", w.manage_selected_item_recipe)
    actions_menu.addAction("Delete Item (Admin PIN)", w.delete_selected_item)
    actions_menu.addAction("Load Starter Cigarette SKUs", w.load_starter_cigarettes)
    actions_menu_btn.setMenu(actions_menu)

    action_row.addWidget(refresh_btn)
    action_row.addWidget(actions_menu_btn)
    action_row.addStretch()
    return action_row


def apply_inventory_panel_style(w, tab: QWidget) -> None:
    T = w.THEME
    tab.setStyleSheet(f"""
        #InventoryPanel {{
            background-color: {T['bg_deep']};
        }}
        #InventoryPanel QGroupBox {{
            border: 1.5px solid {T['border_bold']};
            border-radius: 12px;
            background-color: {T['bg_surface']};
            margin-top: 15px;
            padding-top: 15px;
        }}
        #InventorySummaryCard, #InventorySummaryLow, #InventorySummaryOOS {{
            border: 1.5px solid {T['border_bold']};
            border-radius: 10px;
            background-color: {T['bg_surface']};
            padding: 10px;
            font-weight: 800;
        }}
        #InventorySummaryReorder {{
            border: 1.5px solid {T['accent_primary']};
            border-radius: 10px;
            background-color: #eff6ff;
            padding: 10px;
            font-weight: 800;
            color: {T['accent_primary']};
        }}
        #InventorySummaryLow {{
            border-color: {T['accent_gold']};
            background-color: #fff9eb;
            color: {T['accent_gold']};
        }}
        #InventorySummaryOOS {{
            border-color: {T['danger']};
            background-color: #fef2f2;
            color: {T['danger']};
        }}
        #InventoryEmptyState {{
            padding: 15px;
            border: 2px dashed {T['border_bold']};
            border-radius: 10px;
            color: {T['text_medium']};
            background-color: transparent;
            font-weight: 700;
        }}
    """)
