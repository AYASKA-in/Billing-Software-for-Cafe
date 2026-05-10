from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.licensing import generate_ed25519_keypair


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Ed25519 key pair for offline licensing.")
    parser.add_argument("--out-dir", default="keys", help="Output folder for key files")
    parser.add_argument(
        "--public-copy",
        default="config/license_public_key.pem",
        help="Where to copy the public key for app verification",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    private_pem, public_pem = generate_ed25519_keypair()

    private_path = out_dir / "license_private_key.pem"
    public_path = out_dir / "license_public_key.pem"
    app_public_path = Path(args.public_copy)
    app_public_path.parent.mkdir(parents=True, exist_ok=True)

    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)
    app_public_path.write_bytes(public_pem)

    print("License key pair generated.")
    print(f"Private key: {private_path}")
    print(f"Public key:  {public_path}")
    print(f"App public key copied to: {app_public_path}")
    print("IMPORTANT: Keep private key secret and never ship it with the app.")


if __name__ == "__main__":
    main()
