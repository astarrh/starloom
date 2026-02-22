"""Tests for post-generation constraint validation (Phase 04)."""

from __future__ import annotations

import pytest

from starloom.config import GalaxyConfig
from starloom.domain.models import (
    Galaxy,
    Location,
    Node,
    Planet,
    Sector,
    SolarSystem,
    ValidationIssue,
)
from starloom.domain.types import (
    ClimateType,
    LocationType,
    NodeType,
    PlanetClass,
    Severity,
    Size,
    TopographyType,
    ValidationStage,
)


# ---------------------------------------------------------------------------
# Helpers to build minimal domain objects
# ---------------------------------------------------------------------------


def _node(idx: int = 0, loc_id: str = "loc-0") -> Node:
    return Node(
        id=f"{loc_id}-node-{idx}",
        name=f"Node {idx}",
        node_type=NodeType.GENERIC,
        in_town=True,
        distinctiveness=0.5,
    )


def _location(idx: int = 0, sector_id: str = "sec-0") -> Location:
    loc_id = f"{sector_id}-loc-{idx}"
    return Location(
        id=loc_id,
        name=f"Location {idx}",
        location_type=LocationType.TRADING,
        size=Size.MEDIUM,
        features=(),
        distinctiveness=0.5,
        nodes=(_node(0, loc_id),),
    )


def _sector(idx: int = 0, planet_id: str = "pl-0", density: int = 5) -> Sector:
    sec_id = f"{planet_id}-sec-{idx}"
    return Sector(
        id=sec_id,
        name=f"Sector {idx}",
        topography=TopographyType.PLAINS,
        climate=ClimateType.TEMPERATE,
        density=density,
        urbanization=0.5,
        hostility=0.2,
        remoteness=0.3,
        locations=(_location(0, sec_id),),
    )


def _planet(
    idx: int = 0,
    system_id: str = "sys-0000",
    x: float = 0.0,
    y: float = 0.0,
    parent_planet_id: str | None = None,
) -> Planet:
    return Planet(
        id=f"{system_id}-pl-{idx:03d}",
        name=f"Planet {idx}",
        size=Size.MEDIUM,
        classification=PlanetClass.TELLURIC,
        x=x,
        y=y,
        z=0.0,
        parent_planet_id=parent_planet_id,
        distinctiveness=0.5,
        sectors=(_sector(0, f"{system_id}-pl-{idx:03d}"),),
    )


def _system(
    idx: int = 0,
    x: float = 0.0,
    y: float = 0.0,
    planets: tuple[Planet, ...] = (),
    culture_ids: tuple[tuple[str, float], ...] = (),
) -> SolarSystem:
    return SolarSystem(
        id=f"sys-{idx:04d}",
        name=f"System {idx}",
        size=Size.MEDIUM,
        x=x,
        y=y,
        z=0.0,
        culture_ids=culture_ids,
        planets=planets,
    )


def _galaxy(systems: tuple[SolarSystem, ...], cultures: dict | None = None) -> Galaxy:
    return Galaxy(
        seed=42,
        config_version="0.1",
        content_pack_version="none",
        cultures=cultures or {},
        systems=systems,
        metadata={},
    )


def _config(strict: bool = False) -> GalaxyConfig:
    return GalaxyConfig(strict=strict)


# ---------------------------------------------------------------------------
# Happy-path: clean galaxy produces no issues
# ---------------------------------------------------------------------------


