"""Deterministic RNG infrastructure for starloom.

Design contract (from design doc §8):
- Root seed: int | str.  Strings are NFC-normalised, UTF-8 encoded, and
  SHA-256 hashed to a 64-bit unsigned integer (first 8 bytes, big-endian).
- Stream derivation: each pipeline stage gets an isolated Random instance via
      stream_seed = hash64(f"{root_seed}:{stream_name}:{context_key}")
      rng = random.Random(stream_seed)
- All input collections are sorted before random selection.
- RNG algorithm: Python random.Random (MT19937).  Any future change is a
  breaking reproducibility change requiring an engine major-version bump.
- In repro_mode="strict", the stream derivation includes engine version,
  content-pack hash, and metric formula versions.
"""

from __future__ import annotations

import hashlib
import random
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Engine version — included in strict-mode stream derivation.
# ---------------------------------------------------------------------------

ENGINE_MAJOR_VERSION: int = 0
ENGINE_VERSION: str = f"{ENGINE_MAJOR_VERSION}.1"

# Named streams used by the generation pipeline.
STREAM_SYSTEMS = "systems"
STREAM_PLANETS = "planets"
STREAM_SATELLITES = "satellites"
STREAM_SECTORS = "sectors"
STREAM_LOCATIONS = "locations"
STREAM_NODES = "nodes"
STREAM_NAMING = "naming"
STREAM_CULTURE = "culture"

ALL_STREAMS: frozenset[str] = frozenset(
    {
        STREAM_SYSTEMS,
        STREAM_PLANETS,
        STREAM_SATELLITES,
        STREAM_SECTORS,
        STREAM_LOCATIONS,
        STREAM_NODES,
        STREAM_NAMING,
        STREAM_CULTURE,
    }
)


# ---------------------------------------------------------------------------
# Seed normalisation
# ---------------------------------------------------------------------------


def hash64(data: str) -> int:
    """SHA-256 hash of a UTF-8 string → unsigned 64-bit int (first 8 bytes, big-endian)."""
    digest = hashlib.sha256(data.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big")


def normalise_seed(seed: int | str) -> int:
    """Convert a developer-supplied seed to a stable unsigned 64-bit integer.

    - int seeds are returned as-is (no truncation; Python ints are arbitrary precision).
    - str seeds are NFC-normalised, then hashed to 64-bit via SHA-256.
    """
    if isinstance(seed, int):
        return seed
    if isinstance(seed, str):
        normalised = unicodedata.normalize("NFC", seed)
        return hash64(normalised)
    raise TypeError(f"seed must be int or str, got {type(seed).__name__!r}")


# ---------------------------------------------------------------------------
# Stream derivation
# ---------------------------------------------------------------------------


def _stream_key(
    root_seed: int,
    stream_name: str,
    context_key: str,
    *,
    repro_mode: str = "compatible",
    content_pack_hash: str | None = None,
    metric_versions: dict[str, str] | None = None,
) -> int:
    """Derive a deterministic integer seed for one RNG stream.

    In 'compatible' mode the key is:
        "{root_seed}:{stream_name}:{context_key}"

    In 'strict' mode additional pins are appended:
        ":{engine_major}:{pack_hash}:{metric_pin}"
    """
    base = f"{root_seed}:{stream_name}:{context_key}"
    if repro_mode == "strict":
        pack_hash = content_pack_hash or ""
        metric_pin = ",".join(
            f"{k}={v}" for k, v in sorted((metric_versions or {}).items())
        )
        base = f"{base}:{ENGINE_MAJOR_VERSION}:{pack_hash}:{metric_pin}"
    return hash64(base)


def make_rng(
    root_seed: int,
    stream_name: str,
    context_key: str = "",
    *,
    repro_mode: str = "compatible",
    content_pack_hash: str | None = None,
    metric_versions: dict[str, str] | None = None,
) -> random.Random:
    """Create an isolated Random instance for a named pipeline stream.

    Parameters
    ----------
    root_seed:
        Normalised integer seed (output of normalise_seed()).
    stream_name:
        One of the ALL_STREAMS constants.
    context_key:
        Additional context that further isolates this stream (e.g. system id).
    repro_mode:
        "compatible" (default) or "strict".
    content_pack_hash:
        SHA-256 hex digest of the content pack directory — required in strict mode.
    metric_versions:
        Mapping of metric name → version string — required in strict mode.
    """
    seed = _stream_key(
        root_seed,
        stream_name,
        context_key,
        repro_mode=repro_mode,
        content_pack_hash=content_pack_hash,
        metric_versions=metric_versions,
    )
    rng = random.Random()
    rng.seed(seed)
    return rng


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def sorted_choice(rng: random.Random, population: list) -> object:  # type: ignore[type-arg]
    """Choose one item from population after sorting (preserves determinism)."""
    return rng.choice(sorted(population))


def sorted_sample(rng: random.Random, population: list, k: int) -> list:  # type: ignore[type-arg]
    """Sample k items from population after sorting (preserves determinism)."""
    return rng.sample(sorted(population), k)


def sorted_choices(
    rng: random.Random,
    population: list,  # type: ignore[type-arg]
    weights: list[float] | None = None,
    *,
    k: int = 1,
) -> list:  # type: ignore[type-arg]
    """Weighted random.choices() after sorting population + weights together."""
    if weights is not None:
        paired = sorted(zip(population, weights, strict=True), key=lambda t: t[0])
        population, weights = zip(*paired, strict=True)  # type: ignore[assignment]
        weights = list(weights)
    return rng.choices(list(population), weights=weights, k=k)
