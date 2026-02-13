"""ARC & BHS chain-related errors."""

from __future__ import annotations

from spv_wallet.errors.spv_errors import SPVError


class ARCError(SPVError):
    """Error from ARC transaction broadcaster."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message, status_code=status_code, code="arc-error")


class BHSError(SPVError):
    """Error from Block Headers Service."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message, status_code=status_code, code="bhs-error")
