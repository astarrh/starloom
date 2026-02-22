"""Character-level n-gram Markov model for name generation.

Design summary (design doc §12):
- Trained on a list of example name strings.
- Uses character bigrams (n=2) with optional trigram blending.
- Generation follows the learned transition probabilities.
- Drift perturbs the frequency table deterministically from a seed.
- The trained model is a plain dict — JSON-serialisable, storable in CultureSpec.

Model wire format (stored in Culture.markov_model / CultureSpec.markov_model_data):
    {
        "n":        int,                   # order (default 2)
        "starts":   list[str],             # possible start n-grams
        "table":    dict[str, dict[str, float]],  # context -> {next_char: weight}
        "min_len":  int,
        "max_len":  int,
    }
"""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Any

# Sentinel used as the implicit end-of-word marker.
_END = "\x00"
# Sentinel for start-of-word padding.
_START = "\x01"

MIN_EXAMPLES = 4
DEFAULT_ORDER = 2


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


def train(examples: list[str], *, order: int = DEFAULT_ORDER) -> dict[str, Any]:
    """Train a character n-gram model on a list of example strings.

    Parameters
    ----------
    examples:
        Name strings.  Must have at least MIN_EXAMPLES entries.
    order:
        Context window size (bigrams = 2, trigrams = 3).

    Returns
    -------
    JSON-serialisable model dict.
    """
    if len(examples) < MIN_EXAMPLES:
        raise ValueError(
            f"At least {MIN_EXAMPLES} examples required to train a culture model, "
            f"got {len(examples)}."
        )

    # Pad each word with start sentinels so the model learns valid beginnings.
    padded = [_START * order + w + _END for w in examples]

    table: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    starts: list[str] = []

    for word in padded:
        # Record valid start n-grams (the first real context after padding).
        start_ctx = word[:order]
        if start_ctx not in starts:
            starts.append(start_ctx)

        for i in range(len(word) - order):
            ctx = word[i : i + order]
            next_char = word[i + order]
            table[ctx][next_char] += 1.0

    # Normalise to probabilities.
    normalised: dict[str, dict[str, float]] = {}
    for ctx, transitions in table.items():
        total = sum(transitions.values())
        normalised[ctx] = {ch: w / total for ch, w in transitions.items()}

    return {
        "n": order,
        "starts": sorted(starts),  # sorted for determinism
        "table": normalised,
        "min_len": 3,
        "max_len": 12,
    }


# ---------------------------------------------------------------------------
# Drift
# ---------------------------------------------------------------------------


def apply_drift(model: dict[str, Any], drift: float, rng: random.Random) -> dict[str, Any]:
    """Return a new model with transition weights perturbed by *drift*.

    drift=0.0 → identical model.
    drift=1.0 → weights shuffled heavily; broad phonemic shape preserved.

    Perturbation strategy: for each transition distribution, randomly
    redistribute *drift* fraction of weight among all valid next characters.
    This preserves the set of reachable characters while shifting probabilities.
    """
    if drift == 0.0:
        return model

    new_table: dict[str, dict[str, float]] = {}
    for ctx, transitions in model["table"].items():
        chars = sorted(transitions.keys())
        weights = [transitions[c] for c in chars]
        n = len(chars)

        if n == 1:
            # Nothing to redistribute — only one transition possible.
            new_table[ctx] = dict(transitions)
            continue

        # Amount to move away from the base distribution.
        shift_total = drift
        # Generate random deltas (sum to shift_total).
        deltas = [rng.random() for _ in chars]
        delta_sum = sum(deltas)
        deltas = [d / delta_sum * shift_total for d in deltas]

        # Blend: (1 - drift) * original + drift * random redistribution
        blended = [(1.0 - drift) * w + d for w, d in zip(weights, deltas, strict=True)]

        # Re-normalise to ensure they sum to 1.0.
        total = sum(blended)
        new_table[ctx] = {c: w / total for c, w in zip(chars, blended, strict=True)}

    return {**model, "table": new_table}


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def generate(model: dict[str, Any], rng: random.Random) -> str:
    """Generate one name string from a trained (possibly drifted) model.

    Returns a string without sentinel characters.
    Loops until a valid-length result is produced (bounded by 100 attempts).
    Raises RuntimeError if no valid name can be generated.
    """
    order: int = model["n"]
    min_len: int = model["min_len"]
    max_len: int = model["max_len"]
    starts: list[str] = model["starts"]
    table: dict[str, dict[str, float]] = model["table"]

    for _ in range(100):
        ctx = rng.choice(sorted(starts))
        chars: list[str] = []

        for _ in range(max_len + order + 5):
            transitions = table.get(ctx)
            if transitions is None:
                break
            next_chars = sorted(transitions.keys())
            weights = [transitions[c] for c in next_chars]
            chosen = rng.choices(next_chars, weights=weights, k=1)[0]
            if chosen == _END:
                break
            chars.append(chosen)
            ctx = (ctx + chosen)[-order:]

        name = "".join(chars).replace(_START, "").strip()
        if min_len <= len(name) <= max_len:
            return name.capitalize()

    raise RuntimeError("Markov model failed to generate a valid name within retry budget.")


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def supplement_sparse_model(model: dict[str, Any], examples: list[str]) -> dict[str, Any]:
    """Pad a model with character-level unigram fallbacks.

    Used when the example set is near the minimum (4–6 words) and the table
    has gaps.  Merges the sparse model with a unigram baseline trained on the
    same examples, weighted 80/20 in favour of the original.
    """
    base = train(examples, order=1)
    merged_table: dict[str, dict[str, float]] = {}

    all_ctxs = set(model["table"]) | set(base["table"])
    for ctx in all_ctxs:
        orig = model["table"].get(ctx, {})
        fallback = base["table"].get(ctx, {})
        all_chars = set(orig) | set(fallback)
        merged: dict[str, float] = {}
        for ch in all_chars:
            merged[ch] = 0.8 * orig.get(ch, 0.0) + 0.2 * fallback.get(ch, 0.0)
        total = sum(merged.values())
        merged_table[ctx] = {c: w / total for c, w in merged.items()}

    return {**model, "table": merged_table}
