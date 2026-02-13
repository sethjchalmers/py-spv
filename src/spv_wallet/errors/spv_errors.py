"""SPVError — base exception class for all py-spv errors."""

from __future__ import annotations


class SPVError(Exception):
    """Base error for all SPV wallet operations.

    Attributes:
        message: Human-readable error description.
        status_code: Suggested HTTP status code.
        code: Machine-readable error code string.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        code: str = "spv-error",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
