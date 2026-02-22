"""Configuration dataclasses and validators for the starloom generator."""

from __future__ import annotations

from dataclasses import dataclass, field

from starloom.domain.types import ReproMode

# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

CONFIG_VERSION = "0.1"


class ConfigurationError(ValueError):
    """Raised when a GalaxyConfig fails validation."""


# ---------------------------------------------------------------------------
# Retry policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded retry counts for placement and generation operations."""

    max_coordinate_retries: int = 100
    max_name_retries: int = 50
    max_affinity_retries: int = 20

    def validate(self) -> None:
        for attr in ("max_coordinate_retries", "max_name_retries", "max_affinity_retries"):
            val = getattr(self, attr)
            if not isinstance(val, int) or val < 1:
                raise ConfigurationError(
                    f"CONFIG_OUT_OF_RANGE: {attr} must be a positive integer, got {val!r}"
                )


# ---------------------------------------------------------------------------
# System count + planet density
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SystemConfig:
    """Controls how many solar systems are generated and their placement."""

    count: int = 100
    # Galactic plane bounding box: systems are placed in [-bound, bound] on both axes.
    placement_bound: float = 1000.0
    # Number of decimal places used for quantized coordinate uniqueness checks.
    coordinate_precision_digits: int = 1

    def validate(self) -> None:
        if not isinstance(self.count, int) or self.count < 1:
            raise ConfigurationError(
                f"CONFIG_OUT_OF_RANGE: system count must be a positive integer, got {self.count!r}"
            )
        if self.placement_bound <= 0:
            raise ConfigurationError(
                f"CONFIG_OUT_OF_RANGE: placement_bound must be positive, got {self.placement_bound!r}"
            )
        if not isinstance(self.coordinate_precision_digits, int) or self.coordinate_precision_digits < 0:
            raise ConfigurationError(
                "CONFIG_OUT_OF_RANGE: coordinate_precision_digits must be a non-negative integer, "
                f"got {self.coordinate_precision_digits!r}"
            )


# ---------------------------------------------------------------------------
# Fallback policy
# ---------------------------------------------------------------------------


class FallbackPolicy(str):
    """Allow or raise on exhaustion of retries."""

    ALLOW = "allow"
    RAISE = "raise"

    def __new__(cls, value: str) -> "FallbackPolicy":
        if value not in (cls.ALLOW, cls.RAISE):
            raise ConfigurationError(
                f"CONFIG_INVALID_ENUM: fallback_policy must be 'allow' or 'raise', got {value!r}"
            )
        return super().__new__(cls, value)


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GalaxyConfig:
    """All configuration for a single generate_galaxy() call.

    All fields have safe defaults so ``GalaxyConfig()`` works out of the box.
    """

    version: str = CONFIG_VERSION
    repro_mode: ReproMode = ReproMode.COMPATIBLE
    strict: bool = False  # promote warnings to errors
    system: SystemConfig = field(default_factory=SystemConfig)
    retries: RetryPolicy = field(default_factory=RetryPolicy)
    fallback_policy: str = FallbackPolicy.RAISE
    # depth="galaxy" (full), "systems", "planets", "sectors", "locations", "nodes"
    depth: str = "galaxy"

    _VALID_DEPTHS: frozenset[str] = field(
        default=frozenset({"galaxy", "systems", "planets", "sectors", "locations", "nodes"}),
        init=False,
        repr=False,
        compare=False,
    )

    def validate(self) -> None:
        """Validate all sub-configs; raise ConfigurationError on first problem."""
        if self.depth not in self._VALID_DEPTHS:
            raise ConfigurationError(
                f"CONFIG_INVALID_ENUM: depth must be one of {sorted(self._VALID_DEPTHS)}, "
                f"got {self.depth!r}"
            )
        if self.fallback_policy not in (FallbackPolicy.ALLOW, FallbackPolicy.RAISE):
            raise ConfigurationError(
                f"CONFIG_INVALID_ENUM: fallback_policy must be 'allow' or 'raise', "
                f"got {self.fallback_policy!r}"
            )
        self.system.validate()
        self.retries.validate()
