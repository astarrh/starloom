"""Location generation (design doc §11 — Locations)."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from starloom.domain.models import Culture, Location
from starloom.domain.types import LocationType, NameStyle, Size
from starloom.generation.naming import generate_entity_name

if TYPE_CHECKING:
    from starloom.config import GalaxyConfig

# ---------------------------------------------------------------------------
# Constants (design doc §11 — Locations)
# ---------------------------------------------------------------------------

_LOCATION_COUNT_RANGE: tuple[int, int] = (3, 7)

# Density thresholds per location type.
# Phase 04 will load these from the content pack; Phase 03 uses built-ins.
_LOCATION_DENSITY_RANGE: dict[LocationType, tuple[int, int]] = {
    LocationType.TRIBAL:     (1, 4),
    LocationType.TRADING:    (3, 7),
    LocationType.CITY:       (5, 9),
    LocationType.METROPOLIS: (8, 10),
}

_ALL_LOCATION_TYPES = sorted(LocationType, key=lambda lt: lt.value)

_ALL_SIZES = sorted(Size, key=lambda s: s.value)
_SIZE_WEIGHTS = [0.15, 0.25, 0.30, 0.20, 0.10]


def _eligible_location_types(density: int) -> list[LocationType]:
    """Return location types whose density range includes the given density."""
    return [lt for lt in _ALL_LOCATION_TYPES
            if _LOCATION_DENSITY_RANGE[lt][0] <= density <= _LOCATION_DENSITY_RANGE[lt][1]]


def _compute_distinctiveness(location_type: LocationType, size: Size, density: int) -> float:
    """Simple distinctiveness heuristic for Phase 03.

    Phase 05 will refine this with rarity scores and affinity matching.
    Larger sizes and rarer types score higher.
    """
    type_rarity = {
        LocationType.TRIBAL: 0.1,
        LocationType.TRADING: 0.3,
        LocationType.CITY: 0.6,
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
) -> list[Location]:
    """Generate all locations for one sector.

    Eligible location types are filtered by density range.  If no type is
    eligible the density is clamped to ensure at least one option (TRIBAL
    always applies at density 1–4).
    """
    count = location_rng.randint(*_LOCATION_COUNT_RANGE)

    eligible = _eligible_location_types(density)
    if not eligible:
        eligible = [LocationType.TRIBAL]  # guaranteed fallback

    locations: list[Location] = []
    for l_idx in range(count):
        loc_id = f"{sector_id}-loc-{l_idx}"

        location_type: LocationType = location_rng.choice(sorted(eligible, key=lambda lt: lt.value))
        size: Size = location_rng.choices(_ALL_SIZES, weights=_SIZE_WEIGHTS, k=1)[0]
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
                features=(),      # Phase 04: populated from content pack descriptors
                distinctiveness=distinctiveness,
                nodes=(),         # filled by node generation
            )
        )

    return locations
