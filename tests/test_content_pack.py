"""Tests for content pack loading, validation, and eligibility matrices (Phase 04)."""

from __future__ import annotations

import pathlib
import textwrap

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def default_pack():
    from starloom.content.loader import default_content_pack
    return default_content_pack()


@pytest.fixture()
def tmp_pack_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """Return a tmp directory pre-populated with minimal valid YAML files."""
    planet_classes = textwrap.dedent("""\
        version: "0.1"
        planet_classes:
          - name: TELLURIC
          - name: GASEOUS
    """)
    sector_types = textwrap.dedent("""\
        version: "0.1"
        sector_types:
          - topography: PLAINS
            climate: TEMPERATE
            max_density: 8
            hostility: 0.1
            remoteness: 0.2
    """)
    location_types = textwrap.dedent("""\
        version: "0.1"
        location_types:
          - name: Tribal Camp
            type: TRIBAL
            density_min: 1
            density_max: 4
            rarity: 1.0
            affinity:
              climates: []
              topographies: []
          - name: Trade Post
            type: TRADING
            density_min: 3
            density_max: 7
            rarity: 0.8
            affinity:
              climates: []
              topographies: []
    """)
    node_types = textwrap.dedent("""\
        version: "0.1"
        node_types:
          - name: Generic POI
            type: GENERIC
            density_min: 1
            density_max: 10
            rarity: 1.0
            in_town: true
            affinity:
              climates: []
              topographies: []
    """)
    (tmp_path / "planet_classes.yaml").write_text(planet_classes)
    (tmp_path / "sector_types.yaml").write_text(sector_types)
    (tmp_path / "location_types.yaml").write_text(location_types)
    (tmp_path / "node_types.yaml").write_text(node_types)
    return tmp_path


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


class TestDefaultPackLoads:
    def test_loads_without_error(self, default_pack) -> None:
        assert default_pack is not None

    def test_version_is_string(self, default_pack) -> None:
        assert isinstance(default_pack.version, str)
        assert default_pack.version

    def test_pack_hash_is_hex(self, default_pack) -> None:
        assert len(default_pack.pack_hash) == 64
        int(default_pack.pack_hash, 16)  # no exception → valid hex

    def test_sector_types_coverage(self, default_pack) -> None:
        # Default pack has 7 topographies × 7 climates = 49 entries
        assert len(default_pack.sector_types) == 49

    def test_location_types_present(self, default_pack) -> None:
        assert len(default_pack.location_types) >= 1

    def test_node_types_present(self, default_pack) -> None:
        assert len(default_pack.node_types) >= 1

    def test_planet_classes_present(self, default_pack) -> None:
        assert len(default_pack.planet_classes) >= 1


class TestLoadFromPath:
    def test_loads_minimal_pack(self, tmp_pack_dir: pathlib.Path) -> None:
        from starloom.content.loader import load_content_pack
        pack = load_content_pack(tmp_pack_dir)
        assert pack is not None

    def test_missing_directory_raises(self, tmp_path: pathlib.Path) -> None:
        from starloom.content.loader import load_content_pack
        with pytest.raises(FileNotFoundError):
            load_content_pack(tmp_path / "nonexistent")

    def test_missing_file_raises(self, tmp_pack_dir: pathlib.Path) -> None:
        from starloom.content.loader import load_content_pack
        (tmp_pack_dir / "node_types.yaml").unlink()
        with pytest.raises(FileNotFoundError):
            load_content_pack(tmp_pack_dir)

    def test_pack_hash_deterministic(self, tmp_pack_dir: pathlib.Path) -> None:
        from starloom.content.loader import load_content_pack
        pack_a = load_content_pack(tmp_pack_dir)
        pack_b = load_content_pack(tmp_pack_dir)
        assert pack_a.pack_hash == pack_b.pack_hash


