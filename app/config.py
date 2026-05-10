from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BillingSettings:
    invoice_prefix: str = "CAFE"
    cart_autosave_seconds: int = 5


@dataclass(frozen=True)
class BackupSettings:
    enabled: bool = True
    directory: str = "data/backups"


@dataclass(frozen=True)
class AppSettings:
    shop_name: str = "Cafe Name"
    currency: str = "INR"
    language: str = "en"
    default_admin_pin: str = "1234"
    billing: BillingSettings = BillingSettings()
    backup: BackupSettings = BackupSettings()


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_version(root: Path | None = None) -> str:
    root = root or project_root()
    # Primary location: project root (development)
    version_file = root / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip() or "0.0.0"

    # When bundled by PyInstaller, data files are typically placed under
    # a runtime `_internal` folder inside the executable's directory.
    internal_version = root / "_internal" / "VERSION"
    if internal_version.exists():
        return internal_version.read_text(encoding="utf-8").strip() or "0.0.0"

    return "0.0.0"


def load_app_settings(root: Path | None = None) -> AppSettings:
    root = root or project_root()
    settings_file = root / "config" / "settings.json"
    if not settings_file.exists():
        return AppSettings()

    raw = json.loads(settings_file.read_text(encoding="utf-8"))
    billing_raw = raw.get("billing", {}) or {}
    backup_raw = raw.get("backup", {}) or {}
    admin_raw = raw.get("admin", {}) or {}
    return AppSettings(
        shop_name=str(raw.get("shop_name") or "Cafe Name"),
        currency=str(raw.get("currency") or "INR"),
        language=str(raw.get("language") or "en"),
        default_admin_pin=str(admin_raw.get("default_pin") or "1234"),
        billing=BillingSettings(
            invoice_prefix=str(billing_raw.get("invoice_prefix") or "CAFE"),
            cart_autosave_seconds=max(1, int(billing_raw.get("cart_autosave_seconds") or 5)),
        ),
        backup=BackupSettings(
            enabled=bool(backup_raw.get("enabled", True)),
            directory=str(backup_raw.get("directory") or "data/backups"),
        ),
    )
