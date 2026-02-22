"""Location generation (design doc §11 — Locations)."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from starloom.domain.models import Culture, Location
from starloom.domain.types import ClimateType, LocationType, NameStyle, Size, TopographyType
from starloom.generation.errors import EligibilityExhaustedError
from starloom.generation.naming import generate_entity_name

if TYPE_CHECKING:
    from starloom.config import GalaxyConfig
    from starloom.content.loader import ContentPack

# ---------------------------------------------------------------------------
# Built-in density ranges (fallback when no content pack is provided)
# ---------------------------------------------------------------------------

_LOCATION_COUNT_RANGE: tuple[int, int] = (3, 7)

_LOCATION_DENSITY_RANGE: dict[LocationType, tuple[int, int]] = {
    LocationType.TRIBAL:     (1, 4),
    LocationType.TRADING:    (3, 7),
    LocationType.CITY:       (5, 9),
    LocationType.METROPOLIS: (8, 10),
}

_ALL_LOCATION_TYPES = sorted(LocationType, key=lambda lt: lt.value)
_ALL_SIZES = sorted(Size, key=lambda s: s.value)
_SIZE_WEIGHTS = [0.15, 0.25, 0.30, 0.20, 0.10]


def _eligible_fallback(density: int) -> list[LocationType]:
    return [lt for lt in _ALL_LOCATION_TYPES
            if _LOCATION_DENSITY_RANGE[lt][0] <= density <= _LOCATION_DENSITY_RANGE[lt][1]]


# Alias used by tests
_eligible_location_types = _eligible_fallback


def _compute_distinctiveness(location_type: LocationType, size: Size, density: int) -> float:
    type_rarity = {
        LocationType.TRIBAL:     0.1,
        LocationType.TRADING:    0.3,
        LocationType.CITY:       0.6,
        LocationType.METROPOLIS: 0.9,
    }
    size_factor = (size.value - 1) / 4.0
    rarity = type_rarity[location_type]
    return round(min(1.0, (rarity * 0.6 + size_factor * 0.4)), 4)


# ---------------------------------------------------------------------------
# Public generation function
# ---------------------------------------------------------------------------


def generate_locations_for_sector(
    sector_id: str,
    density: int,
    config: "GalaxyConfig",
    cultures: list[tuple[Culture, float]],
    *,
    location_rng: random.Random,
    naming_rng: random.Random,
    content_pack: "ContentPack | None" = None,
    topography: TopographyType | None = None,
    climate: ClimateType | None = None,
) -> list[Location]:
    """Generate all locations for one sector.

    When a content_pack is provided together with topography and climate,
    eligible types come from the pack's precomputed eligibility matrix.
    Otherwise built-in density ranges are used.
    """
    count = location_rng.randint(*_LOCATION_COUNT_RANGE)

    # Resolve eligible location types
    if content_pack is not None and topography is not None and climate is not None:
        eligible_values = content_pack.eligible_location_types(topography, climate, density)
        eligible: list[LocationType] = [LocationType(v) for v in eligible_values]
    else:
        eligible = _eligible_fallback(density)

    if not eligible:
        if config.fallback_policy == "allow":
            eligible = [LocationType.TRIBAL]  # guaranteed safe fallback
        else:
            raise EligibilityExhaustedError(
                f"ELIGIBILITY_EXHAUSTED: no eligible location types for sector {sector_id!r} "
                f"at density={density}."
            )

    locations: list[Location] = []
    for l_idx in range(count):
        loc_id = f"{sector_id}-loc-{l_idx}"

        location_type: LocationType = location_rng.choice(
            sorted(eligible, key=lambda lt: lt.value)
        )
        size: Size = location_rng.choices(_ALL_SIZES, weights=_SIZE_WEIGHTS, k=1)[0]

        # Descriptors from content pack when available
        features: tuple[str, ...] = ()
        if content_pack is not None:
            for lt_data in content_pack.location_types:
                if lt_data["type"] == location_type.value:
                    descriptors = lt_data.get("descriptors", [])
                    if descriptors:
                        chosen = location_rng.choice(sorted(descriptors))
                        features = (chosen,)
                    break

        distinctiveness = _compute_distinctiveness(location_type, size, density)

        if cultures:
            name = generate_entity_name(cultures, NameStyle.GENERIC, naming_rng)
        else:
            name = f"Location-{l_idx}"

        locations.append(
            Location(
                id=loc_id,
                name=name,
                location_type=location_type,
                size=size,
                features=features,
                distinctiveness=distinctiveness,
                nodes=(),
            )
        )

    return locations
