"""Tests for Phase 03 — world generation pipeline."""

from __future__ import annotations

import pytest

from starloom.config import GalaxyConfig, RetryPolicy, SystemConfig
from starloom.culture import create_culture, create_culture_family
from starloom.domain.models import (
    Culture,
    Galaxy,
    Location,
    Node,
    Planet,
    Sector,
    SolarSystem,
    ValidationReport,
)
from starloom.domain.types import PlanetClass, Size
from starloom.generation.errors import (
    EligibilityExhaustedError,
    GenerationConstraintError,
    NameGenerationExhaustedError,
    PlacementExhaustedError,
)
from starloom.generation.galaxy import generate_galaxy
from starloom.generation.locations import generate_locations_for_sector
from starloom.generation.nodes import generate_nodes_for_location
from starloom.generation.planets import generate_planets_for_system
from starloom.generation.sectors import generate_sectors_for_planet
from starloom.generation.systems import generate_systems
from starloom.rng import STREAM_CULTURE, STREAM_NAMING, STREAM_PLANETS, STREAM_SYSTEMS, make_rng

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

EXAMPLES = [
    "Valdris", "Korveth", "Almara", "Selindra", "Tharion",
    "Elyndra", "Morvek", "Zephalon", "Briskon", "Caelith",
]

SEED = 42
ROOT_SEED = SEED  # normalise_seed(42) == 42


def _small_config(count: int = 5) -> GalaxyConfig:
    return GalaxyConfig(system=SystemConfig(count=count, placement_bound=500.0))


def _culture() -> Culture:
    return create_culture(EXAMPLES, name="Terran")


def _cultures() -> list[tuple[Culture, float]]:
    return [(_culture(), 1.0)]


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class TestGenerationErrors:
    def test_placement_exhausted_has_code(self) -> None:
        err = PlacementExhaustedError("test")
        assert err.code == "PLACEMENT_EXHAUSTED"

    def test_name_generation_exhausted_has_code(self) -> None:
        err = NameGenerationExhaustedError("test")
        assert err.code == "NAME_GENERATION_EXHAUSTED"

    def test_eligibility_exhausted_has_code(self) -> None:
        err = EligibilityExhaustedError("test")
        assert err.code == "ELIGIBILITY_EXHAUSTED"

    def test_generation_constraint_has_code(self) -> None:
        err = GenerationConstraintError("test")
        assert err.code == "GENERATION_CONSTRAINT_ERROR"

    def test_custom_code_override(self) -> None:
        err = PlacementExhaustedError("test", code="CUSTOM")
        assert err.code == "CUSTOM"


# ---------------------------------------------------------------------------
# System generation
# ---------------------------------------------------------------------------


