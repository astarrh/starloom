"""Tests for geometry query helpers (Phase 05)."""

from __future__ import annotations

import math

import pytest

from starloom.domain.models import (
    Galaxy,
    Location,
    Node,
    Planet,
    Sector,
    SolarSystem,
)
from starloom.domain.types import (
    ClimateType,
    LocationType,
    NodeType,
    PlanetClass,
    Size,
    TopographyType,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _node(idx: int, loc_id: str, distinctiveness: float = 0.5) -> Node:
    return Node(
        id=f"{loc_id}-n{idx}",
        name=f"Node {idx}",
        node_type=NodeType.GENERIC,
        in_town=True,
        distinctiveness=distinctiveness,
    )


def _location(idx: int, sec_id: str, distinctiveness: float = 0.5) -> Location:
    loc_id = f"{sec_id}-loc{idx}"
    return Location(
        id=loc_id,
        name=f"Location {idx}",
        location_type=LocationType.TRADING,
        size=Size.MEDIUM,
        features=(),
        distinctiveness=distinctiveness,
        nodes=(_node(0, loc_id, distinctiveness),),
    )


def _sector(
    idx: int,
    planet_id: str,
    *,
    hostility: float = 0.2,
    remoteness: float = 0.3,
    urbanization: float = 0.5,
    density: int = 5,
) -> Sector:
    sec_id = f"{planet_id}-sec{idx}"
    return Sector(
        id=sec_id,
        name=f"Sector {idx}",
        topography=TopographyType.PLAINS,
        climate=ClimateType.TEMPERATE,
        density=density,
        urbanization=urbanization,
        hostility=hostility,
        remoteness=remoteness,
        locations=(_location(0, sec_id),),
    )


def _planet(
    idx: int,
    system_id: str,
    x: float = 0.0,
    y: float = 0.0,
    distinctiveness: float = 0.5,
    sectors: tuple[Sector, ...] = (),
) -> Planet:
    return Planet(
        id=f"{system_id}-pl{idx:03d}",
        name=f"Planet {idx}",
        size=Size.MEDIUM,
        classification=PlanetClass.TELLURIC,
        x=x, y=y, z=0.0,
        parent_planet_id=None,
        distinctiveness=distinctiveness,
        sectors=sectors,
    )


def _system(
    sys_id: str,
    x: float,
    y: float,
    planets: tuple[Planet, ...] = (),
) -> SolarSystem:
    return SolarSystem(
        id=sys_id,
        name=sys_id,
        size=Size.MEDIUM,
        x=x, y=y, z=0.0,
        culture_ids=(),
        planets=planets,
    )


def _galaxy(*systems: SolarSystem) -> Galaxy:
    return Galaxy(
        seed=0,
        config_version="0.1",
        content_pack_version="none",
        cultures={},
        systems=tuple(systems),
        metadata={},
    )


# Known coordinate layout for spatial tests:
#
#   A at (0, 0)
#   B at (3, 4)   → dist from A = 5.0
#   C at (10, 0)  → dist from A = 10.0
#   D at (100, 0) → dist from A = 100.0

@pytest.fixture()
def four_system_galaxy() -> Galaxy:
    sa = _system("sys-A", 0.0, 0.0)
    sb = _system("sys-B", 3.0, 4.0)
    sc = _system("sys-C", 10.0, 0.0)
    sd = _system("sys-D", 100.0, 0.0)
    return _galaxy(sa, sb, sc, sd)


# ---------------------------------------------------------------------------
# system_distance
# ---------------------------------------------------------------------------


class TestSystemDistance:
    def test_distance_known_pair(self, four_system_galaxy: Galaxy) -> None:
        from starloom.geometry import system_distance
        d = system_distance(four_system_galaxy, "sys-A", "sys-B")
        assert d == pytest.approx(5.0)

    def test_distance_symmetry(self, four_system_galaxy: Galaxy) -> None:
        from starloom.geometry import system_distance
        assert system_distance(four_system_galaxy, "sys-A", "sys-C") == \
               system_distance(four_system_galaxy, "sys-C", "sys-A")

    def test_distance_same_system(self, four_system_galaxy: Galaxy) -> None:
        from starloom.geometry import system_distance
        assert system_distance(four_system_galaxy, "sys-A", "sys-A") == pytest.approx(0.0)

    def test_z_not_used(self) -> None:
        from starloom.geometry import system_distance
        # Two systems with same (x, y) but different z should have distance 0
        sa = _system("s0", 0.0, 0.0)
        sb = SolarSystem(
            id="s1", name="s1", size=Size.SMALL,
            x=0.0, y=0.0, z=999.0,  # z differs wildly
            culture_ids=(), planets=(),
        )
        g = _galaxy(sa, sb)
        assert system_distance(g, "s0", "s1") == pytest.approx(0.0)

    def test_unknown_id_raises(self, four_system_galaxy: Galaxy) -> None:
        from starloom.geometry import system_distance
        with pytest.raises(KeyError):
            system_distance(four_system_galaxy, "sys-A", "does-not-exist")


# ---------------------------------------------------------------------------
# systems_within_radius
# ---------------------------------------------------------------------------


class TestSystemsWithinRadius:
    def test_radius_includes_close_excludes_far(self, four_system_galaxy: Galaxy) -> None:
        from starloom.geometry import systems_within_radius
        result = systems_within_radius(four_system_galaxy, "sys-A", radius=7.0)
        ids = [s.id for s in result]
        assert "sys-B" in ids   # dist = 5.0
        assert "sys-C" not in ids  # dist = 10.0
        assert "sys-D" not in ids  # dist = 100.0

    def test_origin_excluded_by_default(self, four_system_galaxy: Galaxy) -> None:
        from starloom.geometry import systems_within_radius
        result = systems_within_radius(four_system_galaxy, "sys-A", radius=1000.0)
        ids = [s.id for s in result]
        assert "sys-A" not in ids

    def test_origin_included_when_requested(self, four_system_galaxy: Galaxy) -> None:
        from starloom.geometry import systems_within_radius
        result = systems_within_radius(
            four_system_galaxy, "sys-A", radius=1000.0, include_origin=True
        )
        ids = [s.id for s in result]
        assert "sys-A" in ids

    def test_sorted_ascending(self, four_system_galaxy: Galaxy) -> None:
        from starloom.geometry import systems_within_radius
        result = systems_within_radius(four_system_galaxy, "sys-A", radius=1000.0)
        dists = [
            math.sqrt(s.x ** 2 + s.y ** 2)
            for s in result
        ]
        assert dists == sorted(dists)

    def test_coordinate_origin(self, four_system_galaxy: Galaxy) -> None:
        from starloom.geometry import systems_within_radius
        # origin as (x, y) tuple
        result = systems_within_radius(four_system_galaxy, (0.0, 0.0), radius=7.0)
        ids = [s.id for s in result]
        assert "sys-B" in ids
        assert "sys-A" in ids  # no origin to exclude when using coord

    def test_empty_result_when_radius_too_small(self, four_system_galaxy: Galaxy) -> None:
        from starloom.geometry import systems_within_radius
        result = systems_within_radius(four_system_galaxy, "sys-A", radius=0.1)
        assert result == []

    def test_radius_boundary_inclusive(self, four_system_galaxy: Galaxy) -> None:
        from starloom.geometry import systems_within_radius
        # sys-B is exactly 5.0 away; radius=5.0 should include it
        result = systems_within_radius(four_system_galaxy, "sys-A", radius=5.0)
        ids = [s.id for s in result]
        assert "sys-B" in ids


# ---------------------------------------------------------------------------
# nearest_systems
# ---------------------------------------------------------------------------


class TestNearestSystems:
    def test_nearest_returns_correct_count(self, four_system_galaxy: Galaxy) -> None:
        from starloom.geometry import nearest_systems
        result = nearest_systems(four_system_galaxy, "sys-A", count=2)
        assert len(result) == 2

    def test_nearest_correct_order(self, four_system_galaxy: Galaxy) -> None:
        from starloom.geometry import nearest_systems
        result = nearest_systems(four_system_galaxy, "sys-A", count=3)
        ids = [s.id for s in result]
        assert ids == ["sys-B", "sys-C", "sys-D"]

    def test_nearest_excludes_origin(self, four_system_galaxy: Galaxy) -> None:
        from starloom.geometry import nearest_systems
        result = nearest_systems(four_system_galaxy, "sys-A", count=10)
        ids = [s.id for s in result]
        assert "sys-A" not in ids

    def test_nearest_includes_origin_when_requested(self, four_system_galaxy: Galaxy) -> None:
        from starloom.geometry import nearest_systems
        result = nearest_systems(
            four_system_galaxy, "sys-A", count=10, include_origin=True
        )
        ids = [s.id for s in result]
        assert "sys-A" in ids

    def test_count_larger_than_galaxy(self, four_system_galaxy: Galaxy) -> None:
        from starloom.geometry import nearest_systems
        result = nearest_systems(four_system_galaxy, "sys-A", count=999)
        assert len(result) == 3  # 4 systems minus origin

    def test_coordinate_origin(self, four_system_galaxy: Galaxy) -> None:
        from starloom.geometry import nearest_systems
        result = nearest_systems(four_system_galaxy, (0.0, 0.0), count=1)
        assert result[0].id == "sys-A"


# ---------------------------------------------------------------------------
# planets_by_distinctiveness
# ---------------------------------------------------------------------------


class TestPlanetsByDistinctiveness:
    def test_returns_descending(self) -> None:
        from starloom.geometry import planets_by_distinctiveness
        sa = _system("s0", 0.0, 0.0, planets=(
            _planet(0, "s0", distinctiveness=0.9),
            _planet(1, "s0", x=1.0, distinctiveness=0.3),
        ))
        g = _galaxy(sa)
        result = planets_by_distinctiveness(g)
        assert result[0].distinctiveness >= result[1].distinctiveness

    def test_threshold_filters(self) -> None:
        from starloom.geometry import planets_by_distinctiveness
        sa = _system("s0", 0.0, 0.0, planets=(
            _planet(0, "s0", distinctiveness=0.9),
            _planet(1, "s0", x=1.0, distinctiveness=0.3),
        ))
        g = _galaxy(sa)
        result = planets_by_distinctiveness(g, threshold=0.8)
        assert all(p.distinctiveness >= 0.8 for p in result)
        assert len(result) == 1

    def test_systems_filter(self) -> None:
        from starloom.geometry import planets_by_distinctiveness
        sa = _system("s0", 0.0, 0.0, planets=(_planet(0, "s0", distinctiveness=0.9),))
        sb = _system("s1", 10.0, 0.0, planets=(_planet(0, "s1", x=10.0, distinctiveness=0.2),))
        g = _galaxy(sa, sb)
        result = planets_by_distinctiveness(g, systems=[sa])
        assert all(p.id.startswith("s0") for p in result)


# ---------------------------------------------------------------------------
# locations_by_distinctiveness
# ---------------------------------------------------------------------------


class TestLocationsByDistinctiveness:
    def test_returns_locations_above_threshold(self) -> None:
        from starloom.geometry import locations_by_distinctiveness
        sec = _sector(0, "s0-pl000", hostility=0.1, remoteness=0.1, urbanization=0.9)
        pl = _planet(0, "s0", sectors=(sec,))
        sa = _system("s0", 0.0, 0.0, planets=(pl,))
        g = _galaxy(sa)
        # All generated locations have distinctiveness = 0.5 (default in fixture)
        result = locations_by_distinctiveness(g, threshold=0.3)
        assert len(result) >= 1

    def test_empty_when_threshold_too_high(self) -> None:
        from starloom.geometry import locations_by_distinctiveness
        sec = _sector(0, "s0-pl000")
        pl = _planet(0, "s0", sectors=(sec,))
        sa = _system("s0", 0.0, 0.0, planets=(pl,))
        g = _galaxy(sa)
        result = locations_by_distinctiveness(g, threshold=0.99)
        assert result == []


# ---------------------------------------------------------------------------
# nodes_by_distinctiveness
# ---------------------------------------------------------------------------


class TestNodesByDistinctiveness:
    def test_returns_nodes_above_threshold(self) -> None:
        from starloom.geometry import nodes_by_distinctiveness
        sec = _sector(0, "s0-pl000")
        pl = _planet(0, "s0", sectors=(sec,))
        sa = _system("s0", 0.0, 0.0, planets=(pl,))
        g = _galaxy(sa)
        result = nodes_by_distinctiveness(g, threshold=0.0)
        assert len(result) >= 1

    def test_descending_order(self) -> None:
        from starloom.geometry import nodes_by_distinctiveness
        sec = _sector(0, "s0-pl000")
        pl = _planet(0, "s0", sectors=(sec,))
        sa = _system("s0", 0.0, 0.0, planets=(pl,))
        g = _galaxy(sa)
        result = nodes_by_distinctiveness(g)
        dists = [n.distinctiveness for n in result]
        assert dists == sorted(dists, reverse=True)


# ---------------------------------------------------------------------------
# sectors_by_character
# ---------------------------------------------------------------------------


class TestSectorsByCharacter:
    def _galaxy_with_sectors(self) -> Galaxy:
        # Sector A: frontier (high remoteness, low urbanization, low hostility)
        sec_a = Sector(
            id="s0-pl000-secA", name="A",
            topography=TopographyType.PEAKS, climate=ClimateType.ARID,
            density=2, urbanization=0.1, hostility=0.1, remoteness=0.9,
            locations=(),
        )
        # Sector B: urban centre (low remoteness, high urbanization)
        sec_b = Sector(
            id="s0-pl000-secB", name="B",
            topography=TopographyType.PLAINS, climate=ClimateType.TEMPERATE,
            density=8, urbanization=0.9, hostility=0.2, remoteness=0.1,
            locations=(),
        )
        # Sector C: hostile wilderness
        sec_c = Sector(
            id="s0-pl000-secC", name="C",
            topography=TopographyType.CANYON, climate=ClimateType.VOLCANIC,
            density=3, urbanization=0.2, hostility=0.9, remoteness=0.7,
            locations=(),
        )
        pl = Planet(
            id="s0-pl000", name="P0", size=Size.LARGE,
            classification=PlanetClass.TELLURIC,
            x=0.0, y=0.0, z=0.0,
            parent_planet_id=None, distinctiveness=0.5,
            sectors=(sec_a, sec_b, sec_c),
        )
        sys = _system("s0", 0.0, 0.0, planets=(pl,))
        return _galaxy(sys)

    def test_no_constraints_returns_all(self) -> None:
        from starloom.geometry import sectors_by_character
        g = self._galaxy_with_sectors()
        result = sectors_by_character(g)
        assert len(result) == 3

    def test_remoteness_min_filter(self) -> None:
        from starloom.geometry import sectors_by_character
        g = self._galaxy_with_sectors()
        result = sectors_by_character(g, remoteness_min=0.7)
        assert all(s.remoteness >= 0.7 for s in result)
        assert len(result) == 2  # A and C

    def test_urbanization_max_filter(self) -> None:
        from starloom.geometry import sectors_by_character
        g = self._galaxy_with_sectors()
        result = sectors_by_character(g, urbanization_max=0.3)
        ids = {s.id for s in result}
        assert "s0-pl000-secA" in ids
        assert "s0-pl000-secC" in ids
        assert "s0-pl000-secB" not in ids

    def test_hostility_min_filter(self) -> None:
        from starloom.geometry import sectors_by_character
        g = self._galaxy_with_sectors()
        result = sectors_by_character(g, hostility_min=0.8)
        assert len(result) == 1
        assert result[0].id == "s0-pl000-secC"

    def test_combined_constraints(self) -> None:
        from starloom.geometry import sectors_by_character
        g = self._galaxy_with_sectors()
        # frontier: high remoteness, low urbanization
        result = sectors_by_character(
            g, remoteness_min=0.7, urbanization_max=0.3
        )
        ids = {s.id for s in result}
        assert "s0-pl000-secA" in ids  # matches both
        # C has remoteness=0.7 and urbanization=0.2, also matches
        assert "s0-pl000-secC" in ids

    def test_no_matches_returns_empty(self) -> None:
        from starloom.geometry import sectors_by_character
        g = self._galaxy_with_sectors()
        result = sectors_by_character(
            g, hostility_min=0.99, remoteness_min=0.99
        )
        assert result == []

    def test_systems_filter(self) -> None:
        from starloom.geometry import sectors_by_character
        g = self._galaxy_with_sectors()
        result = sectors_by_character(g, systems=[])
        assert result == []


# ---------------------------------------------------------------------------
# nodes_by_character
# ---------------------------------------------------------------------------


class TestNodesByCharacter:
    def _galaxy_with_nodes(self) -> Galaxy:
        # Low hostility, high urbanization sector → trade nodes
        sec_trade = Sector(
            id="s0-pl000-sec0", name="Trade",
            topography=TopographyType.PLAINS, climate=ClimateType.TEMPERATE,
            density=8, urbanization=0.9, hostility=0.1, remoteness=0.1,
            locations=(
                Location(
                    id="s0-pl000-sec0-loc0", name="L0",
                    location_type=LocationType.CITY,
                    size=Size.LARGE, features=(), distinctiveness=0.7,
                    nodes=(
                        Node(
                            id="s0-pl000-sec0-loc0-n0", name="N0",
                            node_type=NodeType.GENERIC, in_town=True,
                            distinctiveness=0.7,
                        ),
                    ),
                ),
            ),
        )
        # High hostility sector → no nodes should appear with hostility_max=0.3
        sec_wild = Sector(
            id="s0-pl000-sec1", name="Wild",
            topography=TopographyType.CANYON, climate=ClimateType.VOLCANIC,
            density=2, urbanization=0.1, hostility=0.9, remoteness=0.8,
            locations=(
                Location(
                    id="s0-pl000-sec1-loc0", name="L1",
                    location_type=LocationType.TRIBAL,
                    size=Size.SMALL, features=(), distinctiveness=0.2,
                    nodes=(
                        Node(
                            id="s0-pl000-sec1-loc0-n0", name="N1",
                            node_type=NodeType.GENERIC, in_town=False,
                            distinctiveness=0.2,
                        ),
                    ),
                ),
            ),
        )
        pl = Planet(
            id="s0-pl000", name="P0", size=Size.LARGE,
            classification=PlanetClass.TELLURIC,
            x=0.0, y=0.0, z=0.0, parent_planet_id=None,
            distinctiveness=0.5,
            sectors=(sec_trade, sec_wild),
        )
        sys = _system("s0", 0.0, 0.0, planets=(pl,))
        return _galaxy(sys)

    def test_hostility_max_filters_nodes(self) -> None:
        from starloom.geometry import nodes_by_character
        g = self._galaxy_with_nodes()
        result = nodes_by_character(g, hostility_max=0.3)
        node_ids = {n.id for n in result}
        assert "s0-pl000-sec0-loc0-n0" in node_ids
        assert "s0-pl000-sec1-loc0-n0" not in node_ids

    def test_no_constraints_returns_all_nodes(self) -> None:
        from starloom.geometry import nodes_by_character
        g = self._galaxy_with_nodes()
        result = nodes_by_character(g)
        assert len(result) == 2
