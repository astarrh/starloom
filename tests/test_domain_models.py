"""Tests for starloom.domain.models."""

import pytest

from starloom.domain.models import (
    Culture,
    CultureFamily,
    CultureSpec,
    Galaxy,
    Location,
    Node,
    Planet,
    Sector,
    SolarSystem,
    StyleConfig,
    ValidationIssue,
    ValidationReport,
)
from starloom.domain.types import (
    ClimateType,
    LocationType,
    NameStyle,
    NodeType,
    PlanetClass,
    Severity,
    Size,
    TopographyType,
    ValidationStage,
)


class TestImmutability:
    def test_node_is_frozen(self) -> None:
        node = Node(
            id="nd-1", name="Tavern", node_type=NodeType.GENERIC,
            in_town=True, distinctiveness=0.5
        )
        with pytest.raises((AttributeError, TypeError)):
            node.name = "changed"  # type: ignore[misc]

    def test_galaxy_is_frozen(self) -> None:
        galaxy = Galaxy(seed=42, config_version="0.1", content_pack_version="0.1")
        with pytest.raises((AttributeError, TypeError)):
            galaxy.seed = 99  # type: ignore[misc]


class TestValidationReport:
    def _issue(self, severity: Severity) -> ValidationIssue:
        return ValidationIssue(
            code="TEST_CODE",
            severity=severity,
            stage=ValidationStage.CONSTRAINTS,
            message="test",
        )

    def test_ok_when_no_errors(self) -> None:
        report = ValidationReport(issues=(self._issue(Severity.WARNING),))
        assert report.ok is True

    def test_not_ok_when_error(self) -> None:
        report = ValidationReport(issues=(self._issue(Severity.ERROR),))
        assert report.ok is False

    def test_empty_report_is_ok(self) -> None:
        report = ValidationReport()
        assert report.ok is True

    def test_errors_and_warnings_filtered(self) -> None:
        err = self._issue(Severity.ERROR)
        warn = self._issue(Severity.WARNING)
        report = ValidationReport(issues=(err, warn))
        assert report.errors() == (err,)
        assert report.warnings() == (warn,)


class TestCultureSpec:
    def test_to_runtime_round_trips(self) -> None:
        spec = CultureSpec(
            id="c-001",
            name="Terran",
            markov_model_data={"bigrams": {"ab": 2}},
            name_styles={NameStyle.GENERIC: StyleConfig(min_length=4, max_length=10)},
        )
        runtime = spec.to_runtime()
        assert isinstance(runtime, Culture)
        assert runtime.id == spec.id
        assert runtime.name == spec.name
        assert runtime.markov_model == spec.markov_model_data


class TestHierarchyInstantiation:
    """Smoke test: build a minimal hierarchy without errors."""

    def test_build_minimal_galaxy(self) -> None:
        node = Node(id="nd-1", name="Inn", node_type=NodeType.GENERIC,
                    in_town=True, distinctiveness=0.3)
        location = Location(
            id="loc-1", name="Riverside", location_type=LocationType.TRADING,
            size=Size.SMALL, features=("river",), distinctiveness=0.4, nodes=(node,)
        )
        sector = Sector(
            id="sec-1", name="Northern Basin", topography=TopographyType.BASIN,
            climate=ClimateType.TEMPERATE, density=5,
            urbanization=0.5, hostility=0.2, remoteness=0.3,
            locations=(location,)
        )
        planet = Planet(
            id="pl-1", name="Verdania", size=Size.MEDIUM,
            classification=PlanetClass.TELLURIC,
            x=10.0, y=-5.0, z=0.5, parent_planet_id=None,
            distinctiveness=0.6, sectors=(sector,)
        )
        system = SolarSystem(
            id="sys-0001", name="Aethon", size=Size.LARGE,
            x=100.0, y=200.0, z=2.0,
            culture_ids=(("c-001", 1.0),),
            planets=(planet,)
        )
        galaxy = Galaxy(
            seed="test-seed",
            config_version="0.1",
            content_pack_version="0.1",
            systems=(system,),
        )
        assert galaxy.systems[0].planets[0].sectors[0].locations[0].nodes[0].name == "Inn"
