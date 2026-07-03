"""Exceptions for Lemonade Conversation Advanced."""

from __future__ import annotations


class LemonadeError(Exception):
    """Base exception for Lemonade errors."""

    def __init__(self, message: str, status_code: int | None = None):
        """Initialize the exception."""
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class LemonadeConnectionError(LemonadeError):
    """Error when connection to Lemonade Server fails."""

    def __init__(self, message: str = "Failed to connect to Lemonade Server"):
        super().__init__(message)


class LemonadeAPIError(LemonadeError):
    """Error returned by Lemonade Server API."""

    def __init__(self, message: str, status_code: int, response: dict | None = None):
        super().__init__(message, status_code)
        self.response = response


class LemonadeModelError(LemonadeError):
    """Error related to model operations (not found, not loaded, etc.)."""

    def __init__(self, message: str, model_name: str | None = None):
        super().__init__(message)
        self.model_name = model_name


class LemonadeModelNotFoundError(LemonadeModelError):
    """Model not found in registry or not downloaded."""

    def __init__(self, model_name: str):
        super().__init__(f"Model '{model_name}' not found", model_name)


class LemonadeModelNotLoadedError(LemonadeModelError):
    """Model not loaded in memory."""

    def __init__(self, model_name: str):
        super().__init__(f"Model '{model_name}' not loaded in memory", model_name)


class LemonadeHardwareError(LemonadeError):
    """Hardware-related errors (NPU busy, OOM, etc.)."""

    def __init__(self, message: str, hardware_type: str | None = None):
        super().__init__(message)
        self.hardware_type = hardware_type


class LemonadeNPUBusyError(LemonadeHardwareError):
    """NPU is busy with another model."""

    def __init__(self, model_name: str | None = None):
        msg = "NPU is busy"
        if model_name:
            msg += f" (model: {model_name})"
        super().__init__(msg, "NPU")


class LemonadeOutOfMemoryError(LemonadeHardwareError):
    """Out of VRAM/RAM memory."""

    def __init__(self, device: str = "GPU"):
        super().__init__(f"Out of memory on {device}", device)


class LemonadeBackendUnavailableError(LemonadeError):
    """Requested backend is not available."""

    def __init__(self, backend: str):
        super().__init__(f"Backend '{backend}' is not available")


class LemonadeInvalidRequestError(LemonadeError):
    """Invalid request parameters."""

    def __init__(self, message: str):
        super().__init__(message)
