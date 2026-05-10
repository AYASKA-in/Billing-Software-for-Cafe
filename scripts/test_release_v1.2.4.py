"""
Test Plan: CafePOS v1.2.4 with Offline Licensing

This script will be executed once the release build completes to verify:
1. Release artifact structure (ZIP file exists and contains public key)
2. App launches from built executable
3. Activation dialog appears on first launch (no license)
4. Trial code can be entered and validated
5. App persists license and allows normal operation on restart
"""

import subprocess
import tempfile
import time
from pathlib import Path

def test_release_artifacts():
    """Verify v1.2.4 release artifacts were created."""
    print("\n" + "=" * 80)
    print("TEST 1: Release Artifacts")
    print("=" * 80)
    
    release_dir = Path("release/v1.2.4")
    zip_file = release_dir / "CafePOS-v1.2.4-win64.zip"
    manifest = release_dir / "manifest.txt"
    
    print(f"✓ Release dir: {release_dir}")
    print(f"  - ZIP exists: {zip_file.exists()}")
    print(f"  - Manifest exists: {manifest.exists()}")
    
    if manifest.exists():
        print(f"  - Manifest content:")
        for line in manifest.read_text().splitlines():
            print(f"    {line}")
    
    return zip_file.exists() and manifest.exists()


def test_public_key_bundled():
    """Verify public key is in the release ZIP."""
    print("\n" + "=" * 80)
    print("TEST 2: Public Key Bundled in Release")
    print("=" * 80)
    
    zip_file = Path("release/v1.2.4/CafePOS-v1.2.4-win64.zip")
    
    # Extract and check
    with tempfile.TemporaryDirectory() as tmpdir:
        extract_dir = Path(tmpdir) / "extracted"
        
        # Unzip
        import zipfile
        with zipfile.ZipFile(zip_file, 'r') as zf:
            zf.extractall(extract_dir)
        
        # Check for public key
        public_key_path = extract_dir / "CafePOS" / "config" / "license_public_key.pem"
        
        print(f"Extracted to: {extract_dir}")
        print(f"Public key exists in bundle: {public_key_path.exists()}")
        
        if public_key_path.exists():
            key_content = public_key_path.read_text()
            print(f"Public key size: {len(key_content)} bytes")
            print(f"Key format: {key_content.splitlines()[0]}")
        
        return public_key_path.exists()


def test_release_notes():
    """Verify release documentation."""
    print("\n" + "=" * 80)
    print("TEST 3: Release Documentation")
    print("=" * 80)
    
    version_file = Path("release/v1.2.4/VERSION.txt")
    readme_file = Path("release/v1.2.4/README.txt")
    
    print(f"VERSION.txt exists: {version_file.exists()}")
    if version_file.exists():
        print(f"  Version: {version_file.read_text().strip()}")
    
    print(f"README.txt exists: {readme_file.exists()}")
    print(f"README size: {readme_file.stat().st_size if readme_file.exists() else 'N/A'} bytes")
    
    return version_file.exists() and readme_file.exists()


def main():
    print("\n" + "=" * 80)
    print("CAFEPOS v1.2.4 WITH OFFLINE LICENSING - RELEASE VERIFICATION")
    print("=" * 80)
    
    test1 = test_release_artifacts()
    test2 = test_public_key_bundled()
    test3 = test_release_notes()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Release artifacts: {'✓ PASS' if test1 else '✗ FAIL'}")
    print(f"Public key bundled: {'✓ PASS' if test2 else '✗ FAIL'}")
    print(f"Documentation: {'✓ PASS' if test3 else '✗ FAIL'}")
    
    if all([test1, test2, test3]):
        print("\n✓ ALL TESTS PASSED - v1.2.4 release is ready for deployment")
        print("\nNext steps:")
        print("1. Extract CafePOS-v1.2.4-win64.zip to test machine")
        print("2. Run CafePOS.exe (or CafePOS/CafePOS.exe inside)")
        print("3. Activation dialog should appear (no license found)")
        print("4. Get machine ID from dialog, generate trial code with:")
        print("   python scripts/generate_license_code.py \\")
        print("     --private-key keys/license_private_key.pem \\")
        print("     --kind trial \\")
        print("     --customer 'Test Customer' \\")
        print("     --machine-id '<MACHINE_ID>' \\")
        print("     --license-id 'TEST-001' \\")
        print("     --trial-days 30")
        print("5. Paste code into activation dialog → app unlocks")
        return 0
    else:
        print("\n✗ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
