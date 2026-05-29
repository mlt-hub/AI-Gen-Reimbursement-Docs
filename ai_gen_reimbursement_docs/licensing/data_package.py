"""Build and decrypt encrypted data packages."""

from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ._crypto import b64d, b64e
from .exceptions import DataPackageError

DATA_PACKAGE_FORMAT = "ard-data-v1"
DATA_PACKAGE_CIPHER = "AES-256-GCM"


@dataclass(frozen=True)
class DataPackageInfo:
    """Metadata returned after building a data package."""

    path: Path
    data_hash: str
    cek: bytes


def _sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _tar_directory(data_dir: Path) -> bytes:
    if not data_dir.exists() or not data_dir.is_dir():
        raise DataPackageError(f"data directory does not exist: {data_dir}")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:") as tar:
        for path in sorted(p for p in data_dir.rglob("*") if p.is_file()):
            arcname = path.relative_to(data_dir).as_posix()
            tar.add(path, arcname=arcname, recursive=False)
    return buf.getvalue()


def build_data_package(data_dir: Path, output: Path, *, cek: bytes | None = None) -> DataPackageInfo:
    """Encrypt ``data_dir`` into ``output`` using a random CEK.

    The returned CEK must be handled as sensitive material by the release
    process. It is intentionally not persisted unless callers choose to store it.
    """
    cek = cek or os.urandom(32)
    if len(cek) != 32:
        raise DataPackageError("CEK must be 32 bytes")

    plaintext = _tar_directory(data_dir)
    data_hash = _sha256_prefixed(plaintext)
    nonce = os.urandom(12)
    ciphertext = AESGCM(cek).encrypt(nonce, plaintext, None)

    package = {
        "format": DATA_PACKAGE_FORMAT,
        "cipher": DATA_PACKAGE_CIPHER,
        "nonce": b64e(nonce),
        "data_hash": data_hash,
        "ciphertext": b64e(ciphertext),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    return DataPackageInfo(path=output, data_hash=data_hash, cek=cek)


def read_data_package_metadata(path: Path) -> dict:
    """Read package metadata without decrypting ciphertext."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise DataPackageError(f"invalid data package: {path}") from exc

    if data.get("format") != DATA_PACKAGE_FORMAT:
        raise DataPackageError("unsupported data package format")
    if data.get("cipher") != DATA_PACKAGE_CIPHER:
        raise DataPackageError("unsupported data package cipher")
    if not isinstance(data.get("data_hash"), str):
        raise DataPackageError("data package missing data_hash")
    return data


def _safe_extract_tar(plaintext: bytes, output_dir: Path) -> None:
    output_root = output_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    with tarfile.open(fileobj=io.BytesIO(plaintext), mode="r:") as tar:
        members = tar.getmembers()
        for member in members:
            name = member.name
            normalized_name = name.replace("\\", "/")
            posix_name = PurePosixPath(normalized_name)
            if (
                not name
                or "\\" in name
                or ":" in name
                or posix_name.is_absolute()
                or any(part in ("", ".", "..") for part in posix_name.parts)
            ):
                raise DataPackageError(f"unsafe tar path: {name}")
            target = (output_root / Path(*posix_name.parts)).resolve()
            try:
                target.relative_to(output_root)
            except ValueError as exc:
                raise DataPackageError(f"unsafe tar path: {name}") from exc
            if member.issym() or member.islnk():
                raise DataPackageError(f"tar links are not allowed: {name}")
        tar.extractall(output_root, members=members)


def decrypt_data_package(path: Path, output_dir: Path, cek: bytes) -> str:
    """Decrypt ``path`` with ``cek`` and safely extract into ``output_dir``.

    Returns the plaintext tar SHA-256 hash in ``sha256:<hex>`` form.
    """
    if len(cek) != 32:
        raise DataPackageError("CEK must be 32 bytes")

    package = read_data_package_metadata(path)
    try:
        nonce = b64d(package["nonce"])
        ciphertext = b64d(package["ciphertext"])
        plaintext = AESGCM(cek).decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise DataPackageError("failed to decrypt data package") from exc

    data_hash = _sha256_prefixed(plaintext)
    if data_hash != package["data_hash"]:
        raise DataPackageError("data package hash mismatch")

    _safe_extract_tar(plaintext, output_dir)
    return data_hash