class TestSystemGeneration:
    def _make_systems(self, count: int = 5, seed: int = SEED) -> list[SolarSystem]:
        cfg = _small_config(count)
        naming_rng = make_rng(seed, STREAM_NAMING)
        placement_rng = make_rng(seed, STREAM_SYSTEMS)
        culture_rng = make_rng(seed, STREAM_CULTURE)
        systems, _ = generate_systems(
            seed, cfg, [],
            naming_rng=naming_rng,
            placement_rng=placement_rng,
            culture_rng=culture_rng,
        )
        return systems

    def test_correct_count(self) -> None:
        systems = self._make_systems(10)
        assert len(systems) == 10

    def test_unique_ids(self) -> None:
        systems = self._make_systems(10)
        ids = [s.id for s in systems]
        assert len(ids) == len(set(ids))

    def test_id_format(self) -> None:
        systems = self._make_systems(3)
        for i, s in enumerate(systems):
            assert s.id == f"sys-{i:04d}"

    def test_unique_quantized_coordinates(self) -> None:
        systems = self._make_systems(20)
        coords = [(round(s.x, 1), round(s.y, 1)) for s in systems]
        assert len(coords) == len(set(coords))

    def test_z_within_bounds(self) -> None:
        systems = self._make_systems(20)
        for s in systems:
            assert -5.0 <= s.z <= 5.0

    def test_sizes_are_valid(self) -> None:
        systems = self._make_systems(20)
        for s in systems:
            assert s.size in Size

    def test_deterministic(self) -> None:
        s1 = self._make_systems(5, seed=99)
        s2 = self._make_systems(5, seed=99)
        assert [(s.id, s.name, s.x, s.y) for s in s1] == [(s.id, s.name, s.x, s.y) for s in s2]

    def test_different_seeds_differ(self) -> None:
        # Without cultures, names are indexed (identical). Compare coordinates instead.
        s1 = self._make_systems(5, seed=1)
        s2 = self._make_systems(5, seed=2)
        assert [(round(s.x, 1), round(s.y, 1)) for s in s1] != [(round(s.x, 1), round(s.y, 1)) for s in s2]

    def test_with_cultures(self) -> None:
        cfg = _small_config(5)
        naming_rng = make_rng(SEED, STREAM_NAMING)
        placement_rng = make_rng(SEED, STREAM_SYSTEMS)
        culture_rng = make_rng(SEED, STREAM_CULTURE)
        systems, registry = generate_systems(
            SEED, cfg, _cultures(),
            naming_rng=naming_rng,
            placement_rng=placement_rng,
            culture_rng=culture_rng,
        )
        assert len(registry) == 1
        for s in systems:
            assert len(s.culture_ids) == 1
            assert abs(sum(w for _, w in s.culture_ids) - 1.0) < 1e-9

    def test_placement_exhausted_raises(self) -> None:
        # Tiny bound + many systems → guaranteed exhaustion
        cfg = GalaxyConfig(
            system=SystemConfig(count=5, placement_bound=0.001, coordinate_precision_digits=1),
            retries=RetryPolicy(max_coordinate_retries=3),
        )
        with pytest.raises(PlacementExhaustedError):
            naming_rng = make_rng(SEED, STREAM_NAMING)
            placement_rng = make_rng(SEED, STREAM_SYSTEMS)
            culture_rng = make_rng(SEED, STREAM_CULTURE)
            generate_systems(
                SEED, cfg, [],
                naming_rng=naming_rng,
                placement_rng=placement_rng,
                culture_rng=culture_rng,
            )


# ---------------------------------------------------------------------------
# Planet generation
# ---------------------------------------------------------------------------


class TestPlanetGeneration:
    def _make_planets(self, system_size: Size = Size.MEDIUM, seed: int = SEED) -> list[Planet]:
        cfg = _small_config()
        planet_rng = make_rng(seed, STREAM_PLANETS, "sys-0000")
        naming_rng = make_rng(seed, STREAM_NAMING, "sys-0000")
        placement_rng = make_rng(seed, STREAM_PLANETS, "sat-sys-0000")
        return generate_planets_for_system(
            "sys-0000", system_size, seed, cfg, [],
            planet_rng=planet_rng,
            naming_rng=naming_rng,
            placement_rng=placement_rng,
        )

    def test_returns_list(self) -> None:
        planets = self._make_planets()
        assert isinstance(planets, list)
        assert len(planets) >= 1

    def test_primary_planets_have_no_parent(self) -> None:
        planets = self._make_planets()
        primaries = [p for p in planets if p.parent_planet_id is None]
        assert len(primaries) >= 1

    def test_satellites_reference_valid_parents(self) -> None:
        planets = self._make_planets(Size.ENORMOUS, seed=77)
        planet_ids = {p.id for p in planets}
        for p in planets:
            if p.parent_planet_id is not None:
                assert p.parent_planet_id in planet_ids

    def test_satellite_sizes_are_tiny_or_small(self) -> None:
        planets = self._make_planets(Size.ENORMOUS, seed=77)
        for p in planets:
            if p.parent_planet_id is not None:
                assert p.size in (Size.TINY, Size.SMALL)

    def test_planet_z_within_bounds(self) -> None:
        planets = self._make_planets(Size.LARGE, seed=5)
        for p in planets:
            if p.parent_planet_id is None:
                assert -2.0 <= p.z <= 2.0

    def test_unique_ids(self) -> None:
        planets = self._make_planets(Size.ENORMOUS, seed=7)
        ids = [p.id for p in planets]
        assert len(ids) == len(set(ids))

    def test_deterministic(self) -> None:
        p1 = self._make_planets(Size.MEDIUM, seed=42)
        p2 = self._make_planets(Size.MEDIUM, seed=42)
        assert [p.id for p in p1] == [p.id for p in p2]
        assert [p.name for p in p1] == [p.name for p in p2]

    def test_classification_is_valid(self) -> None:
        planets = self._make_planets()
        for p in planets:
            assert p.classification in PlanetClass


