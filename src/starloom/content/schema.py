"""JSON Schema definitions for content pack validation (design doc §9.7).

Each YAML file in a content pack is normalised to a JSON-compatible object
and validated against these schemas before generation begins.

Schema strategy:
- JSON Schema Draft 2020-12 for structural validation (via jsonschema library
  when available, or a lightweight fallback validator).
- Semantic checks (cross-file references, coverage invariants) are implemented
  as Python functions here and run by the loader after schema validation.
"""

from __future__ import annotations

from starloom.domain.types import (
    ClimateType,
    LocationType,
    NodeType,
    PlanetClass,
    TopographyType,
)

# ---------------------------------------------------------------------------
# Valid enum value sets (used in semantic checks)
# ---------------------------------------------------------------------------

VALID_TOPOGRAPHIES: frozenset[str] = frozenset(t.value for t in TopographyType)
VALID_CLIMATES: frozenset[str] = frozenset(c.value for c in ClimateType)
VALID_LOCATION_TYPES: frozenset[str] = frozenset(lt.value for lt in LocationType)
VALID_NODE_TYPES: frozenset[str] = frozenset(nt.value for nt in NodeType)
VALID_PLANET_CLASSES: frozenset[str] = frozenset(pc.value for pc in PlanetClass)

# ---------------------------------------------------------------------------
# JSON Schema definitions
# ---------------------------------------------------------------------------

_AFFINITY_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "climates":     {"type": "array", "items": {"type": "string"}},
        "topographies": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}