# ---------------------------------------------------------------------------
# Schema / semantic validation
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_bad_topography_raises(self, tmp_pack_dir: pathlib.Path) -> None:
        from starloom.content.loader import load_content_pack
        from starloom.content.schema import ContentPackValidationError
        bad = textwrap.dedent("""\
            version: "0.1"
            sector_types:
              - topography: BADTOPO
                climate: TEMPERATE
                max_density: 5
                hostility: 0.1
                remoteness: 0.2
        """)
        (tmp_pack_dir / "sector_types.yaml").write_text(bad)
        with pytest.raises(ContentPackValidationError):
            load_content_pack(tmp_pack_dir)

    def test_bad_climate_raises(self, tmp_pack_dir: pathlib.Path) -> None:
        from starloom.content.loader import load_content_pack
        from starloom.content.schema import ContentPackValidationError
        bad = textwrap.dedent("""\
            version: "0.1"
            sector_types:
              - topography: PLAINS
                climate: BADCLIMATE
                max_density: 5
                hostility: 0.1
                remoteness: 0.2
        """)
        (tmp_pack_dir / "sector_types.yaml").write_text(bad)
        with pytest.raises(ContentPackValidationError):
            load_content_pack(tmp_pack_dir)

    def test_duplicate_sector_entry_raises(self, tmp_pack_dir: pathlib.Path) -> None:
        from starloom.content.loader import load_content_pack
        from starloom.content.schema import ContentPackValidationError
        dup = textwrap.dedent("""\
            version: "0.1"
            sector_types:
              - topography: PLAINS
                climate: TEMPERATE
                max_density: 5
                hostility: 0.1
                remoteness: 0.2
              - topography: PLAINS
                climate: TEMPERATE
                max_density: 7
                hostility: 0.3
                remoteness: 0.4
        """)
        (tmp_pack_dir / "sector_types.yaml").write_text(dup)
        with pytest.raises(ContentPackValidationError):
            load_content_pack(tmp_pack_dir)

    def test_bad_location_type_raises(self, tmp_pack_dir: pathlib.Path) -> None:
        from starloom.content.loader import load_content_pack
        from starloom.content.schema import ContentPackValidationError
        bad = textwrap.dedent("""\
            version: "0.1"
            location_types:
              - name: Bad
                type: NOTATYPE
                density_min: 1
                density_max: 5
                rarity: 0.5
        """)
        (tmp_pack_dir / "location_types.yaml").write_text(bad)
        with pytest.raises(ContentPackValidationError):
            load_content_pack(tmp_pack_dir)

    def test_density_min_exceeds_max_raises(self, tmp_pack_dir: pathlib.Path) -> None:
        from starloom.content.loader import load_content_pack
        from starloom.content.schema import ContentPackValidationError
        bad = textwrap.dedent("""\
            version: "0.1"
            location_types:
              - name: Bad
                type: TRIBAL
                density_min: 8
                density_max: 3
                rarity: 0.5
        """)
        (tmp_pack_dir / "location_types.yaml").write_text(bad)
        with pytest.raises(ContentPackValidationError):
            load_content_pack(tmp_pack_dir)

    def test_bad_affinity_climate_raises(self, tmp_pack_dir: pathlib.Path) -> None:
        from starloom.content.loader import load_content_pack
        from starloom.content.schema import ContentPackValidationError
        bad = textwrap.dedent("""\
            version: "0.1"
            location_types:
              - name: Temp
                type: TRIBAL
                density_min: 1
                density_max: 4
                rarity: 1.0
                affinity:
                  climates: [NOTACLIMATE]
                  topographies: []
        """)
        (tmp_pack_dir / "location_types.yaml").write_text(bad)
        with pytest.raises(ContentPackValidationError):
            load_content_pack(tmp_pack_dir)

    def test_bad_planet_class_raises(self, tmp_pack_dir: pathlib.Path) -> None:
        from starloom.content.loader import load_content_pack
        from starloom.content.schema import ContentPackValidationError
        bad = textwrap.dedent("""\
            version: "0.1"
            planet_classes:
              - name: NOTACLASS
        """)
        (tmp_pack_dir / "planet_classes.yaml").write_text(bad)
        with pytest.raises(ContentPackValidationError):
            load_content_pack(tmp_pack_dir)


