import io
import json
import os
import tarfile
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ai_gen_reimbursement_docs.licensing import (
    ActivationError,
    DataPackageError,
    LicenseExpiredError,
    LicenseInvalidError,
    LicenseMismatchError,
    activate,
    activate_verified_payload,
    build_data_package,
    create_license,
    generate_license_secret,
    is_activated,
)
from ai_gen_reimbursement_docs.licensing._crypto import b64e
from ai_gen_reimbursement_docs.licensing.data_package import DATA_PACKAGE_CIPHER, DATA_PACKAGE_FORMAT
from ai_gen_reimbursement_docs.licensing.license_file import verify_license_doc, write_license_file


def _sample_data_dir(tmp_path):
    data_dir = tmp_path / "data-src"
    data_dir.mkdir()
    (data_dir / "alpha.txt").write_text("alpha", encoding="utf-8")
    nested = data_dir / "nested"
    nested.mkdir()
    (nested / "beta.txt").write_text("beta", encoding="utf-8")
    return data_dir


def _license_doc(private_key, info, *, secret=None, expires_at=None):
    secret = secret or generate_license_secret()
    doc = create_license(
        private_key=private_key,
        license_id="lic_test",
        customer="test customer",
        data_hash=info.data_hash,
        cek=info.cek,
        secret=secret,
        expires_at=expires_at,
        scrypt_n=2**10,
    )
    return doc, secret


