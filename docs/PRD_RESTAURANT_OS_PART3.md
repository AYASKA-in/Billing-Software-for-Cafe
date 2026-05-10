# Restaurant Operating System — Production PRD & SRS (Part 3)
6: > **Project Codename:** FLAVOR OS
7: > **Version:** 1.0.0-draft
8: > **Classification:** Internal — Engineering Reference
9: 
10: ---
11: 
12: ## 8. Real-Time & Offline Architecture
13: 
14: ### 8.1 The "Local First" Strategy
15: To ensure zero downtime, the POS terminal must follow a **Local-First** synchronization pattern:
16: 
17: 1.  **Local State**: All orders are first written to the local SQLite database.
18: 2.  **Background Sync**: A dedicated worker service periodically pushes local changes to the Cloud PostgreSQL instance.
19: 3.  **Conflict Handling**: Use vector clocks or standard `updated_at` timestamps. In most POS scenarios, "Last Write Wins" is acceptable at the order level, while "Append Only" is required for the ledger.
20: 
21: ### 8.2 Real-Time Communication (WebSockets)
22: - **KDS Updates**: When a POS terminal places an order, the server broadcasts to the specific KDS client for that outlet.
23: - **Order Status**: When the kitchen marks an item as "Ready," the waiter's app and POS receive an immediate notification.
24: 
25: ---
26: 
27: ## 9. Security & Compliance
28: 
29: ### 9.1 Access Control
30: - **PIN-Based Authorization**: Fast switching between users on the same terminal using 4 or 6-digit PINs.
31: - **Manager Overrides**: Specific actions (Voids, Manual Discounts, Stock Adjustments) trigger a "Manager PIN Required" popup.
32: 
33: ### 9.2 Data Protection
34: - **Encryption**: All PII (Personally Identifiable Information) must be encrypted at rest (AES-256).
35: - **Audit Trails**: Every database mutation must log the `user_id`, `timestamp`, and `old_value` vs `new_value`.
36: 
37: ### 9.3 Tax Compliance
38: - **GST Ready**: Support for CGST, SGST, IGST, and Cess.
39: - **Round-off Logic**: Configurable rounding (Normal, Up, Down) for final bill totals.
40: 
41: ---
42: 
43: ## 10. Screen Flows & UX
44: 
45: ### 10.1 POS Billing Flow
46: 1.  **Login**: Enter PIN → Dashboard.
47: 2.  **Selection**: Select Table → Browse Categories → Tap Items (Modifiers appear as popups).
48: 3.  **Checkout**: View Summary → Apply Coupon → Select Payment Method → Print Bill.
49: 
50: ### 10.2 Inventory Flow
51: 1.  **Stock-In**: Scan Invoice/Barcode → Enter Quantity → Update Cost Price → Save.
52: 2.  **Audit**: Select Ingredient → Enter "Physical Count" → System calculates "Variance" → Manager approves adjustment.
53: 
54: ---
55: 
56: ## 11. Non-Functional Requirements
57: 
58: | Category | Requirement |
59: |---|---|
60: | **Availability** | 99.95% uptime for the cloud backend. |
61: | **Latency** | <100ms for local database hits; <500ms for API responses (P95). |
62: | **Scalability** | Support up to 10,000 concurrent outlets on a single cluster. |
63: | **Durability** | Multi-region database backups with 15-minute RPO. |
64: 
65: ---
66: 
67: ## 12. Build Phases & Roadmap
68: 
69: ### Phase 1: Core Foundation (MVP) - 8 Weeks
70: - Basic Billing & KOT Printing.
71: - Menu Management (Single Outlet).
72: - Basic Sales Reports (Daily/Monthly).
73: 
74: ### Phase 2: Inventory & Recipes - 6 Weeks
75: - Ingredient Ledger & Recipe Mapping.
76: - Low-Stock Alerts.
77: - Expense Tracking.
78: 
79: ### Phase 3: Omnichannel & Scale - 8 Weeks
80: - Online Order Aggregation (Zomato/Swiggy).
81: - Multi-Outlet Dashboard.
82: - Customer Loyalty & CRM.
83: 
84: ---
85: 
86: ## 13. Appendices
87: - **A1**: ESC/POS Print Template Samples.
88: - **A2**: GST Calculation Examples.
89: - **A3**: API Error Code Dictionary.
90: 
91: ---
92: 
93: **End of Document.**
94: 
