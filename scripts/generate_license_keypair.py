#!/usr/bin/env python
"""Generate an Ed25519 keypair for ARD license signing."""

from __future__ import annotations

import argparse
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Ed25519 license signing keys")
    parser.add_argument("--private-key", type=Path, default=Path("signing_private_key.pem"))
    parser.add_argument("--public-key", type=Path, default=Path("signing_public_key.pem"))
    args = parser.parse_args()

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    args.private_key.parent.mkdir(parents=True, exist_ok=True)
    args.public_key.parent.mkdir(parents=True, exist_ok=True)
    args.private_key.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    args.public_key.write_bytes(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print(f"private key: {args.private_key}")
    print(f"public key:  {args.public_key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
