"""Content pack loader (design doc §9).

Responsibilities:
1. Load YAML files from a pack directory.
2. Normalise to JSON-compatible Python objects.
3. Validate against JSON Schema (structural) using jsonschema if available,
   or a lightweight fallback if not installed.
4. Run semantic validators (enum references, density ordering, affinity coverage).
5. Build a ContentPack dataclass that bundles all validated data.
6. Precompute the eligibility matrix:
   (topography, climate, density) → [eligible LocationType, ...]
   (topography, climate, density, in_town) → [eligible NodeType, ...]
7. Compute a deterministic SHA-256 hash of pack contents for repro_mode="strict".

Only local paths are supported (no remote URLs).  See design doc §9, decision #5.

Usage
-----
    from starloom.content.loader import load_content_pack, default_content_pack

    pack = default_content_pack()          # ships with the library
    pack = load_content_pack("./my-pack")  # custom replacement
"""

from __future__ import annotations

import hashlib
import importlib.resources
import json
import pathlib
from dataclasses import dataclass, field
from typing import Any

from starloom.content.schema import (
    LOCATION_TYPES_SCHEMA,
    NODE_TYPES_SCHEMA,
    PLANET_CLASSES_SCHEMA,
    SECTOR_TYPES_SCHEMA,
    ContentPackValidationError,
    validate_location_types_semantic,
    validate_node_types_semantic,
    validate_planet_classes_semantic,
    validate_sector_types_semantic,
)
from starloom.domain.types import ClimateType, LocationType, NodeType, TopographyType

# ---------------------------------------------------------------------------
# Optional jsonschema import
# ---------------------------------------------------------------------------

try:
    import jsonschema as _jsonschema  # type: ignore[import]
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

try:
    import yaml as _yaml  # type: ignore[import]
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


# ---------------------------------------------------------------------------
# SectorType resolved entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SectorTypeEntry:
    topography: TopographyType
    climate: ClimateType
    max_density: int
    hostility: float
    remoteness: float


# ---------------------------------------------------------------------------
# Eligibility matrix key types
# ---------------------------------------------------------------------------

LocationEligibilityKey = tuple[str, str, int]       # (topo, climate, density)
NodeEligibilityKey = tuple[str, str, int, bool]     # (topo, climate, density, in_town)


# ---------------------------------------------------------------------------
# ContentPack
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContentPack:
    """Validated, ready-to-use content pack.

    All dicts are keyed by (topography.value, climate.value) or similar
    for fast lookup during generation.
    """

    version: str
    pack_hash: str  # SHA-256 hex digest of canonical JSON representation

    # Sector type lookup: (topo_value, climate_value) → SectorTypeEntry
    sector_types: dict[tuple[str, str], SectorTypeEntry]

    # Location type data keyed by LocationType.value
    location_types: list[dict[str, Any]]

    # Node type data keyed by NodeType.value
    node_types: list[dict[str, Any]]

    # Planet class data
    planet_classes: list[dict[str, Any]]

    # Precomputed eligibility matrices
    location_eligibility: dict[LocationEligibilityKey, list[str]]   # → [LocationType.value]
    node_eligibility: dict[NodeEligibilityKey, list[str]]            # → [NodeType.value]

    def sector_type(self, topography: TopographyType, climate: ClimateType) -> SectorTypeEntry | None:
        return self.sector_types.get((topography.value, climate.value))

    def eligible_location_types(
        self, topography: TopographyType, climate: ClimateType, density: int
    ) -> list[str]:
        key: LocationEligibilityKey = (topography.value, climate.value, density)
        return self.location_eligibility.get(key, [])

    def eligible_node_types(
        self, topography: TopographyType, climate: ClimateType, density: int, in_town: bool
    ) -> list[str]:
        key: NodeEligibilityKey = (topography.value, climate.value, density, in_town)
        return self.node_eligibility.get(key, [])


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_content_pack(path: str | pathlib.Path) -> ContentPack:
    """Load and validate a content pack from a local directory.

    Parameters
    ----------
    path:
        Path to a directory containing planet_classes.yaml, sector_types.yaml,
        location_types.yaml, and node_types.yaml.

    Raises
    ------
    ContentPackValidationError
        On any schema or semantic violation.
    FileNotFoundError
        If a required YAML file is missing.
    """
    pack_dir = pathlib.Path(path)
    if not pack_dir.is_dir():
        raise FileNotFoundError(f"Content pack directory not found: {pack_dir}")

    raw: dict[str, Any] = {}
    for fname in ("planet_classes.yaml", "sector_types.yaml", "location_types.yaml", "node_types.yaml"):
        fpath = pack_dir / fname
        if not fpath.exists():
            raise FileNotFoundError(f"Missing required pack file: {fpath}")
        raw[fname] = _load_yaml(fpath)

    return _build_pack(raw)


