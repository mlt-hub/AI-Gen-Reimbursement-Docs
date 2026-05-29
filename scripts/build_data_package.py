#!/usr/bin/env python
"""Build an encrypted ARD data package."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from ai_gen_reimbursement_docs.licensing import build_data_package


def main() -> int:
    parser = argparse.ArgumentParser(description="Encrypt data/ into data.enc")
    parser.add_argument("data_dir", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cek-out", type=Path, help="Write base64 CEK for license issuance")
    parser.add_argument("--metadata-out", type=Path, help="Write build metadata JSON")
    args = parser.parse_args()

    info = build_data_package(args.data_dir, args.output)
    cek_b64 = base64.b64encode(info.cek).decode("ascii")

    if args.cek_out:
        args.cek_out.parent.mkdir(parents=True, exist_ok=True)
        args.cek_out.write_text(cek_b64 + "\n", encoding="utf-8")

    metadata = {
        "data_package": str(info.path),
        "data_hash": info.data_hash,
        "cek_base64": cek_b64 if args.cek_out is None else None,
    }
    if args.metadata_out:
        args.metadata_out.parent.mkdir(parents=True, exist_ok=True)
        args.metadata_out.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(metadata, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