class TestCleanGalaxy:
    def test_clean_galaxy_has_no_issues(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        s0 = _system(0, x=0.0, y=0.0, planets=(_planet(0, "sys-0000", 1.0, 1.0),))
        s1 = _system(1, x=100.0, y=200.0, planets=(_planet(0, "sys-0001", 2.0, 2.0),))
        galaxy = _galaxy((s0, s1))
        report = validate_galaxy(galaxy, _config())
        assert report.ok
        assert len(report.issues) == 0

    def test_report_is_ok_when_no_errors(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        galaxy = _galaxy((_system(0, x=0.0, y=0.0),))
        report = validate_galaxy(galaxy, _config())
        assert report.ok


# ---------------------------------------------------------------------------
# DUPLICATE_SYSTEM_COORD
# ---------------------------------------------------------------------------


class TestDuplicateSystemCoord:
    def test_duplicate_system_coord_detected(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        s0 = _system(0, x=10.0, y=20.0)
        s1 = _system(1, x=10.0, y=20.0)  # same (x, y) → duplicate
        galaxy = _galaxy((s0, s1))
        report = validate_galaxy(galaxy, _config())
        assert not report.ok
        codes = [i.code for i in report.errors()]
        assert "DUPLICATE_SYSTEM_COORD" in codes

    def test_near_identical_coords_within_precision_detected(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        # Both round to (10.0, 20.0) at 1 decimal place
        s0 = _system(0, x=10.01, y=20.01)
        s1 = _system(1, x=10.04, y=20.04)
        galaxy = _galaxy((s0, s1))
        report = validate_galaxy(galaxy, _config())
        assert not report.ok

    def test_distinct_coords_no_error(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        s0 = _system(0, x=10.0, y=20.0)
        s1 = _system(1, x=10.2, y=20.0)  # x differs at precision=1
        galaxy = _galaxy((s0, s1))
        report = validate_galaxy(galaxy, _config())
        assert report.ok


# ---------------------------------------------------------------------------
# DUPLICATE_PLANET_COORD
# ---------------------------------------------------------------------------


class TestDuplicatePlanetCoord:
    def test_duplicate_planet_coord_in_same_system(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        p0 = _planet(0, "sys-0000", x=5.0, y=5.0)
        p1 = _planet(1, "sys-0000", x=5.0, y=5.0)  # same (x, y) → duplicate
        s = _system(0, x=0.0, y=0.0, planets=(p0, p1))
        galaxy = _galaxy((s,))
        report = validate_galaxy(galaxy, _config())
        assert not report.ok
        codes = [i.code for i in report.errors()]
        assert "DUPLICATE_PLANET_COORD" in codes

    def test_same_coords_different_systems_no_error(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        # Same planet coords, but in different systems → OK
        p0 = _planet(0, "sys-0000", x=5.0, y=5.0)
        p1 = _planet(0, "sys-0001", x=5.0, y=5.0)
        s0 = _system(0, x=0.0, y=0.0, planets=(p0,))
        s1 = _system(1, x=100.0, y=100.0, planets=(p1,))
        galaxy = _galaxy((s0, s1))
        report = validate_galaxy(galaxy, _config())
        assert report.ok


# ---------------------------------------------------------------------------
# INVALID_PARENT_ID
# ---------------------------------------------------------------------------


class TestInvalidParentId:
    def test_invalid_parent_id_detected(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        p_primary = _planet(0, "sys-0000", x=1.0, y=1.0)
        # satellite references a non-existent parent id
        p_sat = _planet(1, "sys-0000", x=2.0, y=2.0, parent_planet_id="sys-0000-pl-999")
        s = _system(0, x=0.0, y=0.0, planets=(p_primary, p_sat))
        galaxy = _galaxy((s,))
        report = validate_galaxy(galaxy, _config())
        assert not report.ok
        codes = [i.code for i in report.errors()]
        assert "INVALID_PARENT_ID" in codes

    def test_valid_parent_id_no_error(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        p_primary = _planet(0, "sys-0000", x=1.0, y=1.0)
        p_sat = _planet(1, "sys-0000", x=2.0, y=2.0, parent_planet_id=p_primary.id)
        s = _system(0, x=0.0, y=0.0, planets=(p_primary, p_sat))
        galaxy = _galaxy((s,))
        report = validate_galaxy(galaxy, _config())
        assert report.ok

    def test_primary_planets_no_parent_no_error(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        p = _planet(0, "sys-0000", x=1.0, y=1.0)
        assert p.parent_planet_id is None
        s = _system(0, x=0.0, y=0.0, planets=(p,))
        galaxy = _galaxy((s,))
        report = validate_galaxy(galaxy, _config())
        assert report.ok


# ---------------------------------------------------------------------------
# DUPLICATE_ENTITY_ID
# ---------------------------------------------------------------------------


class TestDuplicateEntityId:
    def test_duplicate_system_id_detected(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        # Force same id for two systems
        s0 = _system(0, x=0.0, y=0.0)
        s1 = SolarSystem(
            id=s0.id,  # same id!
            name="Duplicate",
            size=Size.SMALL,
            x=100.0, y=200.0, z=0.0,
            culture_ids=(),
            planets=(),
        )
        galaxy = _galaxy((s0, s1))
        report = validate_galaxy(galaxy, _config())
        assert not report.ok
        codes = [i.code for i in report.errors()]
        assert "DUPLICATE_ENTITY_ID" in codes


# ---------------------------------------------------------------------------
# UNKNOWN_CULTURE_ID
# ---------------------------------------------------------------------------


class TestUnknownCultureId:
    def test_unknown_culture_id_is_warning(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        s = _system(0, x=0.0, y=0.0, culture_ids=(("ghost-culture", 1.0),))
        galaxy = _galaxy((s,), cultures={})  # galaxy.cultures is empty
        report = validate_galaxy(galaxy, _config())
        # Warning, not error — so report.ok is True in non-strict mode
        assert report.ok
        warn_codes = [i.code for i in report.warnings()]
        assert "UNKNOWN_CULTURE_ID" in warn_codes

    def test_known_culture_id_no_warning(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        from starloom.domain.models import CultureSpec
        spec = CultureSpec(id="c-001", name="Culture A")
        s = _system(0, x=0.0, y=0.0, culture_ids=(("c-001", 1.0),))
        galaxy = _galaxy((s,), cultures={"c-001": spec})
        report = validate_galaxy(galaxy, _config())
        assert report.ok
        assert not any(i.code == "UNKNOWN_CULTURE_ID" for i in report.issues)


# ---------------------------------------------------------------------------
# Strict mode
# ---------------------------------------------------------------------------


class TestStrictMode:
    def test_strict_promotes_warning_to_error(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        # UNKNOWN_CULTURE_ID is normally a WARNING; in strict mode → ERROR
        s = _system(0, x=0.0, y=0.0, culture_ids=(("ghost", 1.0),))
        galaxy = _galaxy((s,))
        report = validate_galaxy(galaxy, _config(strict=True))
        assert not report.ok  # promoted to error
        err_codes = [i.code for i in report.errors()]
        assert "UNKNOWN_CULTURE_ID" in err_codes

    def test_strict_no_issues_still_ok(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        galaxy = _galaxy((_system(0, x=0.0, y=0.0),))
        report = validate_galaxy(galaxy, _config(strict=True))
        assert report.ok

    def test_strict_preserves_original_errors(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        # A structural ERROR stays ERROR in strict mode too
        s0 = _system(0, x=10.0, y=10.0)
        s1 = _system(1, x=10.0, y=10.0)
        galaxy = _galaxy((s0, s1))
        report = validate_galaxy(galaxy, _config(strict=True))
        assert not report.ok
        assert any(i.severity == Severity.ERROR for i in report.issues)


# ---------------------------------------------------------------------------
# DENSITY_EXCEEDS_MAX (pack-aware)
# ---------------------------------------------------------------------------


class TestDensityExceedsMax:
    def test_density_over_cap_with_pack_is_warning(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        from starloom.content.loader import default_content_pack
        pack = default_content_pack()

        # Find a topo/climate entry with low max_density
        entry = next(
            e for e in pack.sector_types.values() if e.max_density <= 5
        )

        # Build a sector with density > max_density
        sec_id = "sys-0000-pl-000-sec-0"
        bad_sector = Sector(
            id=sec_id,
            name="BadSector",
            topography=entry.topography,
            climate=entry.climate,
            density=entry.max_density + 2,  # intentionally over cap
            urbanization=0.9,
            hostility=entry.hostility,
            remoteness=entry.remoteness,
            locations=(),
        )
        planet = Planet(
            id="sys-0000-pl-000",
            name="P0",
            size=Size.MEDIUM,
            classification=PlanetClass.TELLURIC,
            x=1.0, y=1.0, z=0.0,
            parent_planet_id=None,
            distinctiveness=0.5,
            sectors=(bad_sector,),
        )
        system = _system(0, x=0.0, y=0.0, planets=(planet,))
        galaxy = _galaxy((system,))
        report = validate_galaxy(galaxy, _config(), content_pack=pack)
        warn_codes = [i.code for i in report.warnings()]
        assert "DENSITY_EXCEEDS_MAX" in warn_codes

    def test_density_at_cap_no_warning(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        from starloom.content.loader import default_content_pack
        pack = default_content_pack()
        entry = next(iter(pack.sector_types.values()))
        sec_id = "sys-0000-pl-000-sec-0"
        ok_sector = Sector(
            id=sec_id,
            name="OkSector",
            topography=entry.topography,
            climate=entry.climate,
            density=entry.max_density,  # exactly at cap → no warning
            urbanization=0.5,
            hostility=entry.hostility,
            remoteness=entry.remoteness,
            locations=(),
        )
        planet = Planet(
            id="sys-0000-pl-000",
            name="P0",
            size=Size.MEDIUM,
            classification=PlanetClass.TELLURIC,
            x=1.0, y=1.0, z=0.0,
            parent_planet_id=None,
            distinctiveness=0.5,
            sectors=(ok_sector,),
        )
        system = _system(0, x=0.0, y=0.0, planets=(planet,))
        galaxy = _galaxy((system,))
        report = validate_galaxy(galaxy, _config(), content_pack=pack)
        assert not any(i.code == "DENSITY_EXCEEDS_MAX" for i in report.issues)

    def test_no_pack_no_density_warning(self) -> None:
        from starloom.constraints.rules import validate_galaxy
        # Without a pack, density cap checks are skipped entirely
        sec_id = "sys-0000-pl-000-sec-0"
        sector = Sector(
            id=sec_id,
            name="HighDensity",
            topography=TopographyType.PLAINS,
            climate=ClimateType.TEMPERATE,
            density=10,
            urbanization=1.0,
            hostility=0.1,
            remoteness=0.1,
            locations=(),
        )
        planet = Planet(
            id="sys-0000-pl-000",
            name="P0",
            size=Size.MEDIUM,
            classification=PlanetClass.TELLURIC,
            x=1.0, y=1.0, z=0.0,
            parent_planet_id=None,
            distinctiveness=0.5,
            sectors=(sector,),
        )
        system = _system(0, x=0.0, y=0.0, planets=(planet,))
        galaxy = _galaxy((system,))
        report = validate_galaxy(galaxy, _config(), content_pack=None)
        assert not any(i.code == "DENSITY_EXCEEDS_MAX" for i in report.issues)


# ---------------------------------------------------------------------------
# Integration: generate_galaxy produces a ValidationReport
# ---------------------------------------------------------------------------


class TestGenerateGalaxyReport:
    def test_generate_galaxy_returns_report(self) -> None:
        from starloom.config import GalaxyConfig, SystemConfig
        from starloom.generation.galaxy import generate_galaxy
        config = GalaxyConfig(system=SystemConfig(count=3), depth="systems")
        _, report = generate_galaxy(42, config=config)
        assert report is not None
        assert isinstance(report.ok, bool)

    def test_generate_galaxy_with_pack_returns_report(self) -> None:
        from starloom.config import GalaxyConfig, SystemConfig
        from starloom.content.loader import default_content_pack
        from starloom.generation.galaxy import generate_galaxy
        pack = default_content_pack()
        config = GalaxyConfig(system=SystemConfig(count=2), depth="planets")
        _, report = generate_galaxy(99, config=config, content_pack=pack)
        assert report is not None

    def test_full_pipeline_report_ok(self) -> None:
        from starloom.config import GalaxyConfig, SystemConfig
        from starloom.generation.galaxy import generate_galaxy
        config = GalaxyConfig(system=SystemConfig(count=2), depth="nodes")
        _, report = generate_galaxy("test-seed", config=config)
        assert report.ok

    def test_generate_galaxy_systems_depth(self) -> None:
        from starloom.config import GalaxyConfig, SystemConfig
        from starloom.generation.galaxy import generate_galaxy
        config = GalaxyConfig(system=SystemConfig(count=5), depth="systems")
        galaxy, report = generate_galaxy(1, config=config)
        assert len(galaxy.systems) > 0