def test_activation_roundtrip_writes_metadata_and_extracts_data(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    data_package = tmp_path / "data.enc"
    info = build_data_package(_sample_data_dir(tmp_path), data_package)
    doc, secret = _license_doc(private_key, info)
    license_path = tmp_path / "license.ard.json"
    write_license_file(license_path, doc)
    output_dir = tmp_path / "out"
    activation_path = tmp_path / "activation.json"

    result = activate(
        license_path=license_path,
        secret=secret,
        data_enc=data_package,
        output_dir=output_dir,
        public_key=private_key.public_key(),
        activation_path=activation_path,
    )

    assert result.license_id == "lic_test"
    assert (output_dir / "alpha.txt").read_text(encoding="utf-8") == "alpha"
    assert (output_dir / "nested" / "beta.txt").read_text(encoding="utf-8") == "beta"
    assert is_activated(data_package, output_dir, activation_path=activation_path) is True


def test_activation_from_verified_payload_roundtrip(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    data_package = tmp_path / "data.enc"
    info = build_data_package(_sample_data_dir(tmp_path), data_package)
    doc, secret = _license_doc(private_key, info)
    payload = verify_license_doc(doc, private_key.public_key())
    output_dir = tmp_path / "out"
    activation_path = tmp_path / "activation.json"

    result = activate_verified_payload(
        payload=payload,
        secret=secret,
        data_enc=data_package,
        output_dir=output_dir,
        activation_path=activation_path,
    )

    assert result.license_id == "lic_test"
    assert (output_dir / "alpha.txt").read_text(encoding="utf-8") == "alpha"
    assert is_activated(data_package, output_dir, activation_path=activation_path) is True


def test_license_payload_tampering_fails_verification(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    info = build_data_package(_sample_data_dir(tmp_path), tmp_path / "data.enc")
    doc, _secret = _license_doc(private_key, info)
    doc["payload"]["customer"] = "attacker"

    with pytest.raises(LicenseInvalidError):
        verify_license_doc(doc, private_key.public_key())


def test_license_signature_tampering_fails_verification(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    info = build_data_package(_sample_data_dir(tmp_path), tmp_path / "data.enc")
    doc, _secret = _license_doc(private_key, info)
    doc["signature"]["value"] = b64e(b"0" * 64)

    with pytest.raises(LicenseInvalidError):
        verify_license_doc(doc, private_key.public_key())


def test_expired_license_fails_activation(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    data_package = tmp_path / "data.enc"
    info = build_data_package(_sample_data_dir(tmp_path), data_package)
    expired = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    doc, secret = _license_doc(private_key, info, expires_at=expired)
    license_path = tmp_path / "license.ard.json"
    write_license_file(license_path, doc)

    with pytest.raises(LicenseExpiredError):
        activate(
            license_path=license_path,
            secret=secret,
            data_enc=data_package,
            output_dir=tmp_path / "out",
            public_key=private_key.public_key(),
            activation_path=tmp_path / "activation.json",
        )


def test_data_hash_mismatch_fails_activation(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    info = build_data_package(_sample_data_dir(tmp_path), tmp_path / "data-a.enc")
    other_package = tmp_path / "data-b.enc"
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    (other_dir / "other.txt").write_text("other", encoding="utf-8")
    build_data_package(other_dir, other_package)
    doc, secret = _license_doc(private_key, info)
    license_path = tmp_path / "license.ard.json"
    write_license_file(license_path, doc)

    with pytest.raises(LicenseMismatchError):
        activate(
            license_path=license_path,
            secret=secret,
            data_enc=other_package,
            output_dir=tmp_path / "out",
            public_key=private_key.public_key(),
            activation_path=tmp_path / "activation.json",
        )


def test_wrong_secret_fails_activation(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    data_package = tmp_path / "data.enc"
    info = build_data_package(_sample_data_dir(tmp_path), data_package)
    doc, _secret = _license_doc(private_key, info)
    license_path = tmp_path / "license.ard.json"
    write_license_file(license_path, doc)

    with pytest.raises(LicenseInvalidError):
        activate(
            license_path=license_path,
            secret="wrong-secret",
            data_enc=data_package,
            output_dir=tmp_path / "out",
            public_key=private_key.public_key(),
            activation_path=tmp_path / "activation.json",
        )


def test_activation_metadata_write_failure_is_activation_error(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    data_package = tmp_path / "data.enc"
    info = build_data_package(_sample_data_dir(tmp_path), data_package)
    doc, secret = _license_doc(private_key, info)
    license_path = tmp_path / "license.ard.json"
    write_license_file(license_path, doc)
    blocked_parent = tmp_path / "blocked-parent"
    blocked_parent.write_text("not a directory", encoding="utf-8")

    with pytest.raises(ActivationError):
        activate(
            license_path=license_path,
            secret=secret,
            data_enc=data_package,
            output_dir=tmp_path / "out",
            public_key=private_key.public_key(),
            activation_path=blocked_parent / "activation.json",
        )


def test_tampered_ciphertext_fails_activation(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    data_package = tmp_path / "data.enc"
    info = build_data_package(_sample_data_dir(tmp_path), data_package)
    package = json.loads(data_package.read_text(encoding="utf-8"))
    package["ciphertext"] = b64e(b"tampered")
    data_package.write_text(json.dumps(package), encoding="utf-8")
    doc, secret = _license_doc(private_key, info)
    license_path = tmp_path / "license.ard.json"
    write_license_file(license_path, doc)

    with pytest.raises(DataPackageError):
        activate(
            license_path=license_path,
            secret=secret,
            data_enc=data_package,
            output_dir=tmp_path / "out",
            public_key=private_key.public_key(),
            activation_path=tmp_path / "activation.json",
        )


def _malicious_package(tmp_path, cek, member_name, *, symlink=False, hardlink=False):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:") as tar:
        info = tarfile.TarInfo(member_name)
        if symlink:
            info.type = tarfile.SYMTYPE
            info.linkname = "target"
            tar.addfile(info)
        elif hardlink:
            info.type = tarfile.LNKTYPE
            info.linkname = "target"
            tar.addfile(info)
        else:
            content = b"evil"
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    plaintext = buf.getvalue()
    nonce = os.urandom(12)
    ciphertext = AESGCM(cek).encrypt(nonce, plaintext, None)
    data_hash = "sha256:" + __import__("hashlib").sha256(plaintext).hexdigest()
    path = tmp_path / "malicious.enc"
    path.write_text(json.dumps({
        "format": DATA_PACKAGE_FORMAT,
        "cipher": DATA_PACKAGE_CIPHER,
        "nonce": b64e(nonce),
        "data_hash": data_hash,
        "ciphertext": b64e(ciphertext),
    }), encoding="utf-8")
    return path, data_hash


def test_safe_extract_rejects_path_traversal(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    cek = os.urandom(32)
    data_package, data_hash = _malicious_package(tmp_path, cek, "../evil.txt")
    secret = generate_license_secret()
    doc = create_license(
        private_key=private_key,
        license_id="lic_test",
        customer="test",
        data_hash=data_hash,
        cek=cek,
        secret=secret,
        scrypt_n=2**10,
    )
    license_path = tmp_path / "license.ard.json"
    write_license_file(license_path, doc)

    with pytest.raises(DataPackageError):
        activate(
            license_path=license_path,
            secret=secret,
            data_enc=data_package,
            output_dir=tmp_path / "out",
            public_key=private_key.public_key(),
            activation_path=tmp_path / "activation.json",
        )


def test_safe_extract_rejects_absolute_path(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    cek = os.urandom(32)
    data_package, data_hash = _malicious_package(tmp_path, cek, "/evil.txt")
    secret = generate_license_secret()
    doc = create_license(
        private_key=private_key,
        license_id="lic_test",
        customer="test",
        data_hash=data_hash,
        cek=cek,
        secret=secret,
        scrypt_n=2**10,
    )
    license_path = tmp_path / "license.ard.json"
    write_license_file(license_path, doc)

    with pytest.raises(DataPackageError):
        activate(
            license_path=license_path,
            secret=secret,
            data_enc=data_package,
            output_dir=tmp_path / "out",
            public_key=private_key.public_key(),
            activation_path=tmp_path / "activation.json",
        )


def test_safe_extract_rejects_symlink(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    cek = os.urandom(32)
    data_package, data_hash = _malicious_package(tmp_path, cek, "link", symlink=True)
    secret = generate_license_secret()
    doc = create_license(
        private_key=private_key,
        license_id="lic_test",
        customer="test",
        data_hash=data_hash,
        cek=cek,
        secret=secret,
        scrypt_n=2**10,
    )
    license_path = tmp_path / "license.ard.json"
    write_license_file(license_path, doc)

    with pytest.raises(DataPackageError):
        activate(
            license_path=license_path,
            secret=secret,
            data_enc=data_package,
            output_dir=tmp_path / "out",
            public_key=private_key.public_key(),
            activation_path=tmp_path / "activation.json",
        )


def test_safe_extract_rejects_hardlink(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    cek = os.urandom(32)
    data_package, data_hash = _malicious_package(tmp_path, cek, "link", hardlink=True)
    secret = generate_license_secret()
    doc = create_license(
        private_key=private_key,
        license_id="lic_test",
        customer="test",
        data_hash=data_hash,
        cek=cek,
        secret=secret,
        scrypt_n=2**10,
    )
    license_path = tmp_path / "license.ard.json"
    write_license_file(license_path, doc)

    with pytest.raises(DataPackageError):
        activate(
            license_path=license_path,
            secret=secret,
            data_enc=data_package,
            output_dir=tmp_path / "out",
            public_key=private_key.public_key(),
            activation_path=tmp_path / "activation.json",
        )
