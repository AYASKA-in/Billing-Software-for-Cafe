from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from app.licensing import (
    LicensePayload,
    LicenseValidationResult,
    load_public_key_from_pem_file,
    machine_fingerprint,
    verify_license_token,
)
from app.services.bookkeeping_service import BookkeepingService


@dataclass(frozen=True)
class LicenseStatus:
    valid: bool
    reason: str
    payload: LicensePayload | None
    machine_id: str


class LicenseService:
    PRODUCT_ID = "cafepos"

    KEY_LICENSE_TOKEN = "license_token"
    KEY_LICENSE_PAYLOAD = "license_payload_json"
    KEY_LICENSE_LAST_SEEN = "license_last_seen_date"

    def __init__(self, bookkeeping_service: BookkeepingService) -> None:
        self.bookkeeping_service = bookkeeping_service

    def machine_id(self) -> str:
        return machine_fingerprint()

    def _get_public_key_path(self) -> Path | None:
        """Find public key in dev or packaged location."""
        # Try development/regular location first
        dev_path = Path("config") / "license_public_key.pem"
        if dev_path.exists():
            return dev_path
        # Try PyInstaller internal location
        internal_path = Path("_internal") / "config" / "license_public_key.pem"
        if internal_path.exists():
            return internal_path
        return None

    def has_public_key(self) -> bool:
        return self._get_public_key_path() is not None

    def is_enforcement_configured(self) -> bool:
        return self.has_public_key()

    def _load_public_key(self):
        key_path = self._get_public_key_path()
        if not key_path:
            raise FileNotFoundError("License public key not found in config or _internal/config")
        return load_public_key_from_pem_file(key_path)

    def _stored_token(self) -> str | None:
        token = self.bookkeeping_service.get_setting(self.KEY_LICENSE_TOKEN, None)
        return token.strip() if token else None

    def _clock_rollback_detected(self, today: date) -> bool:
        last_seen_text = self.bookkeeping_service.get_setting(self.KEY_LICENSE_LAST_SEEN, "") or ""
        if not last_seen_text:
            return False

        try:
            last_seen = date.fromisoformat(last_seen_text)
        except Exception:
            return False

        # Allow 1 day tolerance to avoid timezone/manual mistakes.
        return today < (last_seen - timedelta(days=1))

    def evaluate_current_license(self, today: date | None = None) -> LicenseStatus:
        today = today or date.today()
        machine_id = self.machine_id()

        if not self.has_public_key():
            return LicenseStatus(
                valid=True,
                reason="License system is not configured yet.",
                payload=None,
                machine_id=machine_id,
            )

        token = self._stored_token()
        if not token:
            return LicenseStatus(valid=False, reason="Software is not activated.", payload=None, machine_id=machine_id)

        if self._clock_rollback_detected(today):
            return LicenseStatus(
                valid=False,
                reason="System clock rollback detected. Please correct system date/time.",
                payload=None,
                machine_id=machine_id,
            )

        try:
            public_key = self._load_public_key()
        except Exception as exc:
            return LicenseStatus(valid=False, reason=f"Cannot read license public key: {exc}", payload=None, machine_id=machine_id)

        result: LicenseValidationResult = verify_license_token(
            token=token,
            public_key=public_key,
            machine_id=machine_id,
            today=today,
        )

        payload = result.payload
        if payload and payload.product.lower() != self.PRODUCT_ID:
            return LicenseStatus(valid=False, reason="License is for a different product.", payload=payload, machine_id=machine_id)

        return LicenseStatus(valid=result.valid, reason=result.reason, payload=payload, machine_id=machine_id)

    def activate_with_token(self, token: str, today: date | None = None) -> LicenseStatus:
        today = today or date.today()
        status = self._evaluate_token_text(token=token, today=today)
        if not status.valid:
            return status

        normalized = " ".join(token.strip().split())
        self.bookkeeping_service.set_setting(self.KEY_LICENSE_TOKEN, normalized)
        if status.payload is not None:
            self.bookkeeping_service.set_setting(self.KEY_LICENSE_PAYLOAD, json.dumps(status.payload.__dict__, sort_keys=True))
        self.bookkeeping_service.set_setting(self.KEY_LICENSE_LAST_SEEN, today.isoformat())
        return status

    def _evaluate_token_text(self, token: str, today: date) -> LicenseStatus:
        machine_id = self.machine_id()

        if not self.has_public_key():
            return LicenseStatus(
                valid=False,
                reason="License public key is missing (config/license_public_key.pem).",
                payload=None,
                machine_id=machine_id,
            )

        try:
            public_key = self._load_public_key()
        except Exception as exc:
            return LicenseStatus(valid=False, reason=f"Cannot read license public key: {exc}", payload=None, machine_id=machine_id)

        result = verify_license_token(
            token=token,
            public_key=public_key,
            machine_id=machine_id,
            today=today,
        )
        payload = result.payload
        if payload and payload.product.lower() != self.PRODUCT_ID:
            return LicenseStatus(valid=False, reason="License is for a different product.", payload=payload, machine_id=machine_id)
        return LicenseStatus(valid=result.valid, reason=result.reason, payload=payload, machine_id=machine_id)

    def mark_successful_launch(self, today: date | None = None) -> None:
        today = today or date.today()
        self.bookkeeping_service.set_setting(self.KEY_LICENSE_LAST_SEEN, today.isoformat())

    def summary_text(self) -> str:
        status = self.evaluate_current_license()
        if not status.valid:
            return f"Inactive ({status.reason})"

        payload = status.payload
        if payload is None:
            return "Active"

        if payload.kind == "permanent":
            return f"Active • Permanent • {payload.customer}"

        expiry = payload.expires_at or "N/A"
        return f"Active • {payload.kind.title()} • expires {expiry}"
