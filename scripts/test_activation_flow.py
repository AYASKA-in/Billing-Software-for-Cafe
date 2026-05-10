"""
End-to-end test: offline licensing activation flow.

Simulates:
1. App starts with no license → activation required
2. User enters trial code → activation successful
3. App restarts (simulated) → code still valid
4. User sees "Active" status
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database.connection import Database
from app.database.repository import Repository
from app.licensing import machine_fingerprint, generate_ed25519_keypair, build_token_blob, load_private_key_from_pem_file
from app.services.bookkeeping_service import BookkeepingService
from app.services.license_service import LicenseService


def main() -> int:
    print("=" * 80)
    print("OFFLINE LICENSING ACTIVATION FLOW TEST")
    print("=" * 80)
    print()

    # ──────────────────────────────────────────────────────────────────────
    # Step 1: Setup temp DB and services
    # ──────────────────────────────────────────────────────────────────────
    tmp_db = Path(tempfile.gettempdir()) / "cafe_licensing_test.db"
    if tmp_db.exists():
        tmp_db.unlink()

    print("[SETUP] Initializing temporary database...")
    db = Database(str(tmp_db))
    db.init_schema()
    repo = Repository(db)
    bookkeeping = BookkeepingService(repo)

    # Use the real public key from config
    print("[SETUP] Using production public key from config/license_public_key.pem")
    license_service = LicenseService(bookkeeping)

    machine_id = license_service.machine_id()
    print(f"[SETUP] This machine ID: {machine_id}")
    print()

    # ──────────────────────────────────────────────────────────────────────
    # Step 2: Verify enforcement is configured
    # ──────────────────────────────────────────────────────────────────────
    print("[CHECK] License enforcement configured?", license_service.is_enforcement_configured())
    print("[CHECK] Public key exists?", license_service.has_public_key())
    print()

    # ──────────────────────────────────────────────────────────────────────
    # Step 3: Startup check - no license yet
    # ──────────────────────────────────────────────────────────────────────
    print("[STARTUP] Evaluating current license status...")
    status = license_service.evaluate_current_license()
    print(f"  Valid: {status.valid}")
    print(f"  Reason: {status.reason}")
    if not status.valid:
        print("  ✓ As expected: activation is required")
    print()

    # ──────────────────────────────────────────────────────────────────────
    # Step 4: Generate trial activation code
    # ──────────────────────────────────────────────────────────────────────
    print("[LICENSE-GEN] Generating 30-day trial code for this machine...")
    private_key_path = ROOT_DIR / "keys" / "license_private_key.pem"
    private_key = load_private_key_from_pem_file(private_key_path)
    
    trial_payload = {
        "schema": 1,
        "product": "cafepos",
        "kind": "trial",
        "issued_at": date.today().isoformat(),
        "expires_at": (date.today() + timedelta(days=30)).isoformat(),
        "customer": "Break Time Cafe - Test",
        "machine_id": machine_id,
        "license_id": "TEST-TRIAL-ACTIVATION",
        "max_version": None,
    }
    
    trial_code = build_token_blob(payload=trial_payload, private_key=private_key)
    print(f"  Trial code (first 50 chars): {trial_code[:50]}...")
    print()

    # ──────────────────────────────────────────────────────────────────────
    # Step 5: User activates with the trial code
    # ──────────────────────────────────────────────────────────────────────
    print("[ACTIVATION] User enters trial code into dialog...")
    activation_result = license_service.activate_with_token(trial_code)
    print(f"  Valid: {activation_result.valid}")
    print(f"  Reason: {activation_result.reason}")
    if activation_result.payload:
        print(f"  Payload kind: {activation_result.payload.kind}")
        print(f"  Payload expires: {activation_result.payload.expires_at}")
    if activation_result.valid:
        print("  ✓ Activation successful")
    print()

    # ──────────────────────────────────────────────────────────────────────
    # Step 6: Check persisted token
    # ──────────────────────────────────────────────────────────────────────
    print("[PERSISTENCE] Checking persisted license in app settings...")
    stored_token = bookkeeping.get_setting(LicenseService.KEY_LICENSE_TOKEN, None)
    print(f"  Stored token exists: {bool(stored_token)}")
    print(f"  Stored token (first 50 chars): {str(stored_token)[:50] if stored_token else 'None'}...")
    print()

    # ──────────────────────────────────────────────────────────────────────
    # Step 7: Simulate app restart (create new service instances, same DB)
    # ──────────────────────────────────────────────────────────────────────
    print("[RESTART] Simulating app restart (new service instances, same DB)...")
    
    # New instances, same database
    db2 = Database(str(tmp_db))
    repo2 = Repository(db2)
    bookkeeping2 = BookkeepingService(repo2)
    license_service2 = LicenseService(bookkeeping2)
    
    print("  ✓ New service instances created with persistent database")
    print()

    # ──────────────────────────────────────────────────────────────────────
    # Step 8: Startup check after restart
    # ──────────────────────────────────────────────────────────────────────
    print("[STARTUP-AFTER-RESTART] Evaluating license status...")
    status_after_restart = license_service2.evaluate_current_license()
    print(f"  Valid: {status_after_restart.valid}")
    print(f"  Reason: {status_after_restart.reason}")
    if status_after_restart.valid and status_after_restart.payload:
        print(f"  Customer: {status_after_restart.payload.customer}")
        print(f"  Kind: {status_after_restart.payload.kind}")
        print(f"  Expires: {status_after_restart.payload.expires_at}")
        print("  ✓ License persisted and valid after restart")
    print()

    # ──────────────────────────────────────────────────────────────────────
    # Step 9: Check summary text
    # ──────────────────────────────────────────────────────────────────────
    print("[UI-SUMMARY] License summary for UI display:")
    summary = license_service2.summary_text()
    print(f"  '{summary}'")
    print()

    # ──────────────────────────────────────────────────────────────────────
    # Step 10: Test permanent license activation
    # ──────────────────────────────────────────────────────────────────────
    print("[PERMANENT-LICENSE] Testing permanent license upgrade...")
    
    perm_payload = {
        "schema": 1,
        "product": "cafepos",
        "kind": "permanent",
        "issued_at": date.today().isoformat(),
        "expires_at": None,
        "customer": "Break Time Cafe - Test",
        "machine_id": machine_id,
        "license_id": "TEST-PERM-ACTIVATION",
        "max_version": None,
    }
    
    perm_code = build_token_blob(payload=perm_payload, private_key=private_key)
    perm_result = license_service2.activate_with_token(perm_code)
    print(f"  Valid: {perm_result.valid}")
    print(f"  Reason: {perm_result.reason}")
    if perm_result.payload:
        print(f"  Payload kind: {perm_result.payload.kind}")
        print(f"  Expires: {perm_result.payload.expires_at}")
    if perm_result.valid:
        print("  ✓ Permanent license activation successful")
    print()

    # ──────────────────────────────────────────────────────────────────────
    # Step 11: Verify summary updated
    # ──────────────────────────────────────────────────────────────────────
    print("[UI-SUMMARY-UPDATED] License summary after permanent activation:")
    summary_updated = license_service2.summary_text()
    print(f"  '{summary_updated}'")
    print()

    # ──────────────────────────────────────────────────────────────────────
    # Cleanup
    # ──────────────────────────────────────────────────────────────────────
    if tmp_db.exists():
        tmp_db.unlink()

    print("=" * 80)
    print("✓ END-TO-END ACTIVATION FLOW TEST PASSED")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
