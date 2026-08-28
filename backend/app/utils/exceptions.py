"""Custom exceptions for FBA Sourcer."""


class FBASourcingError(Exception):
    """Base exception for this application."""

    pass


class ToolExecutionError(FBASourcingError):
    """Tool failed to execute."""

    pass


class APIError(FBASourcingError):
    """External API error (Keepa, Claude, etc)."""

    pass


class ValidationError(FBASourcingError):
    """Data validation failed."""

    pass


class ConfigurationError(FBASourcingError):
    """Missing or invalid configuration."""

    pass