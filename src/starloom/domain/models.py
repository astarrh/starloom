"""Immutable domain dataclasses for starloom."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from starloom.domain.types import (
    ClimateType,
    LocationType,
    NameStyle,
    NodeType,
    PlanetClass,
    Severity,
    Size,
    TopographyType,
    ValidationStage,
)


# ---------------------------------------------------------------------------
# Culture
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StyleConfig:
    """Per-style name generation settings for a Culture."""

    min_length: int = 4
    max_length: int = 12
    template: str | None = None  # e.g. "The +" or "+ & +"


@dataclass(frozen=True)
class Culture:
    """Runtime culture object.  Owned by the developer; passed as input to the generator."""

    id: str
    name: str
    # Opaque trained Markov model payload — a dict produced by culture/markov.py.
    markov_model: dict[str, Any] = field(default_factory=dict)
    name_styles: dict[NameStyle, StyleConfig] = field(default_factory=dict)
    # origin examples, drift value, parent_culture_id, etc.
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CultureSpec:
    """Serialisable culture descriptor stored in Galaxy.cultures.

    Unlike Culture, this holds a JSON-compatible model payload rather than a
    live runtime object so the Galaxy output is self-describing.
    """

    id: str
    name: str
    markov_model_data: dict[str, Any] = field(default_factory=dict)
    name_styles: dict[NameStyle, StyleConfig] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_runtime(self) -> Culture:
        """Reconstruct a runtime Culture from this spec."""
        return Culture(
            id=self.id,
            name=self.name,
            markov_model=self.markov_model_data,
            name_styles=self.name_styles,
            metadata=self.metadata,
        )


@dataclass(frozen=True)
class CultureFamily:
    """A group of related Culture objects derived from the same example set."""

    id: str
    name: str
    cultures: tuple[Culture, ...]
    base_examples: tuple[str, ...]  # minimum 4, recommended 8–15
    seed: int | None = None  # set when procedurally generated


# ---------------------------------------------------------------------------
# World hierarchy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Node:
    """A point-of-interest within a Location."""

    id: str
    name: str
    node_type: NodeType
    in_town: bool
    distinctiveness: float  # 0.0–1.0


@dataclass(frozen=True)
class Location:
    """A settlement or landmark within a Sector."""

    id: str
    name: str
    location_type: LocationType
    size: Size
    features: tuple[str, ...]
    distinctiveness: float  # 0.0–1.0
    nodes: tuple[Node, ...]


@dataclass(frozen=True)
class Sector:
    """A region on a Planet defined by a topography × climate combination."""

    id: str
    name: str
    topography: TopographyType
    climate: ClimateType
    density: int  # 1–10
    # Computed character axes — derived from content pack scores + density.
    urbanization: float  # 0.0–1.0
    hostility: float  # 0.0–1.0
    remoteness: float  # 0.0–1.0
    locations: tuple[Location, ...]


@dataclass(frozen=True)
class Planet:
    """A planet or satellite within a SolarSystem."""

    id: str
    name: str
    size: Size
    classification: PlanetClass
    x: float
    y: float
    z: float  # bounded ±2, presentation only
    parent_planet_id: str | None  # None for primary planets; set for satellites
    distinctiveness: float  # 0.0–1.0
    sectors: tuple[Sector, ...]


@dataclass(frozen=True)
class SolarSystem:
    """A named solar system within a Galaxy."""

    id: str
    name: str
    size: Size
    x: float
    y: float
    z: float  # bounded ±5, presentation only
    # list of (culture_id, weight) — weights sum to 1.0
    culture_ids: tuple[tuple[str, float], ...]
    planets: tuple[Planet, ...]


@dataclass(frozen=True)
class Galaxy:
    """Top-level output of the generation pipeline."""

    seed: int | str
    config_version: str
    content_pack_version: str
    # Serialisable culture registry keyed by culture id.
    cultures: dict[str, CultureSpec] = field(default_factory=dict)
    systems: tuple[SolarSystem, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationIssue:
    """A single validation finding with a stable machine-readable code."""

    code: str
    severity: Severity
    stage: ValidationStage
    message: str
    path: str | None = None
    entity_id: str | None = None


@dataclass(frozen=True)
class ValidationReport:
    """Container returned alongside a Galaxy from the generation pipeline."""

    issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not any(i.severity == Severity.ERROR for i in self.issues)

    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == Severity.ERROR)

    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == Severity.WARNING)
