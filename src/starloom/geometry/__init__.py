"""Pure spatial and character-axis query helpers (design doc §14.2).

All functions are stateless — they accept a Galaxy and return results; nothing
is stored between calls.  ``z`` coordinates exist on systems and planets for
visual presentation only; all distance calculations use only ``(x, y)``.

Public API
----------
Spatial queries::

    systems_within_radius(galaxy, origin, radius)
    nearest_systems(galaxy, origin, count=5)
    system_distance(galaxy, system_id_a, system_id_b)

Distinctiveness queries::

    planets_by_distinctiveness(galaxy, *, systems=None, threshold=0.0)
    locations_by_distinctiveness(galaxy, *, systems=None, threshold=0.0)
    nodes_by_distinctiveness(galaxy, *, systems=None, threshold=0.0)

Character-axis queries::

    sectors_by_character(galaxy, *, systems=None,
                         remoteness_min=None, remoteness_max=None,
                         urbanization_min=None, urbanization_max=None,
                         hostility_min=None, hostility_max=None)
    nodes_by_character(galaxy, *, systems=None,
                       remoteness_min=None, remoteness_max=None,
                       urbanization_min=None, urbanization_max=None,
                       hostility_min=None, hostility_max=None)
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starloom.domain.models import (
        Galaxy,
        Location,
        Node,
        Planet,
        Sector,
        SolarSystem,
    )

# ---------------------------------------------------------------------------
# Origin type alias
# ---------------------------------------------------------------------------

# "origin" in spatial helpers accepts either a system id or a (x, y) pair.
Origin = str | tuple[float, float]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _euclidean(ax: float, ay: float, bx: float, by: float) -> float:
    return math.sqrt((bx - ax) ** 2 + (by - ay) ** 2)


def _resolve_origin(galaxy: "Galaxy", origin: Origin) -> tuple[float, float]:
    """Return (x, y) for *origin*, which may be a system id or a coordinate pair."""
    if isinstance(origin, tuple):
        return float(origin[0]), float(origin[1])
    for system in galaxy.systems:
        if system.id == origin:
            return system.x, system.y
    raise KeyError(f"System id not found in galaxy: {origin!r}")


def _iter_systems(galaxy: "Galaxy", systems: "list[SolarSystem] | None") -> "list[SolarSystem]":
    return list(systems) if systems is not None else list(galaxy.systems)


# ---------------------------------------------------------------------------
# Spatial queries
# ---------------------------------------------------------------------------


def system_distance(galaxy: "Galaxy", system_id_a: str, system_id_b: str) -> float:
    """Return the Euclidean distance between two systems (x, y only).

    Raises
    ------
    KeyError
        If either id is not found in the galaxy.
    """
    ox, oy = _resolve_origin(galaxy, system_id_a)
    tx, ty = _resolve_origin(galaxy, system_id_b)
    return _euclidean(ox, oy, tx, ty)


def systems_within_radius(
    galaxy: "Galaxy",
    origin: Origin,
    radius: float,
    *,
    include_origin: bool = False,
) -> "list[SolarSystem]":
    """Return all systems within *radius* of *origin*.

    Parameters
    ----------
    galaxy:
        The galaxy to query.
    origin:
        Either a system id (``str``) or a ``(x, y)`` coordinate pair.
    radius:
        Maximum Euclidean distance (x, y only).
    include_origin:
        When *origin* is a system id, whether to include that system itself
        in the results.  Defaults to ``False``.

    Returns
    -------
    list[SolarSystem]
        Sorted by ascending distance from *origin*.
    """
    ox, oy = _resolve_origin(galaxy, origin)
    origin_id = origin if isinstance(origin, str) else None

    results: list[tuple[float, SolarSystem]] = []
    for system in galaxy.systems:
        if not include_origin and origin_id == system.id:
            continue
        dist = _euclidean(ox, oy, system.x, system.y)
        if dist <= radius:
            results.append((dist, system))

    results.sort(key=lambda t: t[0])
    return [s for _, s in results]


def nearest_systems(
    galaxy: "Galaxy",
    origin: Origin,
    count: int = 5,
    *,
    include_origin: bool = False,
) -> "list[SolarSystem]":
    """Return the *count* nearest systems to *origin*.

    Parameters
    ----------
    galaxy:
        The galaxy to query.
    origin:
        Either a system id (``str``) or a ``(x, y)`` coordinate pair.
    count:
        Number of nearest systems to return.
    include_origin:
        When *origin* is a system id, whether to include that system itself.
        Defaults to ``False``.

    Returns
    -------
    list[SolarSystem]
        Sorted by ascending distance; length ≤ *count*.
    """
    ox, oy = _resolve_origin(galaxy, origin)
    origin_id = origin if isinstance(origin, str) else None

    results: list[tuple[float, SolarSystem]] = []
    for system in galaxy.systems:
        if not include_origin and origin_id == system.id:
            continue
        dist = _euclidean(ox, oy, system.x, system.y)
        results.append((dist, system))

    results.sort(key=lambda t: t[0])
    return [s for _, s in results[:count]]


# ---------------------------------------------------------------------------
# Distinctiveness queries
# ---------------------------------------------------------------------------


def planets_by_distinctiveness(
    galaxy: "Galaxy",
    *,
    systems: "list[SolarSystem] | None" = None,
    threshold: float = 0.0,
) -> "list[Planet]":
    """Return planets with ``distinctiveness >= threshold``, descending.

    Parameters
    ----------
    galaxy:
        The galaxy to query.
    systems:
        Restrict the search to these systems.  ``None`` searches all systems.
    threshold:
        Minimum distinctiveness value (inclusive).  Defaults to ``0.0``
        (returns all planets).
    """
    result: list[Planet] = []
    for system in _iter_systems(galaxy, systems):
        for planet in system.planets:
            if planet.distinctiveness >= threshold:
                result.append(planet)
    result.sort(key=lambda p: p.distinctiveness, reverse=True)
    return result


def locations_by_distinctiveness(
    galaxy: "Galaxy",
    *,
    systems: "list[SolarSystem] | None" = None,
    threshold: float = 0.0,
) -> "list[Location]":
    """Return locations with ``distinctiveness >= threshold``, descending."""
    result: list[Location] = []
    for system in _iter_systems(galaxy, systems):
        for planet in system.planets:
            for sector in planet.sectors:
                for location in sector.locations:
                    if location.distinctiveness >= threshold:
                        result.append(location)
    result.sort(key=lambda loc: loc.distinctiveness, reverse=True)
    return result


def nodes_by_distinctiveness(
    galaxy: "Galaxy",
    *,
    systems: "list[SolarSystem] | None" = None,
    threshold: float = 0.0,
) -> "list[Node]":
    """Return nodes with ``distinctiveness >= threshold``, descending."""
    result: list[Node] = []
    for system in _iter_systems(galaxy, systems):
        for planet in system.planets:
            for sector in planet.sectors:
                for location in sector.locations:
                    for node in location.nodes:
                        if node.distinctiveness >= threshold:
                            result.append(node)
    result.sort(key=lambda n: n.distinctiveness, reverse=True)
    return result


# ---------------------------------------------------------------------------
# Character-axis queries
# ---------------------------------------------------------------------------


def _sector_matches(
    sector: "Sector",
    remoteness_min: float | None,
    remoteness_max: float | None,
    urbanization_min: float | None,
    urbanization_max: float | None,
    hostility_min: float | None,
    hostility_max: float | None,
) -> bool:
    if remoteness_min is not None and sector.remoteness < remoteness_min:
        return False
    if remoteness_max is not None and sector.remoteness > remoteness_max:
        return False
    if urbanization_min is not None and sector.urbanization < urbanization_min:
        return False
    if urbanization_max is not None and sector.urbanization > urbanization_max:
        return False
    if hostility_min is not None and sector.hostility < hostility_min:
        return False
    if hostility_max is not None and sector.hostility > hostility_max:
        return False
    return True


def sectors_by_character(
    galaxy: "Galaxy",
    *,
    systems: "list[SolarSystem] | None" = None,
    remoteness_min: float | None = None,
    remoteness_max: float | None = None,
    urbanization_min: float | None = None,
    urbanization_max: float | None = None,
    hostility_min: float | None = None,
    hostility_max: float | None = None,
) -> "list[Sector]":
    """Return sectors matching all specified character-axis constraints.

    All threshold parameters are optional and combinable.  An absent parameter
    places no constraint on that axis.

    Returns
    -------
    list[Sector]
        Sorted by descending average deviation from the specified midpoints
        (best match first).  When no constraints are given, all sectors are
        returned in stable (galaxy-traversal) order.
    """
    results: list[Sector] = []
    for system in _iter_systems(galaxy, systems):
        for planet in system.planets:
            for sector in planet.sectors:
                if _sector_matches(
                    sector,
                    remoteness_min, remoteness_max,
                    urbanization_min, urbanization_max,
                    hostility_min, hostility_max,
                ):
                    results.append(sector)
    return results


def nodes_by_character(
    galaxy: "Galaxy",
    *,
    systems: "list[SolarSystem] | None" = None,
    remoteness_min: float | None = None,
    remoteness_max: float | None = None,
    urbanization_min: float | None = None,
    urbanization_max: float | None = None,
    hostility_min: float | None = None,
    hostility_max: float | None = None,
) -> "list[Node]":
    """Return nodes in sectors matching all specified character-axis constraints.

    Node eligibility is determined by its parent sector's character axes.

    Returns
    -------
    list[Node]
        In stable galaxy-traversal order.
    """
    results: list[Node] = []
    for system in _iter_systems(galaxy, systems):
        for planet in system.planets:
            for sector in planet.sectors:
                if not _sector_matches(
                    sector,
                    remoteness_min, remoteness_max,
                    urbanization_min, urbanization_max,
                    hostility_min, hostility_max,
                ):
                    continue
                for location in sector.locations:
                    for node in location.nodes:
                        results.append(node)
    return results
