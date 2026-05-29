"""Offline licensing and protected data activation helpers."""

from .activation import ActivationResult, activate, activate_verified_payload, is_activated
from .data_package import DataPackageInfo, build_data_package, decrypt_data_package
from .exceptions import (
    ActivationError,
    DataPackageError,
    LicenseExpiredError,
    LicenseInvalidError,
    LicenseMismatchError,
    LicensingError,
)
from .license_file import (
    LicensePayload,
    create_license,
    generate_license_secret,
    load_public_key,
    verify_license_file,
)

__all__ = [
    "ActivationError",
    "ActivationResult",
    "DataPackageError",
    "DataPackageInfo",
    "LicenseExpiredError",
    "LicenseInvalidError",
    "LicenseMismatchError",
    "LicensePayload",
    "LicensingError",
    "activate",
    "activate_verified_payload",
    "build_data_package",
    "create_license",
    "decrypt_data_package",
    "generate_license_secret",
    "is_activated",
    "load_public_key",
    "verify_license_file",
]