def default_content_pack() -> ContentPack:
    """Load the built-in default content pack shipped with starloom."""
    # Locate the packs/default directory relative to this package.
    pkg_root = pathlib.Path(__file__).parent.parent  # src/starloom/
    pack_dir = pkg_root / "packs" / "default"
    return load_content_pack(pack_dir)


# ---------------------------------------------------------------------------
# Internal build helpers
# ---------------------------------------------------------------------------


def _load_yaml(path: pathlib.Path) -> Any:
    if not _HAS_YAML:
        raise ImportError(
            "PyYAML is required to load content packs. "
            "Install it with: pip install pyyaml"
        )
    with path.open("r", encoding="utf-8") as f:
        return _yaml.safe_load(f)


def _validate_schema(data: Any, schema: dict, filename: str) -> None:
    if _HAS_JSONSCHEMA:
        try:
            _jsonschema.validate(instance=data, schema=schema)
        except _jsonschema.ValidationError as exc:
            path_str = " > ".join(str(p) for p in exc.absolute_path) or "(root)"
            raise ContentPackValidationError(
                f"PACK_SCHEMA_VIOLATION in {filename}: {exc.message}",
                code="PACK_SCHEMA_VIOLATION",
                path=path_str,
            ) from exc
    else:
        # Lightweight fallback: check required top-level keys only.
        required = schema.get("required", [])
        for key in required:
            if key not in data:
                raise ContentPackValidationError(
                    f"PACK_SCHEMA_VIOLATION in {filename}: missing required field {key!r}.",
                    code="PACK_SCHEMA_VIOLATION",
                    path=key,
                )


