"""Sector generation with character axis computation (design doc §11 — Sectors, §9.6)."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from starloom.domain.models import Culture, Sector
from starloom.domain.types import ClimateType, NameStyle, TopographyType
from starloom.generation.naming import generate_entity_name

if TYPE_CHECKING:
    from starloom.config import GalaxyConfig

# ---------------------------------------------------------------------------
# Sector count per planet size (design doc §11 — Sectors)
# ---------------------------------------------------------------------------

_SECTOR_COUNT_RANGE: dict[int, tuple[int, int]] = {
    1: (2, 5),   # TINY
    2: (4, 8),   # SMALL
    3: (6, 12),  # MEDIUM
    4: (10, 16), # LARGE
    5: (18, 21), # ENORMOUS
}

# ---------------------------------------------------------------------------
# Character axis base scores (design doc §9.6).
# Phase 03 uses a built-in table; Phase 04 will load these from content pack.
# ---------------------------------------------------------------------------

# Hostility base scores per climate (0.0 = benign, 1.0 = lethal)
_CLIMATE_HOSTILITY: dict[ClimateType, float] = {
    ClimateType.VOLCANIC: 0.95,
    ClimateType.ARID:     0.70,
    ClimateType.STEPPE:   0.40,
    ClimateType.TEMPERATE:0.15,
    ClimateType.HUMID:    0.20,
    ClimateType.RAINY:    0.30,
    ClimateType.FROZEN:   0.75,
}

# Remoteness base scores per topography (0.0 = accessible, 1.0 = isolated)
_TOPOGRAPHY_REMOTENESS: dict[TopographyType, float] = {
    TopographyType.PLAINS: 0.10,
    TopographyType.BASIN:  0.20,
    TopographyType.HILLS:  0.35,
    TopographyType.KARST:  0.50,
    TopographyType.CANYON: 0.65,
    TopographyType.CLIFFS: 0.75,
    TopographyType.PEAKS:  0.90,
}

_ALL_TOPOGRAPHIES = sorted(TopographyType, key=lambda t: t.value)
_ALL_CLIMATES = sorted(ClimateType, key=lambda c: c.value)


def _urbanization(density: int) -> float:
    """Map density 1–10 linearly onto [0.05, 0.95]."""
    return 0.05 + (density - 1) / 9.0 * 0.90


def _compute_hostility(climate: ClimateType) -> float:
    return _CLIMATE_HOSTILITY[climate]


def _compute_remoteness(topography: TopographyType) -> float:
    return _TOPOGRAPHY_REMOTENESS[topography]


# ---------------------------------------------------------------------------
# Public generation function
# ---------------------------------------------------------------------------


def generate_sectors_for_planet(
    planet_id: str,
    planet_size_value: int,
    config: "GalaxyConfig",
    cultures: list[tuple[Culture, float]],
    *,
    sector_rng: random.Random,
    naming_rng: random.Random,
) -> list[Sector]:
    """Generate all sectors for one planet.

    Parameters
    ----------
    planet_id:
        Deterministic id of the parent planet.
    planet_size_value:
        Integer value of the planet's Size enum (1–5).
    config:
        Validated GalaxyConfig.
    cultures:
        Weighted culture list for naming.
    sector_rng:
        Isolated Random for sector decisions.
    naming_rng:
        Isolated Random for name generation.
    """
    lo, hi = _SECTOR_COUNT_RANGE[planet_size_value]
    count = sector_rng.randint(lo, hi)

    sectors: list[Sector] = []
    for s_idx in range(count):
        sector_id = f"{planet_id}-sec-{s_idx:02d}"

        topography: TopographyType = sector_rng.choice(_ALL_TOPOGRAPHIES)
        climate: ClimateType = sector_rng.choice(_ALL_CLIMATES)

        # Density: 1–10 (Phase 04 will cap by sector_type.max_density from content pack)
        density = sector_rng.randint(1, 10)

        urbanization = _urbanization(density)
        hostility = _compute_hostility(climate)
        remoteness = _compute_remoteness(topography)

        if cultures:
            name = generate_entity_name(cultures, NameStyle.GENERIC, naming_rng)
        else:
            name = f"Sector-{s_idx:02d}"

        sectors.append(
            Sector(
                id=sector_id,
                name=name,
                topography=topography,
                climate=climate,
                density=density,
                urbanization=round(urbanization, 4),
                hostility=round(hostility, 4),
                remoteness=round(remoteness, 4),
                locations=(),  # filled by location generation
            )
        )

    return sectors
