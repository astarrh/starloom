"""Tests for starloom.domain.types."""

import pytest

from starloom.domain.types import (
    ClimateType,
    LocationType,
    NameStyle,
    NodeType,
    PlanetClass,
    ReproMode,
    Severity,
    Size,
    TopographyType,
    ValidationStage,
)


class TestSize:
    def test_numeric_values(self) -> None:
        assert Size.TINY == 1
        assert Size.SMALL == 2
        assert Size.MEDIUM == 3
        assert Size.LARGE == 4
        assert Size.ENORMOUS == 5

    def test_ordering(self) -> None:
        assert Size.TINY < Size.SMALL < Size.MEDIUM < Size.LARGE < Size.ENORMOUS

    def test_int_subclass(self) -> None:
        assert isinstance(Size.MEDIUM, int)

    def test_all_members(self) -> None:
        assert len(Size) == 5


class TestPlanetClass:
    def test_members(self) -> None:
        expected = {"TELLURIC", "GASEOUS", "ICE", "LAVA", "LIQUID", "ASTEROID"}
        assert {m.value for m in PlanetClass} == expected

    def test_str_subclass(self) -> None:
        assert isinstance(PlanetClass.TELLURIC, str)


class TestTopographyType:
    def test_seven_members(self) -> None:
        assert len(TopographyType) == 7

    def test_members(self) -> None:
        expected = {"CANYON", "BASIN", "KARST", "PLAINS", "HILLS", "CLIFFS", "PEAKS"}
        assert {m.value for m in TopographyType} == expected


class TestClimateType:
    def test_seven_members(self) -> None:
        assert len(ClimateType) == 7

    def test_members(self) -> None:
        expected = {"VOLCANIC", "ARID", "STEPPE", "TEMPERATE", "HUMID", "RAINY", "FROZEN"}
        assert {m.value for m in ClimateType} == expected


class TestLocationAndNodeTypes:
    def test_location_types(self) -> None:
        assert {m.value for m in LocationType} == {"TRIBAL", "TRADING", "CITY", "METROPOLIS"}

    def test_node_type_generic(self) -> None:
        assert NodeType.GENERIC.value == "GENERIC"


class TestNameStyle:
    def test_members(self) -> None:
        assert {m.value for m in NameStyle} == {"GENERIC", "PERSON", "RESIDENCE", "BAR"}


class TestReproMode:
    def test_values(self) -> None:
        assert ReproMode.COMPATIBLE.value == "compatible"
        assert ReproMode.STRICT.value == "strict"


class TestSeverityAndStage:
    def test_severity(self) -> None:
        assert Severity.ERROR.value == "ERROR"
        assert Severity.WARNING.value == "WARNING"

    def test_stage(self) -> None:
        values = {m.value for m in ValidationStage}
        assert "config" in values
        assert "content_pack" in values
        assert "constraints" in values
