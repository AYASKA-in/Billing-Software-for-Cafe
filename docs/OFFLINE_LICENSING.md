# Offline Licensing (Trial + Permanent)

This project now supports offline activation using signed license codes.

## 1) Overview

- License codes are signed with an Ed25519 private key.
- The app verifies codes using only the public key.
- No internet/server is required for activation.
- Trial and permanent licenses are both supported.

## 2) One-time key setup (owner side)

Generate key pair and place app public key:

```powershell
python scripts/generate_license_keys.py --out-dir keys --public-copy config/license_public_key.pem
```

Output:
- `keys/license_private_key.pem` (KEEP SECRET)
- `keys/license_public_key.pem`
- `config/license_public_key.pem` (used by app)

## 3) Get customer machine ID

Customer can read machine ID from activation dialog, or run:

```powershell
python scripts/show_machine_id.py
```

## 4) Generate trial code (example: 30 days)

```powershell
python scripts/generate_license_code.py \
  --private-key keys/license_private_key.pem \
  --kind trial \
  --customer "Break Time Cafe - Anna Nagar" \
  --machine-id "<MACHINE_ID>" \
  --license-id "CAFE-2026-0001" \
  --trial-days 30
```

## 5) Generate permanent code

```powershell
python scripts/generate_license_code.py \
  --private-key keys/license_private_key.pem \
  --kind permanent \
  --customer "Break Time Cafe - Anna Nagar" \
  --machine-id "<MACHINE_ID>" \
  --license-id "CAFE-2026-PERM-0001"
```

## 6) App behavior

- If `config/license_public_key.pem` exists, activation is enforced at startup.
- If no valid code exists, activation dialog is shown.
- Trial/subscription locks after expiry and requires new code.
- Existing DB data remains untouched.
- Permanent license never expires.

## 7) Security notes

- Never share `license_private_key.pem`.
- Never package private key with client builds.
- Public key is safe to ship in the app.

## 8) Reissue policy (recommended)

Store these fields for each issued key:
- `license_id`
- `customer`
- `machine_id`
- `kind`
- `issued_at`
- `expires_at`
- `reissue_count`