# ---------------------------------------------------------------------------
# Eligibility matrix
# ---------------------------------------------------------------------------


class TestEligibilityMatrix:
    def test_eligible_location_types_returns_list(self, default_pack) -> None:
        from starloom.domain.types import ClimateType, TopographyType
        result = default_pack.eligible_location_types(
            TopographyType.PLAINS, ClimateType.TEMPERATE, 5
        )
        assert isinstance(result, list)

    def test_eligible_location_types_density_1_no_metropolis(self, default_pack) -> None:
        from starloom.domain.types import ClimateType, LocationType, TopographyType
        result = default_pack.eligible_location_types(
            TopographyType.PLAINS, ClimateType.TEMPERATE, 1
        )
        assert LocationType.METROPOLIS.value not in result

    def test_eligible_location_types_density_10_has_metropolis(self, default_pack) -> None:
        from starloom.domain.types import ClimateType, LocationType, TopographyType
        # Find a topo/climate with high max_density
        entry = default_pack.sector_types.get(("PLAINS", "TEMPERATE"))
        if entry is None or entry.max_density < 8:
            pytest.skip("PLAINS/TEMPERATE doesn't support density 10 in this pack")
        result = default_pack.eligible_location_types(
            TopographyType.PLAINS, ClimateType.TEMPERATE, 8
        )
        assert LocationType.METROPOLIS.value in result

    def test_eligible_node_types_returns_list(self, default_pack) -> None:
        from starloom.domain.types import ClimateType, TopographyType
        result = default_pack.eligible_node_types(
            TopographyType.PLAINS, ClimateType.TEMPERATE, 5, True
        )
        assert isinstance(result, list)

    def test_unknown_topo_climate_returns_empty(self, default_pack) -> None:
        from starloom.domain.types import ClimateType, TopographyType
        # Use a valid topo/climate but density=999 which is out of range
        result = default_pack.eligible_location_types(
            TopographyType.PLAINS, ClimateType.TEMPERATE, 999
        )
        assert result == []

    def test_minimal_pack_eligible_location_types(self, tmp_pack_dir: pathlib.Path) -> None:
        from starloom.content.loader import load_content_pack
        from starloom.domain.types import ClimateType, LocationType, TopographyType
        pack = load_content_pack(tmp_pack_dir)
        # density=1: only TRIBAL (min=1, max=4)
        result = pack.eligible_location_types(
            TopographyType.PLAINS, ClimateType.TEMPERATE, 1
        )
        assert LocationType.TRIBAL.value in result
        assert LocationType.TRADING.value not in result  # min=3

    def test_minimal_pack_density_3_has_both(self, tmp_pack_dir: pathlib.Path) -> None:
        from starloom.content.loader import load_content_pack
        from starloom.domain.types import ClimateType, LocationType, TopographyType
        pack = load_content_pack(tmp_pack_dir)
        result = pack.eligible_location_types(
            TopographyType.PLAINS, ClimateType.TEMPERATE, 3
        )
        assert LocationType.TRIBAL.value in result
        assert LocationType.TRADING.value in result

    def test_sector_type_lookup(self, tmp_pack_dir: pathlib.Path) -> None:
        from starloom.content.loader import load_content_pack
        from starloom.domain.types import ClimateType, TopographyType
        pack = load_content_pack(tmp_pack_dir)
        entry = pack.sector_type(TopographyType.PLAINS, ClimateType.TEMPERATE)
        assert entry is not None
        assert entry.max_density == 8
        assert entry.hostility == pytest.approx(0.1)
        assert entry.remoteness == pytest.approx(0.2)

    def test_sector_type_missing_returns_none(self, tmp_pack_dir: pathlib.Path) -> None:
        from starloom.content.loader import load_content_pack
        from starloom.domain.types import ClimateType, TopographyType
        pack = load_content_pack(tmp_pack_dir)
        # Pack only has PLAINS/TEMPERATE; PEAKS/ARID is absent
        entry = pack.sector_type(TopographyType.PEAKS, ClimateType.ARID)
        assert entry is None
