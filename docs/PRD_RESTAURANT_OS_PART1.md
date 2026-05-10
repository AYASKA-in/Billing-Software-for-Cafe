# Restaurant Operating System — Production PRD & SRS

> **Project Codename:** FLAVOR OS
> **Version:** 1.0.0-draft
> **Author:** Engineering Lead
> **Date:** 2026-04-23
> **Classification:** Internal — Engineering Reference
> **Benchmark:** Petpooja POS Platform

---

## Table of Contents

- [1. Executive Summary](#1-executive-summary)
- [2. Product Vision & Goals](#2-product-vision--goals)
- [3. System Architecture](#3-system-architecture)
- [4. Technology Stack](#4-technology-stack)
- [5. Module Specifications](#5-module-specifications)
- [6. Data Model](#6-data-model)
- [7. API Specification](#7-api-specification)
- [8. Real-Time & Offline Architecture](#8-real-time--offline-architecture)
- [9. Security & Compliance](#9-security--compliance)
- [10. Screen Flows & UX](#10-screen-flows--ux)
- [11. Non-Functional Requirements](#11-non-functional-requirements)
- [12. Build Phases & Roadmap](#12-build-phases--roadmap)
- [13. Appendices](#13-appendices)

---

## 1. Executive Summary

This document is a **production-grade Product Requirements Document (PRD)** and **Software Requirements Specification (SRS)** for building a restaurant operating system that matches and exceeds the capabilities of Petpooja — India's largest restaurant POS platform serving 1,50,000+ businesses across 140+ cities.

The system is an **omnichannel restaurant operating platform** covering:
- Point-of-Sale billing (3-click flow, offline-capable)
- Kitchen Display System & KOT routing
- Inventory management with recipe-based stock deduction
- Menu management with channel/time/outlet pricing
- Online order aggregation (Swiggy, Zomato, etc.)
- GST-compliant invoicing & e-invoicing
- Multi-outlet chain management with head-office dashboard
- CRM, loyalty, feedback, and SMS marketing
- Payments (Cash, UPI, Card, Wallet, Split)
- 80+ report types with real-time analytics
- Marketplace of add-on modules

### 1.1 Competitive Intelligence Summary

**Petpooja's public signals indicate:**

| Metric | Value |
|---|---|
| Clients served | 1,50,000+ businesses |
| Daily bills processed | 60,00,000+ |
| Cities with on-ground support | 140+ |
| Team size | 1,800+ professionals |
| Third-party integrations | 200+ |
| Report types | 80+ |
| Languages supported | 18+ Indian languages |
| Countries | India, UAE, South Africa |

**Their tech stack (from job posts & BuiltWith):**
- Frontend: React.js, Styled Components, Bootstrap, jQuery
- Backend: Node.js, Express.js
- Databases: MySQL, MongoDB
- Cloud: AWS (S3, Lambda, EC2, CloudFront, Route 53)
- Servers: Apache, nginx on Ubuntu
- QA: Selenium, Cypress, Playwright, Appium, Postman
- CI/CD: Jenkins, GitLab Actions, Docker

---

## 2. Product Vision & Goals

### 2.1 Vision Statement

Build a **modern, offline-first, API-driven restaurant operating system** that can be deployed as a SaaS platform for single outlets, chains, franchises, cloud kitchens, and QSR brands — with cleaner architecture, better UX, stronger offline sync, and more maintainable code than existing platforms.

### 2.2 Design Principles

| # | Principle | Why |
|---|---|---|
| 1 | **Billing must be fast** | <2s per transaction under any condition |
| 2 | **Kitchen updates must be real-time** | WebSocket-driven, <1s latency |
| 3 | **Offline terminals are first-class citizens** | Restaurants cannot stop billing during internet drops |
| 4 | **Inventory is ledger-based** | Never store just "current qty" — use immutable ledger |
| 5 | **Financial records are immutable** | Once issued, invoices never mutate |
| 6 | **Integrations are idempotent** | Every webhook/sync operation must be replay-safe |
| 7 | **Every sensitive action is auditable** | Voids, refunds, discounts, stock adjustments |
| 8 | **API-first architecture** | Every feature is an API before it is a screen |

### 2.3 Target User Roles

| Role | Description | Primary Interface |
|---|---|---|
| Owner | Full control across all outlets | Web Dashboard, Mobile App |
| Manager | Operations, staff, inventory at outlet level | Web Dashboard, POS |
| Cashier | Billing, payments, basic order management | POS Terminal |
| Captain/Waiter | Tableside order taking | Mobile App (Captain App) |
| Kitchen Staff | KOT processing, item preparation | Kitchen Display System |
| Inventory Manager | Stock, procurement, recipes, wastage | Web Dashboard |
| Delivery Executive | Order pickup and delivery | Mobile App |
| Customer | QR ordering, feedback, loyalty | QR Web Page, App |

### 2.4 Supported Restaurant Formats

- Fine dining restaurants
- Casual dining / family restaurants
- Quick service restaurants (QSR)
- Cloud kitchens / delivery-only
- Cafes and bakeries
- Bars and lounges
- Food courts
- Multi-brand chains and franchises
- Catering operations

---

## 3. System Architecture

### 3.1 Logical Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                      CLIENT LAYER                           │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌────────┐  │
│  │ POS  │ │Capt. │ │ KDS  │ │QR Web│ │Admin │ │Owner   │  │
│  │ App  │ │ App  │ │ App  │ │Order │ │Dash  │ │Mobile  │  │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └───┬────┘  │
└─────┼────────┼────────┼────────┼────────┼─────────┼────────┘
      │        │        │        │        │         │
┌─────┼────────┼────────┼────────┼────────┼─────────┼────────┐
│     └────────┴────────┴────────┴────────┴─────────┘        │
│                    API GATEWAY                              │
│              (Rate Limit, Auth, Routing)                    │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────┐
│                   APPLICATION LAYER                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │  Auth &  │ │  Menu    │ │  Order   │ │ Billing  │       │
│  │  Tenant  │ │ Service  │ │ Service  │ │ & Tax    │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Kitchen  │ │Inventory │ │ Payment  │ │ Integr.  │       │
│  │ Service  │ │ & Recipe │ │ Service  │ │ Service  │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │Reporting │ │   CRM    │ │ Notif.   │ │  Audit   │       │
│  │ Service  │ │& Loyalty │ │ Service  │ │ Service  │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────┐
│                      DATA LAYER                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │PostgreSQL│ │  Redis   │ │  S3/Obj  │ │ Event    │       │
│  │  (OLTP)  │ │(Cache/Q) │ │ Storage  │ │  Bus     │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Architectural Style

**Phase 1-3:** Modular Monolith with clear domain boundaries
**Phase 4+:** Extract into microservices as scale demands

Benefits:
- Simpler initial development and deployment
- Single deployment unit reduces operational overhead
- Clean module boundaries allow future extraction
- Shared database simplifies transactions during early stages

### 3.3 Multi-Tenancy Model

- **Tenant** = one customer organization (e.g., a restaurant group)
- **Brand** = one restaurant brand under a tenant
- **Outlet** = one physical location under a brand
- Every database record carries `tenant_id`; most also carry `outlet_id`
- Row-level security enforced at the ORM/query layer
- Tenant isolation in application code, not separate databases (for cost efficiency)

---

## 4. Technology Stack

### 4.1 Recommended Stack (Modern Rebuild)

#### Frontend

| Component | Technology | Rationale |
|---|---|---|
| Admin Dashboard | **Next.js 14 + React 18 + TypeScript** | SSR for SEO, RSC for performance, App Router |
| POS Terminal | **Electron 28 + React + TypeScript** | Desktop app with local SQLite, printer access |
| Captain/Waiter App | **React Native 0.73+** | Cross-platform mobile, offline storage |
| Kitchen Display | **React PWA + WebSockets** | Real-time updates, runs on Android TV/tablet |
| QR Order Page | **Next.js (lightweight)** | Fast load, mobile-first, SEO-friendly |
| State Management | **Zustand + React Query** | Lightweight, cache-aware, sync-friendly |
| Styling | **Tailwind CSS 3.4** | Rapid UI development, design consistency |
| Charts | **Recharts or Nivo** | Dashboard analytics visualization |

#### Backend

| Component | Technology | Rationale |
|---|---|---|
| API Framework | **NestJS 10 + TypeScript** | Modular, decorator-based, enterprise-grade |
| ORM | **Prisma 5 or TypeORM** | Type-safe queries, migrations, relations |
| Auth | **JWT (access + refresh) + Passport.js** | Stateless auth with device binding |
| Validation | **class-validator + class-transformer** | DTO validation at controller boundary |
| API Documentation | **Swagger/OpenAPI 3.0 (auto-gen from NestJS)** | Always up-to-date API docs |
| Task Queue | **BullMQ (Redis-backed)** | Background jobs: reports, sync, notifications |
| WebSocket | **Socket.IO via NestJS Gateway** | Real-time KDS, order status, terminal sync |
| File Upload | **Multer + S3 SDK** | Invoice PDFs, logos, attachments |

#### Database & Storage

| Component | Technology | Rationale |
|---|---|---|
| Primary DB | **PostgreSQL 16** | ACID, JSONB, row-level security, mature |
| Cache & Queues | **Redis 7** | Sessions, locks, pub/sub, BullMQ backing |
| Local (POS) | **SQLite (via better-sqlite3)** | Offline cache on Electron terminals |
| Object Storage | **AWS S3 / MinIO** | Invoices, exports, logos, attachments |
| Search (later) | **Meilisearch or OpenSearch** | Fast menu/item search across outlets |

#### Infrastructure

| Component | Technology | Rationale |
|---|---|---|
| Containerization | **Docker + Docker Compose** | Consistent dev/prod environments |
| Orchestration | **Kubernetes (EKS/GKE)** | Auto-scaling, rolling deploys |
| Cloud | **AWS** | RDS, ElastiCache, S3, CloudFront, Lambda |
| CI/CD | **GitHub Actions** | Automated test, build, deploy pipeline |
| Monitoring | **Prometheus + Grafana** | Metrics, dashboards, alerting |
| Error Tracking | **Sentry** | Real-time error capture across all clients |
| Logging | **Winston + CloudWatch / ELK** | Structured logging, searchable |
| CDN | **CloudFront** | Static assets, QR page, dashboard |

#### Communication

| Pattern | Technology | Use Case |
|---|---|---|
| Sync API | **REST (JSON)** | CRUD operations, billing, menu |
| Real-time | **WebSocket (Socket.IO)** | KDS, order status, terminal sync |
| Async Events | **Redis Pub/Sub + BullMQ** | Report generation, notifications, sync |
| Webhooks | **Inbound + Outbound** | Payment callbacks, aggregator orders |

### 4.2 Hardware Support

| Device | Use | OS |
|---|---|---|
| Windows PC/Laptop | POS Terminal | Windows 10+ |
| Android Tablet | Captain App, KDS | Android 9+ |
| Android TV | Token Display, KDS | Android TV |
| Thermal Printer | Bill, KOT printing | ESC/POS protocol |
| Barcode Scanner | Item scanning | USB HID |
| Cash Drawer | Cash management | RJ11 via printer |
| Weighing Scale | Weight-based billing | Serial/USB |
| UPI QR Stand | Customer payment | — |

---

*Continued in [Part 2 →](./PRD_RESTAURANT_OS_PART2.md)*
