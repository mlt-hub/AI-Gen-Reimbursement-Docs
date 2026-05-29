#!/usr/bin/env python
"""Issue an offline ARD license for a data package."""

from __future__ import annotations

import argparse
import base64
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from ai_gen_reimbursement_docs.licensing.data_package import read_data_package_metadata
from ai_gen_reimbursement_docs.licensing.license_file import (
    create_license,
    generate_license_secret,
    write_license_file,
)
from ai_gen_reimbursement_docs.licensing._crypto import load_private_key


def _read_cek(path: Path) -> bytes:
    try:
        return base64.b64decode(path.read_text(encoding="utf-8").strip(), validate=True)
    except Exception as exc:
        raise SystemExit(f"invalid CEK file: {path}") from exc


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_issue_record(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Issue a signed ARD license")
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--data-package", type=Path, required=True)
    parser.add_argument("--cek-file", type=Path, required=True)
    parser.add_argument("--customer", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--license-id", default="")
    parser.add_argument("--expires-at", default=None, help="ISO datetime, or omit for no expiry")
    parser.add_argument("--feature", action="append", dest="features")
    parser.add_argument("--secret-out", type=Path)
    parser.add_argument("--scrypt-n", type=int, default=2**14)
    parser.add_argument("--issued-record", type=Path, help="Append non-secret issue metadata as JSONL")
    args = parser.parse_args()

    secret = generate_license_secret()
    license_id = args.license_id or f"lic_{secrets.token_hex(8)}"
    package = read_data_package_metadata(args.data_package)
    doc = create_license(
        private_key=load_private_key(args.private_key),
        license_id=license_id,
        customer=args.customer,
        data_hash=package["data_hash"],
        cek=_read_cek(args.cek_file),
        secret=secret,
        features=args.features,
        expires_at=args.expires_at,
        scrypt_n=args.scrypt_n,
    )
    write_license_file(args.output, doc)

    if args.secret_out:
        args.secret_out.parent.mkdir(parents=True, exist_ok=True)
        args.secret_out.write_text(secret + "\n", encoding="utf-8")

    if args.issued_record:
        _append_issue_record(args.issued_record, {
            "issued_at": _utc_now(),
            "license_id": license_id,
            "customer": args.customer,
            "license": str(args.output),
            "data_package": str(args.data_package),
            "data_hash": package["data_hash"],
            "expires_at": args.expires_at,
            "features": args.features or ["data:default"],
        })

    print(json.dumps({
        "license": str(args.output),
        "license_id": license_id,
        "customer": args.customer,
        "secret": secret if args.secret_out is None else None,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
