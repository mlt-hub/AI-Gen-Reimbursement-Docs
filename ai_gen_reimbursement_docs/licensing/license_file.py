"""License creation, signing, verification, and CEK wrapping."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from ._crypto import b64d, b64e, b64url_secret, canonical_json_bytes, load_public_key
from .exceptions import LicenseExpiredError, LicenseInvalidError

LICENSE_FORMAT = "ard-license-v1"
LICENSE_SIGNATURE_ALG = "Ed25519"
WRAPPED_KEY_ALG = "AES-256-GCM"
WRAPPED_KEY_KDF = "scrypt"
DEFAULT_SCRYPT_N = 2**14
DEFAULT_SCRYPT_R = 8
DEFAULT_SCRYPT_P = 1


class LicensePayload(TypedDict, total=False):
    format: str
    license_id: str
    customer: str
    issued_at: str
    expires_at: str | None
    data_hash: str
    features: list[str]
    wrapped_key: dict[str, Any]


def generate_license_secret() -> str:
    """Return a high-entropy URL-safe secret for offline license activation."""
    return b64url_secret(os.urandom(32))


def _derive_kek(secret: str, salt: bytes, *, n: int, r: int, p: int) -> bytes:
    return Scrypt(salt=salt, length=32, n=n, r=r, p=p).derive(secret.strip().encode("utf-8"))


def _wrap_cek(
    cek: bytes,
    secret: str,
    *,
    scrypt_n: int = DEFAULT_SCRYPT_N,
    scrypt_r: int = DEFAULT_SCRYPT_R,
    scrypt_p: int = DEFAULT_SCRYPT_P,
) -> dict[str, Any]:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    kek = _derive_kek(secret, salt, n=scrypt_n, r=scrypt_r, p=scrypt_p)
    ciphertext = AESGCM(kek).encrypt(nonce, cek, None)
    return {
        "alg": WRAPPED_KEY_ALG,
        "kdf": WRAPPED_KEY_KDF,
        "salt": b64e(salt),
        "nonce": b64e(nonce),
        "ciphertext": b64e(ciphertext),
        "scrypt": {
            "n": scrypt_n,
            "r": scrypt_r,
            "p": scrypt_p,
        },
    }


def unwrap_cek(payload: LicensePayload, secret: str) -> bytes:
    """Recover the CEK from a verified license payload and customer secret."""
    wrapped = payload.get("wrapped_key")
    if not isinstance(wrapped, dict):
        raise LicenseInvalidError("license missing wrapped_key")
    if wrapped.get("alg") != WRAPPED_KEY_ALG or wrapped.get("kdf") != WRAPPED_KEY_KDF:
        raise LicenseInvalidError("unsupported wrapped key format")

    scrypt_params = wrapped.get("scrypt") or {}
    try:
        salt = b64d(wrapped["salt"])
        nonce = b64d(wrapped["nonce"])
        ciphertext = b64d(wrapped["ciphertext"])
        kek = _derive_kek(
            secret,
            salt,
            n=int(scrypt_params.get("n", DEFAULT_SCRYPT_N)),
            r=int(scrypt_params.get("r", DEFAULT_SCRYPT_R)),
            p=int(scrypt_params.get("p", DEFAULT_SCRYPT_P)),
        )
        cek = AESGCM(kek).decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise LicenseInvalidError("failed to unwrap CEK") from exc

    if len(cek) != 32:
        raise LicenseInvalidError("invalid CEK length")
    return cek


def create_license(
    *,
    private_key: Ed25519PrivateKey,
    license_id: str,
    customer: str,
    data_hash: str,
    cek: bytes,
    secret: str,
    features: list[str] | None = None,
    issued_at: str | None = None,
    expires_at: str | None = None,
    scrypt_n: int = DEFAULT_SCRYPT_N,
) -> dict[str, Any]:
    """Create and sign a license document."""
    if len(cek) != 32:
        raise LicenseInvalidError("CEK must be 32 bytes")
    payload: LicensePayload = {
        "format": LICENSE_FORMAT,
        "license_id": license_id,
        "customer": customer,
        "issued_at": issued_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at,
        "data_hash": data_hash,
        "features": features or ["data:default"],
        "wrapped_key": _wrap_cek(cek, secret, scrypt_n=scrypt_n),
    }
    signature = private_key.sign(canonical_json_bytes(payload))
    return {
        "payload": payload,
        "signature": {
            "alg": LICENSE_SIGNATURE_ALG,
            "value": b64e(signature),
        },
    }


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _assert_not_expired(payload: LicensePayload, *, now: datetime | None = None) -> None:
    expires_at = payload.get("expires_at")
    if not expires_at:
        return
    now = now or datetime.now(timezone.utc)
    if _parse_datetime(expires_at) <= now:
        raise LicenseExpiredError("license is expired")


def verify_license_doc(
    doc: dict[str, Any],
    public_key: Ed25519PublicKey,
    *,
    now: datetime | None = None,
) -> LicensePayload:
    """Verify a parsed license document and return its payload."""
    try:
        payload = doc["payload"]
        signature_doc = doc["signature"]
        if payload.get("format") != LICENSE_FORMAT:
            raise LicenseInvalidError("unsupported license format")
        if signature_doc.get("alg") != LICENSE_SIGNATURE_ALG:
            raise LicenseInvalidError("unsupported signature algorithm")
        signature = b64d(signature_doc["value"])
        public_key.verify(signature, canonical_json_bytes(payload))
    except LicenseInvalidError:
        raise
    except Exception as exc:
        raise LicenseInvalidError("invalid license signature") from exc

    _assert_not_expired(payload, now=now)
    return payload


def verify_license_file(
    path: Path,
    public_key: Ed25519PublicKey,
    *,
    now: datetime | None = None,
) -> LicensePayload:
    """Read and verify a license file."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise LicenseInvalidError(f"invalid license file: {path}") from exc
    return verify_license_doc(doc, public_key, now=now)


def write_license_file(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
