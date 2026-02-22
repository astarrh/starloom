"""Culture construction paths and the standalone generate_name() utility.

Three construction paths (design doc §12.1):
    Path 1 — Example-driven:  create_culture_family(examples=..., ...)
    Path 2 — Procedural:      generate_culture_family(seed=..., ...)
    Path 3 — Single culture:  create_culture(examples=..., ...)

All three return identical, serialisable Culture / CultureFamily objects.
The generator stays stateless — Culture objects are owned by the developer.

generate_name() (design doc §12.5):
    Standalone utility for runtime name generation without a full generation pass.
    Deterministic when a seed is provided; non-reproducible when unseeded.
"""

from __future__ import annotations

import random
from typing import Any

from starloom.culture import markov as _markov
from starloom.domain.models import Culture, CultureFamily, StyleConfig
from starloom.domain.types import NameStyle
from starloom.rng import hash64, normalise_seed

# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class CultureError(ValueError):
    """Raised when culture construction arguments are invalid."""


# ---------------------------------------------------------------------------
# Default style config applied when no overrides are given.
# ---------------------------------------------------------------------------

_DEFAULT_STYLES: dict[NameStyle, StyleConfig] = {
    NameStyle.GENERIC: StyleConfig(min_length=4, max_length=10),
    NameStyle.PERSON: StyleConfig(min_length=4, max_length=9),
    NameStyle.RESIDENCE: StyleConfig(min_length=4, max_length=10, template="The + House"),
    NameStyle.BAR: StyleConfig(min_length=4, max_length=9, template="The +"),
}

# ---------------------------------------------------------------------------
# ID helpers
# ---------------------------------------------------------------------------


def _culture_id(family_id: str, index: int) -> str:
    return f"{family_id}-c{index:02d}"


def _family_id(name: str, seed: int | None) -> str:
    raw = f"family:{name}:{seed}"
    return f"fam-{hash64(raw) % 10**12:012d}"


# ---------------------------------------------------------------------------
# Path 3 — Single culture
# ---------------------------------------------------------------------------


def create_culture(
    examples: list[str],
    name: str,
    *,
    style_overrides: dict[NameStyle, StyleConfig] | None = None,
    order: int = 2,
) -> Culture:
    """Create a single Culture from a list of example name strings.

    Parameters
    ----------
    examples:
        At least 4 example names.  More examples (8–15) produce richer models.
    name:
        Developer-assigned label for this culture (not generated).
    style_overrides:
        Per-style length/template settings.  Defaults are applied for any
        style not explicitly overridden.
    order:
        Markov model order (default 2 = bigrams).
    """
    if len(examples) < _markov.MIN_EXAMPLES:
        raise CultureError(
            f"create_culture() requires at least {_markov.MIN_EXAMPLES} examples, "
            f"got {len(examples)}."
        )

    model = _markov.train(examples, order=order)
    if len(examples) <= 6:
        model = _markov.supplement_sparse_model(model, examples)

    styles = {**_DEFAULT_STYLES, **(style_overrides or {})}
    culture_id = f"fam-{hash64(f'single:{name}'):012d}-c00"

    return Culture(
        id=culture_id,
        name=name,
        markov_model=model,
        name_styles=styles,
        metadata={"origin_examples": list(examples), "order": order},
    )


# ---------------------------------------------------------------------------
# Path 1 — Example-driven family
# ---------------------------------------------------------------------------


def create_culture_family(
    examples: list[str],
    name: str,
    *,
    variant_count: int = 3,
    drift: float = 0.25,
    seed: int | str | None = None,
    style_overrides: dict[NameStyle, StyleConfig] | None = None,
    order: int = 2,
) -> CultureFamily:
    """Derive a CultureFamily from developer/player-supplied example names.

    Parameters
    ----------
    examples:
        At least 4 example names.
    name:
        Label for the family.
    variant_count:
        Number of sibling cultures to derive (each drifted independently).
    drift:
        How far siblings diverge from the base model (0.0–1.0).
        0.0 → identical siblings; 0.6–0.8 → distinct-but-related.
    seed:
        Seed for drift perturbation.  None → non-reproducible drift.
    style_overrides:
        Applied to all sibling cultures.
    order:
        Markov model order.
    """
    if len(examples) < _markov.MIN_EXAMPLES:
        raise CultureError(
            f"create_culture_family() requires at least {_markov.MIN_EXAMPLES} examples, "
            f"got {len(examples)}."
        )
    if not 0.0 <= drift <= 1.0:
        raise CultureError(f"drift must be in [0.0, 1.0], got {drift!r}.")
    if variant_count < 1:
        raise CultureError(f"variant_count must be ≥ 1, got {variant_count!r}.")

    int_seed = normalise_seed(seed) if seed is not None else None
    fam_id = _family_id(name, int_seed)

    base_model = _markov.train(examples, order=order)
    if len(examples) <= 6:
        base_model = _markov.supplement_sparse_model(base_model, examples)

    styles = {**_DEFAULT_STYLES, **(style_overrides or {})}

    cultures: list[Culture] = []
    for i in range(variant_count):
        if int_seed is not None:
            drift_seed = hash64(f"{int_seed}:drift:{i}")
            drift_rng = random.Random(drift_seed)
        else:
            drift_rng = random.Random()

        drifted = _markov.apply_drift(base_model, drift, drift_rng)
        cultures.append(
            Culture(
                id=_culture_id(fam_id, i),
                name=f"{name} {i}" if variant_count > 1 else name,
                markov_model=drifted,
                name_styles=styles,
                metadata={
                    "origin_examples": list(examples),
                    "drift": drift,
                    "variant_index": i,
                    "family_id": fam_id,
                    "order": order,
                },
            )
        )

    return CultureFamily(
        id=fam_id,
        name=name,
        cultures=tuple(cultures),
        base_examples=tuple(sorted(examples)),
        seed=int_seed,
    )