PLANET_CLASSES_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["version", "planet_classes"],
    "properties": {
        "version": {"type": "string"},
        "planet_classes": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name":              {"type": "string"},
                    "state":             {"type": "string"},
                    "temperature_range": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                    "gravity_range":     {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

SECTOR_TYPES_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["version", "sector_types"],
    "properties": {
        "version": {"type": "string"},
        "sector_types": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["topography", "climate", "max_density", "hostility", "remoteness"],
                "properties": {
                    "topography":   {"type": "string"},
                    "climate":      {"type": "string"},
                    "max_density":  {"type": "integer", "minimum": 1, "maximum": 10},
                    "hostility":    {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "remoteness":   {"type": "number", "minimum": 0.0, "maximum": 1.0},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

LOCATION_TYPES_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["version", "location_types"],
    "properties": {
        "version": {"type": "string"},
        "location_types": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["name", "type", "density_min", "density_max", "rarity"],
                "properties": {
                    "name":        {"type": "string"},
                    "type":        {"type": "string"},
                    "density_min": {"type": "integer", "minimum": 1, "maximum": 10},
                    "density_max": {"type": "integer", "minimum": 1, "maximum": 10},
                    "rarity":      {"type": "number", "exclusiveMinimum": 0.0, "maximum": 1.0},
                    "affinity":    _AFFINITY_SCHEMA,
                    "descriptors": {"type": "array", "items": {"type": "string"}},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

NODE_TYPES_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["version", "node_types"],
    "properties": {
        "version": {"type": "string"},
        "node_types": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["name", "type", "density_min", "density_max", "rarity", "in_town"],
                "properties": {
                    "name":        {"type": "string"},
                    "type":        {"type": "string"},
                    "density_min": {"type": "integer", "minimum": 1, "maximum": 10},
                    "density_max": {"type": "integer", "minimum": 1, "maximum": 10},
                    "rarity":      {"type": "number", "exclusiveMinimum": 0.0, "maximum": 1.0},
                    "in_town":     {"type": "boolean"},
                    "name_style":  {"type": "string"},
                    "affinity":    _AFFINITY_SCHEMA,
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# Semantic validators
# ---------------------------------------------------------------------------


class ContentPackValidationError(ValueError):
    """Raised when content pack fails schema or semantic validation."""

    def __init__(self, message: str, *, code: str = "PACK_SCHEMA_VIOLATION", path: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.path = path


def validate_sector_types_semantic(sector_types: list[dict]) -> None:
    """Check topography/climate values reference valid enum members."""
    seen: set[tuple[str, str]] = set()
    for i, st in enumerate(sector_types):
        topo = st["topography"]
        clim = st["climate"]
        if topo not in VALID_TOPOGRAPHIES:
            raise ContentPackValidationError(
                f"sector_types[{i}].topography {topo!r} is not a valid TopographyType.",
                code="PACK_UNKNOWN_REFERENCE",
                path=f"sector_types[{i}].topography",
            )
        if clim not in VALID_CLIMATES:
            raise ContentPackValidationError(
                f"sector_types[{i}].climate {clim!r} is not a valid ClimateType.",
                code="PACK_UNKNOWN_REFERENCE",
                path=f"sector_types[{i}].climate",
            )
        key = (topo, clim)
        if key in seen:
            raise ContentPackValidationError(
                f"Duplicate sector_type entry: topography={topo!r}, climate={clim!r}.",
                code="PACK_SCHEMA_VIOLATION",
                path=f"sector_types[{i}]",
            )
        seen.add(key)


def validate_location_types_semantic(location_types: list[dict]) -> None:
    """Check type values, density ordering, and affinity references."""
    for i, lt in enumerate(location_types):
        if lt["type"] not in VALID_LOCATION_TYPES:
            raise ContentPackValidationError(
                f"location_types[{i}].type {lt['type']!r} is not a valid LocationType.",
                code="PACK_UNKNOWN_REFERENCE",
                path=f"location_types[{i}].type",
            )
        if lt["density_min"] > lt["density_max"]:
            raise ContentPackValidationError(
                f"location_types[{i}]: density_min > density_max.",
                code="PACK_SCHEMA_VIOLATION",
                path=f"location_types[{i}]",
            )
        _validate_affinity(lt.get("affinity", {}), f"location_types[{i}]")


def validate_node_types_semantic(node_types: list[dict]) -> None:
    """Check type values, density ordering, and affinity references."""
    for i, nt in enumerate(node_types):
        if nt["type"] not in VALID_NODE_TYPES:
            raise ContentPackValidationError(
                f"node_types[{i}].type {nt['type']!r} is not a valid NodeType.",
                code="PACK_UNKNOWN_REFERENCE",
                path=f"node_types[{i}].type",
            )
        if nt["density_min"] > nt["density_max"]:
            raise ContentPackValidationError(
                f"node_types[{i}]: density_min > density_max.",
                code="PACK_SCHEMA_VIOLATION",
                path=f"node_types[{i}]",
            )
        _validate_affinity(nt.get("affinity", {}), f"node_types[{i}]")


def validate_planet_classes_semantic(planet_classes: list[dict]) -> None:
    """Check planet class names reference valid enum members."""
    for i, pc in enumerate(planet_classes):
        if pc["name"] not in VALID_PLANET_CLASSES:
            raise ContentPackValidationError(
                f"planet_classes[{i}].name {pc['name']!r} is not a valid PlanetClass.",
                code="PACK_UNKNOWN_REFERENCE",
                path=f"planet_classes[{i}].name",
            )


def _validate_affinity(affinity: dict, path: str) -> None:
    for clim in affinity.get("climates", []):
        if clim not in VALID_CLIMATES:
            raise ContentPackValidationError(
                f"{path}.affinity.climates: {clim!r} is not a valid ClimateType.",
                code="PACK_UNKNOWN_REFERENCE",
                path=f"{path}.affinity.climates",
            )
    for topo in affinity.get("topographies", []):
        if topo not in VALID_TOPOGRAPHIES:
            raise ContentPackValidationError(
                f"{path}.affinity.topographies: {topo!r} is not a valid TopographyType.",
                code="PACK_UNKNOWN_REFERENCE",
                path=f"{path}.affinity.topographies",
            )