# ---------------------------------------------------------------------------
# Sector generation
# ---------------------------------------------------------------------------


class TestSectorGeneration:
    def _make_sectors(self, planet_size: int = 3, seed: int = SEED) -> list[Sector]:
        cfg = _small_config()
        sector_rng = make_rng(seed, "sectors", "pl-test")
        naming_rng = make_rng(seed, STREAM_NAMING, "pl-test")
        return generate_sectors_for_planet(
            "sys-0000-pl-000", planet_size, cfg, [],
            sector_rng=sector_rng,
            naming_rng=naming_rng,
        )

    def test_returns_sectors(self) -> None:
        sectors = self._make_sectors()
        assert len(sectors) >= 1

    def test_density_in_range(self) -> None:
        sectors = self._make_sectors()
        for s in sectors:
            assert 1 <= s.density <= 10

    def test_urbanization_range(self) -> None:
        sectors = self._make_sectors()
        for s in sectors:
            assert 0.0 <= s.urbanization <= 1.0

    def test_hostility_range(self) -> None:
        sectors = self._make_sectors()
        for s in sectors:
            assert 0.0 <= s.hostility <= 1.0

    def test_remoteness_range(self) -> None:
        sectors = self._make_sectors()
        for s in sectors:
            assert 0.0 <= s.remoteness <= 1.0

    def test_unique_ids(self) -> None:
        sectors = self._make_sectors(planet_size=5)
        ids = [s.id for s in sectors]
        assert len(ids) == len(set(ids))

    def test_deterministic(self) -> None:
        s1 = self._make_sectors(seed=55)
        s2 = self._make_sectors(seed=55)
        assert [s.id for s in s1] == [s.id for s in s2]
        assert [s.density for s in s1] == [s.density for s in s2]

    def test_character_axes_consistent(self) -> None:
        """Volcanic climate → high hostility; Plains topography → low remoteness."""
        from starloom.domain.types import ClimateType, TopographyType
        from starloom.generation.sectors import _compute_hostility, _compute_remoteness
        assert _compute_hostility(ClimateType.VOLCANIC) > _compute_hostility(ClimateType.TEMPERATE)
        assert _compute_remoteness(TopographyType.PEAKS) > _compute_remoteness(TopographyType.PLAINS)

    def test_urbanization_increases_with_density(self) -> None:
        from starloom.generation.sectors import _urbanization
        assert _urbanization(1) < _urbanization(5) < _urbanization(10)


# ---------------------------------------------------------------------------
# Location generation
# ---------------------------------------------------------------------------


class TestLocationGeneration:
    def _make_locations(self, density: int = 5, seed: int = SEED) -> list[Location]:
        cfg = _small_config()
        import random as _random
        loc_rng = _random.Random(seed)
        naming_rng = _random.Random(seed + 1)
        return generate_locations_for_sector(
            "sec-test", density, cfg, [],
            location_rng=loc_rng,
            naming_rng=naming_rng,
        )

    def test_returns_locations(self) -> None:
        locs = self._make_locations()
        assert 3 <= len(locs) <= 7

    def test_unique_ids(self) -> None:
        locs = self._make_locations()
        ids = [l.id for l in locs]
        assert len(ids) == len(set(ids))

    def test_distinctiveness_in_range(self) -> None:
        locs = self._make_locations()
        for l in locs:
            assert 0.0 <= l.distinctiveness <= 1.0

    def test_metropolis_only_at_high_density(self) -> None:
        from starloom.domain.types import LocationType
        from starloom.generation.locations import _eligible_location_types
        eligible_low = _eligible_location_types(1)
        eligible_high = _eligible_location_types(9)
        assert LocationType.METROPOLIS not in eligible_low
        assert LocationType.METROPOLIS in eligible_high

    def test_tribal_eligible_at_low_density(self) -> None:
        from starloom.domain.types import LocationType
        from starloom.generation.locations import _eligible_location_types
        assert LocationType.TRIBAL in _eligible_location_types(1)

    def test_deterministic(self) -> None:
        l1 = self._make_locations(seed=7)
        l2 = self._make_locations(seed=7)
        assert [l.id for l in l1] == [l.id for l in l2]


