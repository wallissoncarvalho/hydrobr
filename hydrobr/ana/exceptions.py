"""Exceptions raised by the ANA clients."""


class ANAError(Exception):
    """Base exception for ANA integrations."""


class ANAAuthenticationError(ANAError):
    """Raised when HidroWebService credentials are rejected."""


class ANAServiceUnavailableError(ANAError):
    """Raised when the legacy service is unavailable and credentials are needed."""


class ANAResponseError(ANAError):
    """Raised when an ANA service returns an invalid or unsuccessful response."""
