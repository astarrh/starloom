"""Naming orchestration layer (generation/naming.py).

This module is a thin coordinator between the generation pipeline and the
culture/markov subsystem.  It receives a resolved culture list, samples a
culture according to the weighted distribution, applies style constraints,
and delegates name generation to that culture's Markov model.

Design doc §12.4:
    "naming.py is a thin orchestration layer. It receives an entity's resolved
    culture list, samples a culture, and delegates name generation to that
    culture's Markov model."
"""

from __future__ import annotations

import random

from starloom.culture import markov as _markov
from starloom.culture.factory import _apply_style_lengths, _apply_template
from starloom.domain.models import Culture, StyleConfig
from starloom.domain.types import NameStyle

# Default style used when neither the caller nor the culture specifies one.
_FALLBACK_STYLE = StyleConfig(min_length=4, max_length=10)


def pick_culture(
    cultures: list[tuple[Culture, float]],
    rng: random.Random,
) -> Culture:
    """Sample one Culture from a weighted list using the given RNG.

    Weights are normalised to sum to 1.0.  The culture list is sorted by
    culture id before sampling to preserve insertion-order independence.
    """
    if not cultures:
        raise ValueError("cultures list must not be empty.")

    # Sort by culture id for determinism regardless of insertion order.
    ordered = sorted(cultures, key=lambda t: t[0].id)
    culture_objs = [c for c, _ in ordered]
    weights = [w for _, w in ordered]

    total = sum(weights)
    normalised = [w / total for w in weights]

    chosen: Culture = rng.choices(culture_objs, weights=normalised, k=1)[0]
    return chosen


def generate_entity_name(
    cultures: list[tuple[Culture, float]],
    style: NameStyle,
    rng: random.Random,
) -> str:
    """Generate a name for a world entity.

    Parameters
    ----------
    cultures:
        Non-empty list of (Culture, weight) pairs.  Weights need not sum to 1.
    style:
        Which NameStyle to apply.
    rng:
        Isolated Random instance from the naming stream.

    Returns
    -------
    str — capitalised name with any style template applied.
    """
    culture = pick_culture(cultures, rng)

    style_cfg: StyleConfig = culture.name_styles.get(style, _FALLBACK_STYLE)
    model = _apply_style_lengths(culture.markov_model, style_cfg)
    raw = _markov.generate(model, rng)
    return _apply_template(raw, style_cfg, rng)


def generate_entity_name_seeded(
    cultures: list[tuple[Culture, float]],
    style: NameStyle,
    seed: int,
    context_key: str = "",
) -> str:
    """Deterministic name generation for a specific entity context.

    Creates its own isolated Random from *seed* + *context_key* so that
    callers can call this without affecting any shared RNG state.
    """
    from starloom.rng import hash64

    rng_seed = hash64(f"{seed}:entity-name:{context_key}:{style.value}")
    rng = random.Random(rng_seed)
    return generate_entity_name(cultures, style, rng)