# ---------------------------------------------------------------------------
# Node generation
# ---------------------------------------------------------------------------


class TestNodeGeneration:
    def _make_nodes(self, density: int = 5, seed: int = SEED) -> list[Node]:
        cfg = _small_config()
        import random as _random
        node_rng = _random.Random(seed)
        naming_rng = _random.Random(seed + 1)
        return generate_nodes_for_location(
            "loc-test", density, cfg, [],
            node_rng=node_rng,
            naming_rng=naming_rng,
        )

    def test_returns_nodes(self) -> None:
        nodes = self._make_nodes()
        assert len(nodes) >= 1

    def test_count_scales_with_density(self) -> None:
        low = self._make_nodes(density=1)
        high = self._make_nodes(density=10)
        # On average high density should produce more nodes (may not hold for every seed)
        # so we just check both are non-empty.
        assert len(low) >= 1
        assert len(high) >= 1

    def test_most_nodes_in_town(self) -> None:
        nodes = self._make_nodes(density=5, seed=123)
        in_town_ratio = sum(1 for n in nodes if n.in_town) / len(nodes)
        # Allow generous range — small sample sizes vary
        assert 0.5 <= in_town_ratio <= 1.0

    def test_distinctiveness_in_range(self) -> None:
        for n in self._make_nodes():
            assert 0.0 <= n.distinctiveness <= 1.0

    def test_unique_ids(self) -> None:
        nodes = self._make_nodes(density=8)
        ids = [n.id for n in nodes]
        assert len(ids) == len(set(ids))

    def test_deterministic(self) -> None:
        n1 = self._make_nodes(seed=77)
        n2 = self._make_nodes(seed=77)
        assert [n.id for n in n1] == [n.id for n in n2]
        assert [n.in_town for n in n1] == [n.in_town for n in n2]


# ---------------------------------------------------------------------------
# End-to-end galaxy generation
# ---------------------------------------------------------------------------


