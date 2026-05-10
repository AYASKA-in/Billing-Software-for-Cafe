# Technical Architecture & Documentation: Cafe POS

This document provides a detailed overview of the technical stack, architecture, workflow, and file structure of the Cafe Billing Software.

---

## 1. Technology Stack

The application is built using a modern Python-based desktop stack, prioritized for stability, performance, and portability.

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Language** | Python 3.x | Core programming language. |
| **GUI Framework** | PySide6 (Qt for Python) | Cross-platform UI development with native performance. |
| **Database** | SQLite | Serverless, local relational database for data persistence. |
| **Reporting** | openpyxl | Generating and manipulating Excel (.xlsx) reports. |
| **Packaging** | PyInstaller | Converting Python scripts into standalone executables. |
| **Styling** | QSS (Qt Style Sheets) | CSS-like styling for the PySide6 interface. |

---

## 2. System Architecture

The software follows a **Layered Architecture (N-Tier)** with **Dependency Injection**, ensuring separation of concerns and maintainability.

### Layers:
1.  **Presentation Layer (UI)**:
    - Located in `app/ui/`.
    - Handles user interactions, input validation (UI-level), and data display.
    - Uses PySide6 widgets and custom layouts.
2.  **Service Layer (Business Logic)**:
    - Located in `app/services/`.
    - Contains the core logic for Sales, Inventory, Bookkeeping, and Reporting.
    - Orchestrates data flow between the UI and the Data Access Layer.
3.  **Data Access Layer (DAL)**:
    - Located in `app/database/repository.py`.
    - Provides an abstraction over SQL queries using the Repository Pattern.
    - Centralizes all CRUD operations.
4.  **Persistence Layer**:
    - Located in `app/database/connection.py`.
    - Manages SQLite connections and schema initialization/migrations.

---

## 3. Core Workflows

### A. Application Initialization
1.  `main.py` is executed.
2.  The `bootstrap()` function initializes the **Database** and runs `schema.sql`.
3.  **Services** are instantiated and injected with the `Repository` or `Database` instance.
4.  The `MainWindow` is created, receiving all services via dependency injection.
5.  The PySide6 event loop starts.

### B. Sales & Inventory Deduction
1.  The user adds items to a cart in the UI.
2.  On "Checkout", the UI calls `SalesService.create_sale()`.
3.  `SalesService` checks if the item is a "sellable" with a "recipe".
4.  If a recipe exists, it deducts constituent "ingredients" from stock via `InventoryService`.
5.  The transaction is recorded in `sales` and `sale_items` tables.
6.  `PrintService` is invoked to generate a physical/digital receipt.

### C. Reporting & Analytics
1.  The user selects a date range in the Reports tab.
2.  `ReportService` queries the repository for sales, expenses, and purchases.
3.  Data is processed into summaries (Total Sales, Net Profit, etc.).
4.  If requested, `openpyxl` is used to export this data to an Excel file.

---

## 4. File Arrangement

```text
/Billing-Software-for-Cafe
├── main.py                 # Application entry point & Bootstrapper
├── requirements.txt        # Python dependencies
├── VERSION                 # Current software version (v1.2.x)
│
├── /app                    # Source Code
│   ├── /database           # Persistence Layer
│   │   ├── connection.py   # SQLite connection management
│   │   ├── repository.py   # SQL Query Abstraction (CRUD)
│   │   └── schema.sql      # Database structure & default data
│   │
│   ├── /models             # Data structures (Internal/Domain models)
│   │
│   ├── /services           # Business Logic Layer
│   │   ├── sales_service.py      # POS Logic & Inventory Linkage
│   │   ├── inventory_service.py  # Stock & Item Management
│   │   ├── report_service.py     # Analytics & Export Logic
│   │   ├── bookkeeping_service.py # Expense & Financial Tracking
│   │   └── print_service.py      # Thermal Receipt Generation
│   │
│   ├── /ui                 # Presentation Layer
│   │   └── main_window.py  # Main Dashboard & Screen Logic
│   │
│   └── /utils              # Helper Modules
│       └── backup.py       # DB Backup & Restoration logic
│
├── /config                 # Configuration
│   └── settings.json       # App-level JSON configurations
│
├── /data                   # Local Data Storage
│   ├── cafe.db             # Primary SQLite Database
│   ├── /backups            # Auto-generated DB backups
│   └── /printed_bills      # PDF/Text copies of receipts
│
├── /docs                   # Project Documentation
├── /scripts                # Maintenance & Build Scripts
└── /dist                   # Compiled Executables (Build Output)
```

---

## 5. Database Schema Highlights

The system uses a relational model to link POS activity with inventory:
- **`items`**: Stores both finished goods ("sellable") and raw materials ("ingredient").
- **`recipes`**: Maps sellable items to their ingredient components.
- **`stock_movements`**: Audits every change in inventory (sales, purchases, adjustments).
- **`day_closures`**: Captures a snapshot of financial health at the end of each business day.
