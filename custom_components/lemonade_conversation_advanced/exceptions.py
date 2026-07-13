"""Exceptions for Lemonade Conversation Advanced integration."""

from homeassistant.exceptions import HomeAssistantError


class LemonadeException(HomeAssistantError):
    """Base exception for Lemonade integration."""


class LemonadeConnectionError(LemonadeException):
    """Raised when connection to Lemonade server fails."""


class LemonadeAuthError(LemonadeException):
    """Raised when authentication with Lemonade server fails."""


class LemonadeAPIError(LemonadeException):
    """Raised when Lemonade server returns an error response."""


class LemonadeTimeoutError(LemonadeException):
    """Raised when request to Lemonade server times out."""


class LemonadeConfigurationError(LemonadeException):
    """Raised when configuration is invalid."""


class LemonadeModelNotFoundError(LemonadeException):
    """Raised when requested model is not available."""


class LemonadeInvalidResponseError(LemonadeException):
    """Raised when Lemonade returns an invalid/unexpected response."""
