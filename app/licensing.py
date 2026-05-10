from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)

LICENSE_TOKEN_PREFIX = "CAFEPOS1"


@dataclass(frozen=True)
class LicensePayload:
    schema: int
    product: str
    kind: str
    issued_at: str
    expires_at: str | None
    customer: str
    machine_id: str
    license_id: str
    max_version: str | None = None


@dataclass(frozen=True)
class LicenseValidationResult:
    valid: bool
    reason: str
    payload: LicensePayload | None


class LicenseError(ValueError):
    pass


def canonical_json_bytes(data: dict) -> bytes:
    return json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _base32_encode(raw: bytes) -> str:
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def _base32_decode(text: str) -> bytes:
    padded = text + ("=" * ((8 - (len(text) % 8)) % 8))
    return base64.b32decode(padded.encode("ascii"), casefold=True)


def _chunks(value: str, size: int = 5) -> str:
    return "-".join(value[i : i + size] for i in range(0, len(value), size))


def _clean_token_text(token: str) -> str:
    return "".join(ch for ch in token.upper() if ch.isalnum())


def format_license_token(raw_token_text: str) -> str:
    cleaned = _clean_token_text(raw_token_text)
    if cleaned.startswith(LICENSE_TOKEN_PREFIX):
        cleaned = cleaned[len(LICENSE_TOKEN_PREFIX) :]
    return f"{LICENSE_TOKEN_PREFIX}-{_chunks(cleaned, 5)}"


def parse_token_blob(token: str) -> dict:
    cleaned = _clean_token_text(token)
    if not cleaned.startswith(LICENSE_TOKEN_PREFIX):
        raise LicenseError("Invalid license prefix.")

    payload_text = cleaned[len(LICENSE_TOKEN_PREFIX) :]
    if not payload_text:
        raise LicenseError("Empty license payload.")

    try:
        raw = _base32_decode(payload_text)
        blob = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # pragma: no cover - malformed input
        raise LicenseError("Malformed license key.") from exc

    if not isinstance(blob, dict) or "p" not in blob or "s" not in blob:
        raise LicenseError("Malformed license key payload.")
    return blob


def build_token_blob(payload: dict, private_key: Ed25519PrivateKey) -> str:
    payload_bytes = canonical_json_bytes(payload)
    signature = private_key.sign(payload_bytes)
    blob = {
        "v": 1,
        "p": payload,
        "s": base64.urlsafe_b64encode(signature).decode("ascii").rstrip("="),
    }
    blob_raw = canonical_json_bytes(blob)
    return format_license_token(_base32_encode(blob_raw))


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _payload_from_dict(data: dict) -> LicensePayload:
    required = [
        "schema",
        "product",
        "kind",
        "issued_at",
        "customer",
        "machine_id",
        "license_id",
    ]
    missing = [key for key in required if key not in data]
    if missing:
        raise LicenseError(f"Missing license fields: {', '.join(missing)}")

    kind = str(data["kind"]).lower().strip()
    if kind not in {"trial", "permanent", "subscription"}:
        raise LicenseError("Unsupported license type.")

    expires_at = data.get("expires_at")
    if kind in {"trial", "subscription"} and not expires_at:
        raise LicenseError("Expiry is required for trial/subscription licenses.")

    return LicensePayload(
        schema=int(data["schema"]),
        product=str(data["product"]),
        kind=kind,
        issued_at=str(data["issued_at"]),
        expires_at=str(expires_at) if expires_at else None,
        customer=str(data["customer"]),
        machine_id=str(data["machine_id"]),
        license_id=str(data["license_id"]),
        max_version=str(data.get("max_version")) if data.get("max_version") else None,
    )


def verify_license_token(
    token: str,
    public_key: Ed25519PublicKey,
    machine_id: str,
    today: date | None = None,
) -> LicenseValidationResult:
    today = today or date.today()

    try:
        blob = parse_token_blob(token)
        payload = _payload_from_dict(blob["p"])
    except LicenseError as exc:
        return LicenseValidationResult(valid=False, reason=str(exc), payload=None)

    signature_text = str(blob.get("s", ""))
    if not signature_text:
        return LicenseValidationResult(valid=False, reason="Missing license signature.", payload=None)

    padded_sig = signature_text + ("=" * ((4 - (len(signature_text) % 4)) % 4))
    try:
        signature = base64.urlsafe_b64decode(padded_sig.encode("ascii"))
    except Exception:
        return LicenseValidationResult(valid=False, reason="Malformed signature.", payload=None)

    try:
        public_key.verify(signature, canonical_json_bytes(blob["p"]))
    except InvalidSignature:
        return LicenseValidationResult(valid=False, reason="Invalid license signature.", payload=None)

    if payload.machine_id != machine_id:
        return LicenseValidationResult(valid=False, reason="License is bound to another machine.", payload=payload)

    try:
        issued = _parse_iso_date(payload.issued_at)
    except Exception:
        return LicenseValidationResult(valid=False, reason="Invalid issued date in license.", payload=payload)

    if issued is None:
        return LicenseValidationResult(valid=False, reason="Invalid issued date in license.", payload=payload)

    if today < issued:
        return LicenseValidationResult(valid=False, reason="System date is earlier than license issue date.", payload=payload)

    if payload.expires_at:
        try:
            expiry = _parse_iso_date(payload.expires_at)
        except Exception:
            return LicenseValidationResult(valid=False, reason="Invalid expiry date in license.", payload=payload)

        if expiry is not None and today > expiry:
            return LicenseValidationResult(valid=False, reason="License has expired.", payload=payload)

    return LicenseValidationResult(valid=True, reason="ok", payload=payload)


def load_public_key_from_pem_file(path: Path) -> Ed25519PublicKey:
    pem_data = path.read_bytes()
    key = load_pem_public_key(pem_data)
    if not isinstance(key, Ed25519PublicKey):
        raise LicenseError("License public key is not Ed25519.")
    return key


def load_private_key_from_pem_file(path: Path) -> Ed25519PrivateKey:
    key = load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise LicenseError("License private key is not Ed25519.")
    return key


def generate_ed25519_keypair() -> tuple[bytes, bytes]:
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def machine_fingerprint() -> str:
    parts: list[str] = []

    if platform.system().lower().startswith("win"):
        try:
            import winreg  # pylint: disable=import-outside-toplevel

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                if machine_guid:
                    parts.append(str(machine_guid))
        except Exception:
            pass

    parts.append(platform.node() or "")
    parts.append(str(uuid.getnode()))
    parts.append(os.environ.get("PROCESSOR_IDENTIFIER", ""))

    seed = "|".join(parts).strip("|")
    if not seed:
        seed = "unknown-machine"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()
    return digest
