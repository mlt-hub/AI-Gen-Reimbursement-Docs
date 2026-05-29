"""Exceptions raised by the licensing subsystem."""


class LicensingError(Exception):
    """Base class for licensing failures."""


class LicenseInvalidError(LicensingError):
    """The license file, signature, or secret is invalid."""


class LicenseExpiredError(LicensingError):
    """The license is expired."""


class LicenseMismatchError(LicensingError):
    """The license does not match the current data package."""


class DataPackageError(LicensingError):
    """The encrypted data package is invalid or cannot be unpacked safely."""


class ActivationError(LicensingError):
    """Activation metadata is invalid or activation failed."""