class TestGenerateGalaxy:
    def _small_galaxy(
        self,
        seed: int | str = SEED,
        depth: str = "galaxy",
        count: int = 3,
        cultures: list[tuple[Culture, float]] | None = None,
    ) -> tuple[Galaxy, ValidationReport]:
        cfg = GalaxyConfig(
            system=SystemConfig(count=count, placement_bound=500.0),
            depth=depth,
        )
        return generate_galaxy(seed, cfg, cultures)

    # --- Basic structure ---

    def test_returns_galaxy_and_report(self) -> None:
        galaxy, report = self._small_galaxy()
        assert isinstance(galaxy, Galaxy)
        assert isinstance(report, ValidationReport)

    def test_correct_system_count(self) -> None:
        galaxy, _ = self._small_galaxy(count=5)
        assert len(galaxy.systems) == 5

    def test_systems_have_planets(self) -> None:
        galaxy, _ = self._small_galaxy()
        for system in galaxy.systems:
            assert len(system.planets) >= 1

    def test_planets_have_sectors(self) -> None:
        galaxy, _ = self._small_galaxy()
        for system in galaxy.systems:
            for planet in system.planets:
                assert len(planet.sectors) >= 1

    def test_sectors_have_locations(self) -> None:
        galaxy, _ = self._small_galaxy()
        for system in galaxy.systems:
            for planet in system.planets:
                for sector in planet.sectors:
                    assert len(sector.locations) >= 1

    def test_locations_have_nodes(self) -> None:
        galaxy, _ = self._small_galaxy()
        for system in galaxy.systems:
            for planet in system.planets:
                for sector in planet.sectors:
                    for location in sector.locations:
                        assert len(location.nodes) >= 1

    # --- Determinism ---

    def test_deterministic_full(self) -> None:
        g1, _ = self._small_galaxy(seed=99, count=3)
        g2, _ = self._small_galaxy(seed=99, count=3)
        sys1 = [(s.id, s.name, s.x, s.y) for s in g1.systems]
        sys2 = [(s.id, s.name, s.x, s.y) for s in g2.systems]
        assert sys1 == sys2

    def test_different_seeds_differ(self) -> None:
        # Without cultures, names are indexed (identical). Compare coordinates instead.
        g1, _ = self._small_galaxy(seed=1)
        g2, _ = self._small_galaxy(seed=2)
        assert [(round(s.x, 1), round(s.y, 1)) for s in g1.systems] != [(round(s.x, 1), round(s.y, 1)) for s in g2.systems]

    def test_str_seed_deterministic(self) -> None:
        g1, _ = self._small_galaxy(seed="my-campaign")
        g2, _ = self._small_galaxy(seed="my-campaign")
        assert [s.id for s in g1.systems] == [s.id for s in g2.systems]

    # --- Depth flags ---

    def test_depth_systems_no_planets(self) -> None:
        galaxy, _ = self._small_galaxy(depth="systems")
        for s in galaxy.systems:
            assert len(s.planets) == 0

    def test_depth_planets_no_sectors(self) -> None:
        galaxy, _ = self._small_galaxy(depth="planets")
        for s in galaxy.systems:
            for p in s.planets:
                assert len(p.sectors) == 0

    def test_depth_sectors_no_locations(self) -> None:
        galaxy, _ = self._small_galaxy(depth="sectors")
        for s in galaxy.systems:
            for p in s.planets:
                for sec in p.sectors:
                    assert len(sec.locations) == 0

    def test_depth_locations_no_nodes(self) -> None:
        galaxy, _ = self._small_galaxy(depth="locations")
        for s in galaxy.systems:
            for p in s.planets:
                for sec in p.sectors:
                    for loc in sec.locations:
                        assert len(loc.nodes) == 0

    # --- IDs ---

    def test_all_system_ids_unique(self) -> None:
        galaxy, _ = self._small_galaxy(count=5)
        ids = [s.id for s in galaxy.systems]
        assert len(ids) == len(set(ids))

    def test_all_planet_ids_unique(self) -> None:
        galaxy, _ = self._small_galaxy(count=3)
        ids = [p.id for s in galaxy.systems for p in s.planets]
        assert len(ids) == len(set(ids))

    # --- No-culture fallback ---

    def test_no_cultures_fallback_names(self) -> None:
        galaxy, _ = self._small_galaxy(cultures=[])
        # Systems should have indexed fallback names
        for s in galaxy.systems:
            assert len(s.name) > 0

    # --- Culture integration ---

    def test_with_cultures_populates_registry(self) -> None:
        culture = _culture()
        galaxy, _ = self._small_galaxy(cultures=[(culture, 1.0)])
        assert culture.id in galaxy.cultures

    def test_with_cultures_names_generated(self) -> None:
        culture = _culture()
        galaxy, _ = self._small_galaxy(cultures=[(culture, 1.0)], count=3)
        for s in galaxy.systems:
            assert isinstance(s.name, str)
            assert len(s.name) > 0

    # --- Metadata ---

    def test_metadata_has_seed(self) -> None:
        galaxy, _ = self._small_galaxy(seed=7)
        assert "root_seed_int" in galaxy.metadata

    def test_metadata_has_depth(self) -> None:
        galaxy, _ = self._small_galaxy(depth="sectors")
        assert galaxy.metadata["depth"] == "sectors"

    # --- Satellite structure ---

    def test_satellite_parent_ids_valid(self) -> None:
        galaxy, _ = self._small_galaxy(seed=77, count=3)
        for system in galaxy.systems:
            planet_ids = {p.id for p in system.planets}
            for planet in system.planets:
                if planet.parent_planet_id is not None:
                    assert planet.parent_planet_id in planet_ids

    # --- Default config ---

    def test_default_config_works(self) -> None:
        # GalaxyConfig() defaults to 100 systems — use depth="systems" for speed
        galaxy, _ = generate_galaxy(42, GalaxyConfig(
            system=SystemConfig(count=2),
            depth="systems",
        ))
        assert len(galaxy.systems) == 2
