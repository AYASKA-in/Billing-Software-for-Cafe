PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category_id INTEGER,
    selling_price REAL NOT NULL CHECK (selling_price > 0),
    cost_price REAL NOT NULL DEFAULT 0 CHECK (cost_price >= 0),
    size_type TEXT,
    stock_quantity REAL NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
    reorder_level REAL NOT NULL DEFAULT 0 CHECK (reorder_level >= 0),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories (id)
);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT NOT NULL UNIQUE,
    sold_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_amount REAL NOT NULL CHECK (total_amount >= 0),
    payment_method TEXT NOT NULL DEFAULT 'cash'
);

CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity REAL NOT NULL CHECK (quantity > 0),
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    unit_cost REAL NOT NULL DEFAULT 0 CHECK (unit_cost >= 0),
    line_total REAL NOT NULL CHECK (line_total >= 0),
    FOREIGN KEY (sale_id) REFERENCES sales (id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items (id)
);

CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_name TEXT,
    purchased_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_cost REAL NOT NULL CHECK (total_cost >= 0),
    notes TEXT
);

CREATE TABLE IF NOT EXISTS purchase_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity REAL NOT NULL CHECK (quantity > 0),
    cost_price REAL NOT NULL CHECK (cost_price >= 0),
    line_total REAL NOT NULL CHECK (line_total >= 0),
    FOREIGN KEY (purchase_id) REFERENCES purchases (id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items (id)
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_type TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount >= 0),
    spent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL,
    quantity_delta REAL NOT NULL,
    reference_id INTEGER,
    notes TEXT,
    moved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items (id)
);

CREATE TABLE IF NOT EXISTS app_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS backups_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS day_closures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    closure_date TEXT NOT NULL UNIQUE,
    sales_total REAL NOT NULL,
    cogs_total REAL NOT NULL,
    expenses_total REAL NOT NULL,
    gross_profit REAL NOT NULL,
    net_profit REAL NOT NULL,
    closed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_role TEXT NOT NULL,
    action_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sales_sold_at ON sales (sold_at);
CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id ON sale_items (sale_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_item_id ON stock_movements (item_id);
CREATE INDEX IF NOT EXISTS idx_expenses_spent_at ON expenses (spent_at);
CREATE INDEX IF NOT EXISTS idx_stock_movements_moved_at ON stock_movements (moved_at);
CREATE INDEX IF NOT EXISTS idx_items_size_type ON items (size_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs (created_at);

INSERT OR IGNORE INTO categories (name) VALUES
    ('Food'),
    ('Beverage'),
    ('Cigarette');

INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES
    ('invoice_sequence', '0'),
    ('invoice_prefix', 'CAFE'),
    ('admin_pin', '1234'),
    ('current_role', 'cashier'),
    ('auto_backup_enabled', '0'),
    ('backup_interval_minutes', '60');