# ---------------------------------------------------------------------------
# Path 2 — Procedural family (seed-driven, no examples)
# ---------------------------------------------------------------------------

# Phoneme pool used to generate base examples procedurally.
_CONSONANTS = list("bcdfghjklmnprstvwz")
_VOWELS = list("aeiou")


def _procedural_examples(rng: random.Random, count: int = 12) -> list[str]:
    """Generate plausible-sounding seed words from a seeded RNG."""
    words: list[str] = []
    for _ in range(count):
        length = rng.randint(4, 8)
        letters: list[str] = []
        use_consonant = rng.choice([True, False])
        for _ in range(length):
            if use_consonant:
                letters.append(rng.choice(_CONSONANTS))
            else:
                letters.append(rng.choice(_VOWELS))
            use_consonant = not use_consonant
        words.append("".join(letters).capitalize())
    return words


def generate_culture_family(
    seed: int | str,
    name: str,
    *,
    variant_count: int = 4,
    drift: float = 0.3,
    style_overrides: dict[NameStyle, StyleConfig] | None = None,
    order: int = 2,
) -> CultureFamily:
    """Procedurally generate a CultureFamily — no example names required.

    The seed is used to generate a base example set internally.
    """
    int_seed = normalise_seed(seed)
    example_rng = random.Random(hash64(f"{int_seed}:proc-examples"))
    examples = _procedural_examples(example_rng)

    return create_culture_family(
        examples=examples,
        name=name,
        variant_count=variant_count,
        drift=drift,
        seed=int_seed,
        style_overrides=style_overrides,
        order=order,
    )


# ---------------------------------------------------------------------------
# Standalone name generation utility (design doc §12.5)
# ---------------------------------------------------------------------------


def generate_name(
    culture: Culture,
    style: NameStyle = NameStyle.GENERIC,
    *,
    seed: int | str | None = None,
) -> str:
    """Generate a single name consistent with the given Culture.

    Deterministic when ``seed`` is provided; non-reproducible otherwise.

    Parameters
    ----------
    culture:
        A runtime Culture object (e.g. from ``create_culture()`` or
        ``CultureSpec.to_runtime()``).
    style:
        Which naming style to use (GENERIC, PERSON, RESIDENCE, BAR).
    seed:
        Optional seed for reproducible output.  Suitable for game-critical
        names (quest givers, faction leaders, named ships).

    Returns
    -------
    str — the generated name, with any template applied.
    """
    if seed is not None:
        int_seed = normalise_seed(seed)
        rng = random.Random(hash64(f"{int_seed}:generate_name:{culture.id}:{style.value}"))
    else:
        rng = random.Random()

    style_cfg = culture.name_styles.get(style, _DEFAULT_STYLES.get(style, StyleConfig()))
    model = _apply_style_lengths(culture.markov_model, style_cfg)

    raw = _markov.generate(model, rng)
    return _apply_template(raw, style_cfg, rng)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _apply_style_lengths(model: dict[str, Any], style_cfg: StyleConfig) -> dict[str, Any]:
    """Return a shallow copy of model with min/max_len from the style config."""
    return {**model, "min_len": style_cfg.min_length, "max_len": style_cfg.max_length}


def _apply_template(raw: str, style_cfg: StyleConfig, rng: random.Random) -> str:
    """Apply a template string to the raw generated fragment.

    Template rules:
    - ``+`` is replaced by the generated fragment.
    - If the template contains two ``+`` markers, a second fragment is generated
      from the same model and inserted at the second marker position.
    - If no template, return raw as-is.
    """
    template = style_cfg.template
    if template is None:
        return raw

    parts = template.split("+")
    if len(parts) == 1:
        return raw  # no placeholder — shouldn't happen; return raw

    result = parts[0] + raw
    for extra_part in parts[1:]:
        result += extra_part
    return result
