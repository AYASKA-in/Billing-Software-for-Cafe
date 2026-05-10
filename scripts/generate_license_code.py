from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.licensing import build_token_blob, load_private_key_from_pem_file


def _today_iso() -> str:
    return date.today().isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate signed offline activation code.")
    parser.add_argument("--private-key", required=True, help="Path to Ed25519 private key PEM")
    parser.add_argument("--kind", required=True, choices=["trial", "permanent", "subscription"])
    parser.add_argument("--customer", required=True, help="Customer/shop identifier")
    parser.add_argument("--machine-id", required=True, help="Machine fingerprint from app activation screen")
    parser.add_argument("--license-id", required=True, help="Unique license id, e.g. CAFE-2026-0001")
    parser.add_argument("--issued-at", default=_today_iso(), help="Issue date (YYYY-MM-DD)")
    parser.add_argument(
        "--expires-at",
        default="",
        help="Expiry date (YYYY-MM-DD). Required for trial/subscription unless --trial-days is provided.",
    )
    parser.add_argument(
        "--trial-days",
        type=int,
        default=0,
        help="For trial keys, set expiry to issued_at + N days.",
    )
    parser.add_argument("--max-version", default="", help="Optional max app version")
    parser.add_argument("--product", default="cafepos", help="Product identifier")
    args = parser.parse_args()

    issued = date.fromisoformat(args.issued_at)

    expires = args.expires_at.strip()
    if args.kind in {"trial", "subscription"}:
        if args.trial_days > 0:
            expires = (issued + timedelta(days=args.trial_days)).isoformat()
        if not expires:
            raise ValueError("Expiry is required for trial/subscription keys.")

    if args.kind == "permanent":
        expires = ""

    private_key = load_private_key_from_pem_file(Path(args.private_key))

    payload = {
        "schema": 1,
        "product": args.product.strip().lower(),
        "kind": args.kind,
        "issued_at": issued.isoformat(),
        "expires_at": expires or None,
        "customer": args.customer.strip(),
        "machine_id": args.machine_id.strip().upper(),
        "license_id": args.license_id.strip(),
        "max_version": args.max_version.strip() or None,
    }

    code = build_token_blob(payload=payload, private_key=private_key)

    print("Signed activation code generated:\n")
    print(code)
    print("\nDetails:")
    for key, value in payload.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
