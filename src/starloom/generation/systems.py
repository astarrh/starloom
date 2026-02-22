"""Solar system generation (design doc §11 — Solar Systems)."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from starloom.domain.models import Culture, CultureSpec, Planet, SolarSystem
from starloom.domain.types import Size
from starloom.generation.errors import PlacementExhaustedError
from starloom.generation.naming import generate_entity_name
from starloom.domain.types import NameStyle

if TYPE_CHECKING:
    from starloom.config import GalaxyConfig

# ---------------------------------------------------------------------------
# Size weight distribution for systems (design doc §11 — Solar Systems)
# ---------------------------------------------------------------------------

_SYSTEM_SIZE_WEIGHTS: dict[Size, float] = {
    Size.TINY: 0.10,
    Size.SMALL: 0.25,
    Size.MEDIUM: 0.35,
    Size.LARGE: 0.20,
    Size.ENORMOUS: 0.10,
}

_SIZES = sorted(_SYSTEM_SIZE_WEIGHTS.keys(), key=lambda s: s.value)
_SIZE_WEIGHTS = [_SYSTEM_SIZE_WEIGHTS[s] for s in _SIZES]


# ---------------------------------------------------------------------------
# Coordinate helpers
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
) -> tuple[float, float]:
    """Draw (x, y) within [-bound, bound] until a unique quantized key is found."""
    for _ in range(max_retries):
        x = rng.uniform(-bound, bound)
        y = rng.uniform(-bound, bound)
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


def generate_systems(
    root_seed: int,
    config: "GalaxyConfig",
    cultures: list[tuple[Culture, float]],
    *,
    naming_rng: random.Random,
    placement_rng: random.Random,
    culture_rng: random.Random,
) -> tuple[list[SolarSystem], dict[str, CultureSpec]]:
    """Generate all solar systems for a galaxy.

    Parameters
    ----------
    root_seed:
        Normalised integer seed (for ID derivation).
    config:
        Validated GalaxyConfig.
    cultures:
        List of (Culture, weight) pairs to draw names from.
        May be empty — in that case a fallback name scheme is used.
    naming_rng / placement_rng / culture_rng:
        Pre-created isolated Random instances for their respective streams.

    Returns
    -------
    (list[SolarSystem], dict[str, CultureSpec])
        Systems and the culture registry populated from provided cultures.
    """
    systems: list[SolarSystem] = []
    occupied: set[tuple[float, float]] = set()

    cfg = config.system
    retries = config.retries

    # Build culture registry from provided cultures.
    culture_registry: dict[str, CultureSpec] = {}
    for culture, _ in cultures:
        culture_registry[culture.id] = CultureSpec(
            id=culture.id,
            name=culture.name,
            markov_model_data=culture.markov_model,
            name_styles=culture.name_styles,
            metadata=culture.metadata,
        )

    for index in range(cfg.count):
        sys_id = f"sys-{index:04d}"

        # --- Size ---
        size: Size = culture_rng.choices(_SIZES, weights=_SIZE_WEIGHTS, k=1)[0]

        # --- Coordinates ---
        x, y = _place_unique(
            placement_rng,
            occupied,
            cfg.placement_bound,
            cfg.coordinate_precision_digits,
            retries.max_coordinate_retries,
            sys_id,
        )
        z = placement_rng.uniform(-5.0, 5.0)

        # --- Name ---
        if cultures:
            name = generate_entity_name(cultures, NameStyle.GENERIC, naming_rng)
        else:
            name = _fallback_name("system", index)

        # --- Culture weights for this system ---
        # For now: carry through the galaxy-level culture mix.
        # Phase 03 keeps it simple; per-system culture blending comes with hooks.
        if cultures:
            total_w = sum(w for _, w in cultures)
            sys_culture_ids: tuple[tuple[str, float], ...] = tuple(
                (c.id, w / total_w) for c, w in sorted(cultures, key=lambda t: t[0].id)
            )
        else:
            sys_culture_ids = ()

        systems.append(
            SolarSystem(
                id=sys_id,
                name=name,
                size=size,
                x=x,
                y=y,
                z=z,
                culture_ids=sys_culture_ids,
                planets=(),  # filled in by galaxy.py after planet generation
            )
        )

    return systems, culture_registry


def _fallback_name(domain: str, index: int) -> str:
    """Simple indexed name used when no cultures are provided."""
    return f"{domain.capitalize()}-{index:04d}"


# ---------------------------------------------------------------------------
# ID helpers reused by other generation modules
# ---------------------------------------------------------------------------


def system_id(index: int) -> str:
    return f"sys-{index:04d}"
