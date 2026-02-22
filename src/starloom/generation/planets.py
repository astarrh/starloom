"""Planet and satellite generation (design doc §11 — Planets, Satellites)."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from starloom.domain.models import Culture, Planet
from starloom.domain.types import NameStyle, PlanetClass, Size
from starloom.generation.errors import PlacementExhaustedError
from starloom.generation.naming import generate_entity_name

if TYPE_CHECKING:
    from starloom.config import GalaxyConfig

# ---------------------------------------------------------------------------
# Planet count per system size (design doc §11 — Planets)
# ---------------------------------------------------------------------------

_PLANET_COUNT_RANGE: dict[Size, tuple[int, int]] = {
    Size.TINY: (1, 5),
    Size.SMALL: (3, 8),
    Size.MEDIUM: (5, 12),
    Size.LARGE: (8, 18),
    Size.ENORMOUS: (15, 25),
}

# Satellite count caps per planet size (design doc §11 — Satellites)
_SATELLITE_CAP: dict[Size, int] = {
    Size.MEDIUM: 2,
    Size.LARGE: 6,
    Size.ENORMOUS: 8,
}

# Planet classification weights: ~1/3 TELLURIC, ~2/3 other
_CLASS_WEIGHTS: dict[PlanetClass, float] = {
    PlanetClass.TELLURIC: 0.33,
    PlanetClass.GASEOUS: 0.25,
    PlanetClass.ICE: 0.18,
    PlanetClass.LAVA: 0.10,
    PlanetClass.LIQUID: 0.08,
    PlanetClass.ASTEROID: 0.06,
}
_CLASSES = sorted(_CLASS_WEIGHTS.keys(), key=lambda c: c.value)
_CLASS_W = [_CLASS_WEIGHTS[c] for c in _CLASSES]

# Placement bounds for planets (relative to system centre)
_PLANET_BOUND_BY_SIZE: dict[Size, float] = {
    Size.TINY: 30.0,
    Size.SMALL: 60.0,
    Size.MEDIUM: 120.0,
    Size.LARGE: 200.0,
    Size.ENORMOUS: 350.0,
}

# Satellite offset from parent planet
_SATELLITE_OFFSET: float = 3.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _quantize(value: float, digits: int) -> float:
    return round(value, digits)


def _place_unique(
    rng: random.Random,
    occupied: set[tuple[float, float]],
    bound: float,
    precision: int,
    max_retries: int,
    entity_label: str,
    cx: float = 0.0,
    cy: float = 0.0,
) -> tuple[float, float]:
    for _ in range(max_retries):
        x = cx + rng.uniform(-bound, bound)
        y = cy + rng.uniform(-bound, bound)
        key = (_quantize(x, precision), _quantize(y, precision))
        if key not in occupied:
            occupied.add(key)
            return x, y
    raise PlacementExhaustedError(
        f"PLACEMENT_EXHAUSTED: could not place {entity_label} "
        f"after {max_retries} retries within bound {bound}."
    )


# ---------------------------------------------------------------------------
# Public generation function
# ---------------------------------------------------------------------------


def generate_planets_for_system(
    system_id: str,
    system_size: Size,
    root_seed: int,
    config: "GalaxyConfig",
    cultures: list[tuple[Culture, float]],
    *,
    planet_rng: random.Random,
    naming_rng: random.Random,
    placement_rng: random.Random,
) -> list[Planet]:
    """Generate all planets (and their satellites) for one solar system.

    Parameters
    ----------
    system_id:
        Deterministic id string for the parent system (e.g. "sys-0007").
    system_size:
        Size of the parent system — controls planet count range.
    root_seed / config:
        Used to drive sub-decisions.
    cultures:
        Weighted culture list inherited from the system.
    planet_rng / naming_rng / placement_rng:
        Isolated Random instances for their respective streams.

    Returns
    -------
    list[Planet] — primary planets + satellites, all in one flat list.
    """
    cfg = config.system
    retries = config.retries

    lo, hi = _PLANET_COUNT_RANGE[system_size]
    planet_count = planet_rng.randint(lo, hi)

    bound = _PLANET_BOUND_BY_SIZE[system_size]
    occupied: set[tuple[float, float]] = set()

    planets: list[Planet] = []

    for p_idx in range(planet_count):
        planet_id = f"{system_id}-pl-{p_idx:03d}"

        classification: PlanetClass = planet_rng.choices(_CLASSES, weights=_CLASS_W, k=1)[0]
        size: Size = _choose_planet_size(planet_rng, classification)

        x, y = _place_unique(
            placement_rng,
            occupied,
            bound,
            cfg.coordinate_precision_digits,
            retries.max_coordinate_retries,
            planet_id,
        )
        z = placement_rng.uniform(-2.0, 2.0)

        if cultures:
            name = generate_entity_name(cultures, NameStyle.GENERIC, naming_rng)
        else:
            name = f"Planet-{p_idx:03d}"

        planet = Planet(
            id=planet_id,
            name=name,
            size=size,
            classification=classification,
            x=x,
            y=y,
            z=z,
            parent_planet_id=None,
            distinctiveness=0.0,  # computed post-generation in Phase 05
            sectors=(),           # filled by sector generation
        )
        planets.append(planet)

        # --- Satellites ---
        if size in _SATELLITE_CAP:
            satellites = _generate_satellites(
                planet,
                system_id,
                p_idx,
                config,
                cultures,
                planet_rng=planet_rng,
                naming_rng=naming_rng,
                placement_rng=placement_rng,
                occupied=occupied,
            )
            planets.extend(satellites)

    return planets


def _choose_planet_size(rng: random.Random, classification: PlanetClass) -> Size:
    """Choose a plausible size for a planet based on its classification."""
    if classification == PlanetClass.GASEOUS:
        return rng.choices(
            [Size.LARGE, Size.ENORMOUS],
            weights=[0.6, 0.4],
            k=1,
        )[0]
    if classification == PlanetClass.ASTEROID:
        return rng.choices(
            [Size.TINY, Size.SMALL],
            weights=[0.7, 0.3],
            k=1,
        )[0]
    # All others: full range
    sizes = sorted(Size, key=lambda s: s.value)
    weights = [0.15, 0.25, 0.30, 0.20, 0.10]
    return rng.choices(sizes, weights=weights, k=1)[0]


def _generate_satellites(
    parent: Planet,
    system_id: str,
    parent_idx: int,
    config: "GalaxyConfig",
    cultures: list[tuple[Culture, float]],
    *,
    planet_rng: random.Random,
    naming_rng: random.Random,
    placement_rng: random.Random,
    occupied: set[tuple[float, float]],
) -> list[Planet]:
    cap = _SATELLITE_CAP[parent.size]
    count = planet_rng.randint(0, cap)
    retries = config.retries
    cfg = config.system

    satellites: list[Planet] = []
    for s_idx in range(count):
        sat_id = f"{system_id}-pl-{parent_idx:03d}-sat-{s_idx:02d}"

        size: Size = planet_rng.choices(
            [Size.TINY, Size.SMALL],
            weights=[0.6, 0.4],
            k=1,
        )[0]

        x, y = _place_unique(
            placement_rng,
            occupied,
            _SATELLITE_OFFSET,
            cfg.coordinate_precision_digits,
            retries.max_coordinate_retries,
            sat_id,
            cx=parent.x,
            cy=parent.y,
        )

        if cultures:
            name = generate_entity_name(cultures, NameStyle.GENERIC, naming_rng)
        else:
            name = f"Moon-{parent_idx:03d}-{s_idx:02d}"

        satellites.append(
            Planet(
                id=sat_id,
                name=name,
                size=size,
                classification=PlanetClass.ICE,  # satellites default to ICE
                x=x,
                y=y,
                z=parent.z,
                parent_planet_id=parent.id,
                distinctiveness=0.0,
                sectors=(),
            )
        )

    return satellites
