# Restaurant Operating System — Production PRD & SRS (Part 2)
6: > **Project Codename:** FLAVOR OS
7: > **Version:** 1.0.0-draft
8: > **Classification:** Internal — Engineering Reference
9: 
10: ---
11: 
12: ## 5. Module Specifications
13: 
14: ### 5.1 Point-of-Sale (POS) Module
15: **Core Objective:** Provide a zero-friction billing experience that works offline and syncs when online.
16: 
17: | Feature | Description | Requirement |
18: |---|---|---|
19: | **Quick-Bill Interface** | 3-click flow: Select Item → Apply Discount (Optional) → Print. | Performance: <2s |
20: | **Multi-Terminal Sync** | Multiple terminals in one outlet syncing to a local master station. | Conflict Resolution: Last-write-wins |
21: | **Table Management** | Visual floor plan, table merging/splitting, and move-table logic. | State: Real-time via WebSockets |
22: | **Offline Mode** | Capability to bill, print, and save orders without internet. | Local Storage: SQLite/IndexedDB |
23: | **Payment Versatility** | Cash, Card, UPI (Dynamic QR), Wallet, and Split Payments. | Integration: Payment Gateway SDKs |
24: | **KOT Routing** | Automatically send items to specific printers (e.g., Bar, Kitchen 1). | Protocol: ESC/POS |
25: 
26: ### 5.2 Inventory & Recipe Management
27: **Core Objective:** Prevent wastage and ensure real-time stock visibility through ledger-based tracking.
28: 
29: | Feature | Description | Requirement |
30: |---|---|---|
31: | **Recipe Costing** | Link menu items to raw ingredients (e.g., 1 Burger = 1 Bun + 100g Meat). | Precision: 4 decimal places |
32: | **Auto-Deduction** | Automatically deduct stock based on sales (including modifiers). | Event-driven: Trigger on "Order Finalized" |
33: | **Purchase Orders** | Manage vendor relationships, PO creation, and GRN (Goods Received Note). | Workflow: Draft → Approved → Received |
34: | **Wastage Tracking** | Log wastage with reasons (Spoilage, Burned, Error). | Audit: Require Manager PIN |
35: | **Low-Stock Alerts** | Real-time notifications when ingredients hit reorder levels. | Delivery: In-app + Push |
36: 
37: ### 5.3 Online Order Aggregation
38: **Core Objective:** Centralize Swiggy, Zomato, and Direct Web orders into a single screen.
39: 
40: | Feature | Description | Requirement |
41: |---|---|---|
42: | **Menu Sync** | Push menu changes (Price, Availability) to all aggregators at once. | API: Aggregator Hub (UrbanPiper/Iterate) |
43: | **Order Auto-Accept** | Rules to automatically accept orders based on kitchen capacity. | Configurable: Per-channel |
44: | **Unified KDS** | Display online and dine-in orders on the same Kitchen Display System. | Priority: FIFO or Manual Override |
45: 
46: ---
47: 
48: ## 6. Data Model
49: 
50: ### 6.1 Core Entities (High-Level Schema)
51: 
52: #### 6.1.1 Organization & Outlets
53: - **`tenants`**: Enterprise-level account.
54: - **`outlets`**: Individual physical locations.
55: - **`staff`**: User accounts with RBAC (Role Based Access Control).
56: 
57: #### 6.1.2 Menu System
58: - **`categories`**: Food categories (Appetizers, Mains, etc.).
59: - **`menu_items`**: Sellable products.
60: - **`modifiers`**: Add-ons (Extra Cheese, Spicy, etc.) linked to items.
61: - **`item_prices`**: Outlet-specific and channel-specific pricing.
62: 
63: #### 6.1.3 Transactional
64: - **`orders`**: Header record for a transaction.
65: - **`order_items`**: Line items within an order.
66: - **`invoices`**: Financial record (Immutable).
67: - **`payments`**: Payment details including split methods.
68: 
69: #### 6.1.4 Inventory
70: - **`ingredients`**: Raw materials.
71: - **`recipes`**: Mapping of `menu_item` → `ingredients` (Quantity).
72: - **`stock_ledger`**: Every single movement (Add, Deduct, Waste, Return).
73: 
74: ### 6.2 Database Constraints
75: - **Soft Deletes**: Use `deleted_at` for all primary entities to preserve historical reports.
76: - **UUIDs**: Use `uuid_v7` for primary keys to support distributed offline generation without collisions.
77: - **Audit Columns**: `created_by`, `updated_by`, `ip_address`, `device_id` on every sensitive row.
78: 
79: ---
80: 
81: ## 7. API Specification (Core Endpoints)
82: 
83: | Method | Endpoint | Description |
84: |---|---|---|
85: | **POST** | `/api/v1/auth/login` | Secure login with device fingerprinting. |
86: | **GET** | `/api/v1/pos/menu` | Fetch full menu with local caching headers. |
87: | **POST** | `/api/v1/pos/orders` | Create order (Support for idempotent retry tokens). |
88: | **PATCH** | `/api/v1/pos/orders/:id/status` | Update order state (Pending → Kitchen → Served). |
89: | **GET** | `/api/v1/inventory/stock` | Real-time stock levels across all ingredients. |
90: | **POST** | `/api/v1/inventory/audit` | Manual stock adjustment with manager PIN. |
91: | **GET** | `/api/v1/reports/sales` | Aggregated sales data with multi-dimension filters. |
92: 
93: ---
94: 
95: *Continued in [Part 3 →](./PRD_RESTAURANT_OS_PART3.md)*
96: 
