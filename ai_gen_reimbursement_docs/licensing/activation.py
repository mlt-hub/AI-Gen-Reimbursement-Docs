"""Activation workflow and activation metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .data_package import decrypt_data_package, read_data_package_metadata
from .exceptions import ActivationError, LicenseMismatchError
from .license_file import LicensePayload, unwrap_cek, verify_license_file

ACTIVATION_FORMAT = "ard-activation-v1"


@dataclass(frozen=True)
class ActivationResult:
    """Result returned by successful activation."""

    license_id: str
    customer: str
    data_hash: str
    activation_path: Path


def default_activation_path() -> Path:
    return Path.home() / ".ai-gen-reimbursement-docs" / "license" / "activation.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _activation_valid(metadata: dict, data_hash: str, output_dir: Path) -> bool:
    if metadata.get("format") != ACTIVATION_FORMAT:
        return False
    if metadata.get("data_hash") != data_hash:
        return False
    expires_at = metadata.get("expires_at")
    if expires_at:
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if expires <= datetime.now(timezone.utc):
            return False
    return output_dir.exists() and any(output_dir.iterdir())


def is_activated(
    data_enc: Path,
    output_dir: Path,
    *,
    activation_path: Path | None = None,
) -> bool:
    """Return whether activation metadata matches the current data package."""
    activation_path = activation_path or default_activation_path()
    if not activation_path.exists():
        return False
    try:
        metadata = json.loads(activation_path.read_text(encoding="utf-8"))
        data_hash = read_data_package_metadata(data_enc)["data_hash"]
    except Exception:
        return False
    return _activation_valid(metadata, data_hash, output_dir)


def activate(
    *,
    license_path: Path,
    secret: str,
    data_enc: Path,
    output_dir: Path,
    public_key: Ed25519PublicKey,
    activation_path: Path | None = None,
) -> ActivationResult:
    """Verify license, decrypt the data package, and write activation metadata."""
    activation_path = activation_path or default_activation_path()
    payload = verify_license_file(license_path, public_key)
    return activate_verified_payload(
        payload=payload,
        secret=secret,
        data_enc=data_enc,
        output_dir=output_dir,
        activation_path=activation_path,
    )


def activate_verified_payload(
    *,
    payload: LicensePayload,
    secret: str,
    data_enc: Path,
    output_dir: Path,
    activation_path: Path | None = None,
) -> ActivationResult:
    """Activate from an already verified license payload."""
    activation_path = activation_path or default_activation_path()
    package_hash = read_data_package_metadata(data_enc)["data_hash"]
    if payload.get("data_hash") != package_hash:
        raise LicenseMismatchError("license does not match data package")

    cek = unwrap_cek(payload, secret)
    data_hash = decrypt_data_package(data_enc, output_dir, cek)
    if data_hash != package_hash:
        raise ActivationError("decrypted data hash does not match package")

    metadata = {
        "format": ACTIVATION_FORMAT,
        "license_id": payload["license_id"],
        "customer": payload["customer"],
        "data_hash": data_hash,
        "activated_at": _utc_now(),
        "expires_at": payload.get("expires_at"),
    }
    try:
        activation_path.parent.mkdir(parents=True, exist_ok=True)
        activation_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        raise ActivationError(f"failed to write activation metadata: {activation_path}") from exc

    return ActivationResult(
        license_id=payload["license_id"],
        customer=payload["customer"],
        data_hash=data_hash,
        activation_path=activation_path,
    )