def _build_pack(raw: dict[str, Any]) -> ContentPack:
    # --- Validate schemas ---
    _validate_schema(raw["planet_classes.yaml"], PLANET_CLASSES_SCHEMA, "planet_classes.yaml")
    _validate_schema(raw["sector_types.yaml"], SECTOR_TYPES_SCHEMA, "sector_types.yaml")
    _validate_schema(raw["location_types.yaml"], LOCATION_TYPES_SCHEMA, "location_types.yaml")
    _validate_schema(raw["node_types.yaml"], NODE_TYPES_SCHEMA, "node_types.yaml")

    planet_classes_data: list[dict] = raw["planet_classes.yaml"]["planet_classes"]
    sector_types_data: list[dict] = raw["sector_types.yaml"]["sector_types"]
    location_types_data: list[dict] = raw["location_types.yaml"]["location_types"]
    node_types_data: list[dict] = raw["node_types.yaml"]["node_types"]

    # --- Semantic validation ---
    validate_planet_classes_semantic(planet_classes_data)
    validate_sector_types_semantic(sector_types_data)
    validate_location_types_semantic(location_types_data)
    validate_node_types_semantic(node_types_data)

    # --- Build sector type lookup ---
    sector_map: dict[tuple[str, str], SectorTypeEntry] = {}
    for st in sector_types_data:
        entry = SectorTypeEntry(
            topography=TopographyType(st["topography"]),
            climate=ClimateType(st["climate"]),
            max_density=st["max_density"],
            hostility=st["hostility"],
            remoteness=st["remoteness"],
        )
        sector_map[(st["topography"], st["climate"])] = entry

    # --- Precompute eligibility matrices ---
    location_eligibility = _build_location_eligibility(location_types_data, sector_map)
    node_eligibility = _build_node_eligibility(node_types_data, sector_map)

    # --- Warn on empty pools (PACK_AFFINITY_EMPTY_POOL) ---
    _check_empty_pools(location_eligibility, node_eligibility, sector_map)

    # --- Compute pack hash ---
    canonical = json.dumps(
        {k: v for k, v in sorted(raw.items())},
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    pack_hash = hashlib.sha256(canonical).hexdigest()

    # Determine version from sector_types file (all files share the same version)
    version = raw["sector_types.yaml"].get("version", "unknown")

    return ContentPack(
        version=version,
        pack_hash=pack_hash,
        sector_types=sector_map,
        location_types=location_types_data,
        node_types=node_types_data,
        planet_classes=planet_classes_data,
        location_eligibility=location_eligibility,
        node_eligibility=node_eligibility,
    )


def _affinity_matches(entry: dict, topo: str, climate: str) -> bool:
    """True when the entry's affinity includes the given topo and climate.

    An empty affinity list means "eligible everywhere".
    """
    affinity = entry.get("affinity", {})
    allowed_climates = affinity.get("climates", [])
    allowed_topos = affinity.get("topographies", [])
    if allowed_climates and climate not in allowed_climates:
        return False
    if allowed_topos and topo not in allowed_topos:
        return False
    return True


def _build_location_eligibility(
    location_types: list[dict],
    sector_map: dict[tuple[str, str], SectorTypeEntry],
) -> dict[LocationEligibilityKey, list[str]]:
    matrix: dict[LocationEligibilityKey, list[str]] = {}
    for st_entry in sector_map.values():
        topo = st_entry.topography.value
        climate = st_entry.climate.value
        max_d = st_entry.max_density
        for density in range(1, max_d + 1):
            key: LocationEligibilityKey = (topo, climate, density)
            eligible = [
                lt["type"] for lt in location_types
                if lt["density_min"] <= density <= lt["density_max"]
                and _affinity_matches(lt, topo, climate)
            ]
            matrix[key] = sorted(eligible)
    return matrix


def _build_node_eligibility(
    node_types: list[dict],
    sector_map: dict[tuple[str, str], SectorTypeEntry],
) -> dict[NodeEligibilityKey, list[str]]:
    matrix: dict[NodeEligibilityKey, list[str]] = {}
    for st_entry in sector_map.values():
        topo = st_entry.topography.value
        climate = st_entry.climate.value
        max_d = st_entry.max_density
        for density in range(1, max_d + 1):
            for in_town in (True, False):
                key: NodeEligibilityKey = (topo, climate, density, in_town)
                eligible = [
                    nt["type"] for nt in node_types
                    if nt["density_min"] <= density <= nt["density_max"]
                    and nt.get("in_town", True) == in_town
                    and _affinity_matches(nt, topo, climate)
                ]
                matrix[key] = sorted(eligible)
    return matrix


def _check_empty_pools(
    location_eligibility: dict[LocationEligibilityKey, list[str]],
    node_eligibility: dict[NodeEligibilityKey, list[str]],
    sector_map: dict[tuple[str, str], SectorTypeEntry],
) -> None:
    """Log PACK_AFFINITY_EMPTY_POOL warnings for any context with no eligible types.

    Phase 04 records these as warnings rather than errors (design doc §13.2).
    Callers may inspect ContentPack.location_eligibility for coverage gaps.
    """
    # For now just silently accept — full warning integration requires
    # a ValidationReport accumulator, wired in the galaxy pipeline.
    pass
