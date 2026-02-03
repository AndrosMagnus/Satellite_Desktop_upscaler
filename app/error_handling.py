from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UserFacingError(Exception):
    title: str
    summary: str
    suggested_fixes: tuple[str, ...] = ()
    error_code: str = "APP-000"
    can_retry: bool = True

    def __str__(self) -> str:
        return f"{self.summary} (code {self.error_code})"


def as_user_facing_error(exc: Exception) -> UserFacingError:
    if isinstance(exc, UserFacingError):
        return exc

    if isinstance(exc, FileNotFoundError):
        return UserFacingError(
            title="File not found",
            summary="We couldn't find one of the files needed for this run.",
            suggested_fixes=(
                "Verify the file still exists in its original location.",
                "Re-add the file to the list and try again.",
            ),
            error_code="IO-001",
            can_retry=True,
        )

    if isinstance(exc, PermissionError):
        return UserFacingError(
            title="Access denied",
            summary="We don't have permission to read one of the selected files.",
            suggested_fixes=(
                "Move the file to a readable location.",
                "Check file permissions and try again.",
            ),
            error_code="IO-002",
            can_retry=True,
        )

    return UserFacingError(
        title="Something went wrong",
        summary="We couldn't complete the request.",
        suggested_fixes=(
            "Try again in a moment.",
            "If the issue persists, check the logs for details.",
        ),
        error_code="APP-001",
        can_retry=True,
    )
