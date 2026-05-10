from __future__ import annotations


def premium_pos_stylesheet(theme: dict[str, str]) -> str:
    T = theme
    return f"""
        QMainWindow {{
            background-color: {T['bg_deep']};
        }}
        QWidget {{
            font-size: 13px;
        }}
        #AppShellHeader {{
            background-color: {T['bg_surface']};
            border-bottom: 1px solid {T['border']};
        }}
        #AppShellTitle {{
            font-size: 18px;
            font-weight: 900;
            color: {T['text_primary']};
        }}
        #AppShellSubtitle {{
            color: {T['text_medium']};
            font-size: 11px;
            letter-spacing: 0px;
        }}
        #HeaderRoleBadge {{
            background-color: {T['primary_soft']};
            border: 1px solid {T['accent_primary']};
            border-radius: 8px;
            color: {T['accent_primary']};
            padding: 8px 16px;
            font-weight: 900;
        }}
        #AppSidebar {{
            background-color: {T['bg_surface']};
            border-right: 1px solid {T['border']};
        }}
        QPushButton#SidebarNavButton {{
            border-radius: 8px;
            color: {T['text_medium']};
            font-size: 13px;
            font-weight: 800;
            padding: 9px 12px;
        }}
        QPushButton#SidebarNavButton:hover {{
            background-color: {T['bg_surface_light']};
            color: {T['text_primary']};
        }}
        QPushButton#SidebarNavButton:checked {{
            background-color: {T['primary_soft']};
            border: 1px solid #bfdbfe;
            color: {T['accent_primary']};
        }}
        QGroupBox {{
            border: 1px solid {T['border']};
            border-radius: 8px;
            margin-top: 14px;
            padding-top: 18px;
            background-color: {T['bg_surface']};
            font-weight: 900;
        }}
        QGroupBox::title {{
            color: {T['text_primary']};
            padding: 0 6px;
            left: 12px;
        }}
        QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QDateEdit {{
            background-color: {T['bg_surface']};
            border: 1px solid {T['border_bold']};
            border-radius: 6px;
            min-height: 30px;
            padding: 5px 8px;
        }}
        QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus, QDateEdit:focus {{
            border: 1px solid {T['accent_primary']};
            background-color: {T['bg_surface_light']};
        }}
        QPushButton#StandardAction,
        QPushButton#PrimaryPurchaseButton,
        QPushButton#PrimaryInventoryButton,
        QPushButton#DataOpsPrimaryButton,
        QPushButton#PrimaryRecipeButton {{
            background-color: {T['accent_primary']};
            border: none;
            border-radius: 7px;
            color: white;
            font-weight: 900;
            padding: 8px 16px;
        }}
        QPushButton#StandardAction:hover,
        QPushButton#PrimaryPurchaseButton:hover,
        QPushButton#PrimaryInventoryButton:hover,
        QPushButton#DataOpsPrimaryButton:hover,
        QPushButton#PrimaryRecipeButton:hover {{
            background-color: {T['primary_hover']};
        }}
        QPushButton#DangerAction,
        QPushButton#RecipeDangerBtn,
        QPushButton#PurchaseDangerButton {{
            background-color: {T['danger']};
            border: none;
            border-radius: 7px;
            color: white;
            font-weight: 900;
            padding: 8px 16px;
        }}
        QTableWidget {{
            background-color: {T['bg_surface']};
            border: 1px solid {T['border']};
            border-radius: 8px;
            gridline-color: #e2e8f0;
            selection-background-color: {T['primary_soft']};
            selection-color: {T['text_primary']};
        }}
        QHeaderView::section {{
            background-color: #f8fafc;
            color: {T['text_primary']};
            border: none;
            border-bottom: 1px solid {T['border']};
            padding: 9px 10px;
            font-size: 11px;
            font-weight: 900;
        }}
        QTableWidget::item {{
            border-bottom: 1px solid #e2e8f0;
            padding: 7px 9px;
        }}
        QLabel[profitState="positive"] {{
            color: {T['success']};
        }}
        QLabel[profitState="negative"] {{
            color: {T['danger']};
        }}
        #OpsFilterBar, #OpsSectionCard, #DataOpsSectionBox {{
            background-color: {T['bg_surface']};
            border: 1px solid {T['border']};
            border-radius: 8px;
        }}
        QScrollBar:vertical {{
            background: {T['bg_deep']};
            width: 9px;
        }}
        QScrollBar::handle:vertical {{
            background: #b8c4d6;
            border-radius: 4px;
        }}
    """
