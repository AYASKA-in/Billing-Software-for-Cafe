# Release & Deployment Guide: Offline Licensing

This guide explains how to prepare, build, and deploy releases of CafePOS with offline licensing support.

## 1. Pre-Release Setup (One-Time)

### 1.1 Generate Production Keypair

Run this command once to generate the signing and verification keys:

```powershell
python scripts/generate_license_keys.py --out-dir keys --public-copy config/license_public_key.pem
```

**Output:**
- `keys/license_private_key.pem` — **KEEP OFFLINE & SECRET** (owner's signing key)
- `keys/license_public_key.pem` — backup copy (optional)
- `config/license_public_key.pem` — **included in every release** (app verification key)

### 1.2 Secure the Private Key

```powershell
# Recommended: Encrypt and backup the private key to a secure location
# Example: USB drive, encrypted storage, or offline safe.

# NEVER commit to version control
# NEVER share with anyone
# NEVER include in release artifacts
```

**Backup checklist:**
- ✓ Store `keys/license_private_key.pem` in encrypted offline storage
- ✓ Keep access restricted to owner/admin only
- ✓ Test keypair backup can be recovered when needed
- ✓ Document recovery procedure in owner handbook

## 2. Building a Release with Licensing

### 2.1 Standard Release Process (Unchanged)

The existing release script automatically detects and bundles the public key:

```powershell
cd "d:\software for cafe"
powershell -ExecutionPolicy Bypass -File scripts/release.ps1 -Version 1.2.4
```

**What happens internally:**
1. Hard-smoke regression runs (licensing-aware)
2. PyInstaller builds the app
3. Public key is detected at `config/license_public_key.pem`
4. Public key is bundled into the release ZIP/EXE in the `config/` folder
5. Portable ZIP and installer EXE are created in `release/v1.2.4/`

### 2.2 Verify Public Key is in Release

```powershell
# After release, verify the public key was bundled
$zipPath = "release\v1.2.4\CafePOS-v1.2.4-win64.zip"
$tempExtract = "C:\temp\verify_zip"

if (Test-Path $tempExtract) { Remove-Item $tempExtract -Recurse -Force }
mkdir $tempExtract
Expand-Archive $zipPath -DestinationPath $tempExtract

# Check that public key exists
ls "$tempExtract\CafePOS\config\license_public_key.pem"
# ✓ If found, licensing is enabled in this release
# ✗ If missing, public key was not bundled (check config/license_public_key.pem exists before build)
```

## 3. License Issuance Workflow (For Customers)

Once a release with licensing is deployed:

### 3.1 Customer Requests License

Customer provides:
1. Machine ID (from app activation dialog or `python scripts/show_machine_id.py`)
2. Business name / customer name
3. License type (trial or permanent)
4. Trial duration (if trial)

### 3.2 Generate License Code (Owner)

```powershell
# For 30-day trial:
python scripts/generate_license_code.py \
  --private-key keys/license_private_key.pem \
  --kind trial \
  --customer "Break Time Cafe - Anna Nagar" \
  --machine-id "2BE0B188DDE1C85A9F4E3F3B083CAC638EAE5E2D8A052857ED5A0FD9520CEF68" \
  --license-id "CAFE-2026-0001" \
  --trial-days 30

# For permanent license:
python scripts/generate_license_code.py \
  --private-key keys/license_private_key.pem \
  --kind permanent \
  --customer "Break Time Cafe - Anna Nagar" \
  --machine-id "2BE0B188DDE1C85A9F4E3F3B083CAC638EAE5E2D8A052857ED5A0FD9520CEF68" \
  --license-id "CAFE-2026-PERM-0001"
```

**Output:** Long alphanumeric code starting with `CAFEPOS1-...`

### 3.3 Deliver Code to Customer

Send the generated code to the customer via:
- Email (recommended for audit)
- SMS
- Phone
- Support portal

Include instructions:
1. Open CafePOS application
2. At activation dialog, paste the code
3. Click "Activate"
4. App unlocks; database data is preserved

### 3.4 Record Issuance

Create a license register for your records:

| License ID | Customer | Machine ID | Kind | Issued | Expires | Notes |
|---|---|---|---|---|---|---|
| CAFE-2026-0001 | Break Time Cafe - Anna Nagar | 2BE0B188... | Trial (30d) | 2026-05-10 | 2026-06-09 | Initial evaluation |
| CAFE-2026-PERM-0001 | Break Time Cafe - Anna Nagar | 2BE0B188... | Permanent | 2026-06-15 | Never | Converted from trial |

## 4. Customer Reactivation Workflow

### 4.1 Trial Expiry

When a trial license expires:
- App shows "Trial has expired" at startup
- No data is deleted
- Customer must enter a new code (trial renewal or permanent upgrade)

### 4.2 Reissue Steps

```powershell
# Generate renewal code (same machine, new 30-day period)
python scripts/generate_license_code.py \
  --private-key keys/license_private_key.pem \
  --kind trial \
  --customer "Break Time Cafe - Anna Nagar" \
  --machine-id "2BE0B188DDE1C85A9F4E3F3B083CAC638EAE5E2D8A052857ED5A0FD9520CEF68" \
  --license-id "CAFE-2026-0002" \
  --trial-days 30
```

Send the new code to customer and they re-enter it.

## 5. Security Checklist for Releases

- [ ] Private key (`keys/license_private_key.pem`) is NOT in version control
- [ ] Private key is NOT included in release artifacts
- [ ] Public key (`config/license_public_key.pem`) IS included in release
- [ ] Release script logs indicate public key was bundled: `--add-data config/license_public_key.pem;config`
- [ ] Verify public key is in the final ZIP/EXE using tool from section 2.2
- [ ] License issuance register is maintained and secured
- [ ] Private key has encrypted backup in secure location
- [ ] Team understands: no sharing of private key, never commit to repo, handle code generation carefully

## 6. Troubleshooting

### "License public key is missing" at startup

**Cause:** Public key not bundled in the release ZIP or app installed from an old version.

**Solution:**
```powershell
# Rebuild the release (public key will be auto-detected and bundled)
python scripts/release.ps1 -Version 1.2.4

# Or manually bundle: Place config/license_public_key.pem in the app folder
# after extraction and before first launch.
```

### "License is bound to another machine"

**Cause:** License code was generated for a different Machine ID.

**Solution:**
- Ask customer for current machine ID
- Generate a new license code for their correct Machine ID
- Send updated code to customer

### "System clock rollback detected"

**Cause:** User set system clock backwards (tamper protection).

**Solution:**
- Correct system date/time
- App will unlock on next startup
- No re-activation required

## 7. Future Improvements

- [ ] Web portal for automated license issuance
- [ ] Subscription license type (auto-renew every N days)
- [ ] Version locking (require app >= version X)
- [ ] License key revocation list
- [ ] Audit log export for license compliance

---

**Last Updated:** 2026-05-10  
**Version:** v1.2.3+  
**Licensing System:** Offline Ed25519 signed keys
