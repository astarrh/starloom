"""Typed generation exceptions with stable error codes (design doc §11.1, §13.2)."""

from __future__ import annotations


class GenerationError(RuntimeError):
    """Base class for all generation-time failures."""

    code: str = "GENERATION_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class PlacementExhaustedError(GenerationError):
    """Raised when coordinate placement retries are exhausted (PLACEMENT_EXHAUSTED)."""

    code = "PLACEMENT_EXHAUSTED"


class NameGenerationExhaustedError(GenerationError):
    """Raised when name generation retries are exhausted (NAME_GENERATION_EXHAUSTED)."""

    code = "NAME_GENERATION_EXHAUSTED"


class EligibilityExhaustedError(GenerationError):
    """Raised when no eligible type remains after filtering (ELIGIBILITY_EXHAUSTED)."""

    code = "ELIGIBILITY_EXHAUSTED"


class GenerationConstraintError(GenerationError):
    """Raised when post-generation structural constraints are violated."""

    code = "GENERATION_CONSTRAINT_ERROR"
