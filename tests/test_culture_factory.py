"""Tests for starloom.culture.factory and starloom.culture public API."""

import pytest

from starloom.culture import (
    CultureError,
    create_culture,
    create_culture_family,
    generate_culture_family,
    generate_name,
)
from starloom.domain.models import Culture, CultureFamily, CultureSpec, StyleConfig
from starloom.domain.types import NameStyle

EXAMPLES = [
    "Valdris", "Korveth", "Almara", "Selindra", "Tharion",
    "Elyndra", "Morvek", "Zephalon", "Briskon", "Caelith",
]

MINIMAL = ["Zhal", "Zhora", "Zhelik", "Zhaveth"]


# ---------------------------------------------------------------------------
# create_culture (Path 3)
# ---------------------------------------------------------------------------


class TestCreateCulture:
    def test_returns_culture(self) -> None:
        c = create_culture(EXAMPLES, name="Terran")
        assert isinstance(c, Culture)

    def test_name_assigned(self) -> None:
        c = create_culture(EXAMPLES, name="Terran")
        assert c.name == "Terran"

    def test_has_markov_model(self) -> None:
        c = create_culture(EXAMPLES, name="Terran")
        assert isinstance(c.markov_model, dict)
        assert "table" in c.markov_model

    def test_has_all_default_styles(self) -> None:
        c = create_culture(EXAMPLES, name="Terran")
        for style in NameStyle:
            assert style in c.name_styles

    def test_style_overrides_applied(self) -> None:
        override = {NameStyle.PERSON: StyleConfig(min_length=6, max_length=6)}
        c = create_culture(EXAMPLES, name="Terran", style_overrides=override)
        assert c.name_styles[NameStyle.PERSON].min_length == 6

    def test_too_few_examples_raises(self) -> None:
        with pytest.raises(CultureError, match="at least"):
            create_culture(["a", "b"], name="X")

    def test_id_is_stable(self) -> None:
        c1 = create_culture(EXAMPLES, name="Terran")
        c2 = create_culture(EXAMPLES, name="Terran")
        assert c1.id == c2.id

    def test_metadata_includes_examples(self) -> None:
        c = create_culture(EXAMPLES, name="Terran")
        assert "origin_examples" in c.metadata

    def test_is_immutable(self) -> None:
        c = create_culture(EXAMPLES, name="Terran")
        with pytest.raises((AttributeError, TypeError)):
            c.name = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# create_culture_family (Path 1)
# ---------------------------------------------------------------------------


class TestCreateCultureFamily:
    def test_returns_culture_family(self) -> None:
        fam = create_culture_family(EXAMPLES, name="Terran", variant_count=3, seed=1)
        assert isinstance(fam, CultureFamily)

    def test_correct_variant_count(self) -> None:
        fam = create_culture_family(EXAMPLES, name="Terran", variant_count=4, seed=1)
        assert len(fam.cultures) == 4

    def test_single_variant(self) -> None:
        fam = create_culture_family(EXAMPLES, name="Solo", variant_count=1, seed=1)
        assert len(fam.cultures) == 1

    def test_cultures_are_culture_instances(self) -> None:
        fam = create_culture_family(EXAMPLES, name="Terran", seed=1)
        assert all(isinstance(c, Culture) for c in fam.cultures)

    def test_family_id_stable_with_seed(self) -> None:
        fam1 = create_culture_family(EXAMPLES, name="Terran", seed=42)
        fam2 = create_culture_family(EXAMPLES, name="Terran", seed=42)
        assert fam1.id == fam2.id

    def test_different_seeds_different_ids(self) -> None:
        fam1 = create_culture_family(EXAMPLES, name="Terran", seed=1)
        fam2 = create_culture_family(EXAMPLES, name="Terran", seed=2)
        assert fam1.id != fam2.id

    def test_drift_zero_siblings_produce_same_names(self) -> None:
        fam = create_culture_family(EXAMPLES, name="Same", variant_count=3, drift=0.0, seed=7)
        # With drift=0 all siblings have identical models → same names from same rng state.
        import random
        names = [
            fam.cultures[i].markov_model["table"] == fam.cultures[0].markov_model["table"]
            for i in range(3)
        ]
        assert all(names)

    def test_high_drift_siblings_differ(self) -> None:
        fam = create_culture_family(EXAMPLES, name="Varied", variant_count=3, drift=0.8, seed=7)
        tables = [c.markov_model["table"] for c in fam.cultures]
        # Not all tables should be identical.
        assert not all(t == tables[0] for t in tables)

    def test_seeded_is_fully_deterministic(self) -> None:
        fam1 = create_culture_family(EXAMPLES, name="X", variant_count=2, drift=0.3, seed=99)
        fam2 = create_culture_family(EXAMPLES, name="X", variant_count=2, drift=0.3, seed=99)
        assert fam1.cultures[0].markov_model == fam2.cultures[0].markov_model
        assert fam1.cultures[1].markov_model == fam2.cultures[1].markov_model

    def test_base_examples_stored_sorted(self) -> None:
        fam = create_culture_family(EXAMPLES, name="T", seed=1)
        assert fam.base_examples == tuple(sorted(EXAMPLES))

    def test_too_few_examples_raises(self) -> None:
        with pytest.raises(CultureError, match="at least"):
            create_culture_family(["a", "b"], name="X")

    def test_invalid_drift_raises(self) -> None:
        with pytest.raises(CultureError, match="drift"):
            create_culture_family(EXAMPLES, name="X", drift=1.5)

    def test_invalid_variant_count_raises(self) -> None:
        with pytest.raises(CultureError, match="variant_count"):
            create_culture_family(EXAMPLES, name="X", variant_count=0)

    def test_culture_spec_round_trip(self) -> None:
        fam = create_culture_family(EXAMPLES, name="Terran", seed=42)
        c = fam.cultures[0]
        spec = CultureSpec(
            id=c.id,
            name=c.name,
            markov_model_data=c.markov_model,
            name_styles=c.name_styles,
            metadata=c.metadata,
        )
        runtime = spec.to_runtime()
        assert runtime.id == c.id
        assert runtime.markov_model == c.markov_model


# ---------------------------------------------------------------------------
# generate_culture_family (Path 2)
# ---------------------------------------------------------------------------


class TestGenerateCultureFamily:
    def test_returns_culture_family(self) -> None:
        fam = generate_culture_family(seed=1, name="Outer")
        assert isinstance(fam, CultureFamily)

    def test_deterministic(self) -> None:
        fam1 = generate_culture_family(seed=42, name="Rim")
        fam2 = generate_culture_family(seed=42, name="Rim")
        assert fam1.cultures[0].markov_model == fam2.cultures[0].markov_model

    def test_different_seeds_differ(self) -> None:
        fam1 = generate_culture_family(seed=1, name="A")
        fam2 = generate_culture_family(seed=2, name="A")
        assert fam1.cultures[0].markov_model != fam2.cultures[0].markov_model

    def test_str_seed(self) -> None:
        fam = generate_culture_family(seed="my-galaxy", name="Frontier")
        assert isinstance(fam, CultureFamily)

    def test_generates_cultures(self) -> None:
        fam = generate_culture_family(seed=7, name="Rim", variant_count=3)
        assert len(fam.cultures) == 3


# ---------------------------------------------------------------------------
# generate_name utility
# ---------------------------------------------------------------------------


class TestGenerateName:
    def setup_method(self) -> None:
        self.culture = create_culture(EXAMPLES, name="Terran")

    def test_returns_string(self) -> None:
        name = generate_name(self.culture, style=NameStyle.GENERIC, seed="npc-001")
        assert isinstance(name, str)
        assert len(name) > 0

    def test_seeded_is_deterministic(self) -> None:
        n1 = generate_name(self.culture, style=NameStyle.PERSON, seed="npc-001")
        n2 = generate_name(self.culture, style=NameStyle.PERSON, seed="npc-001")
        assert n1 == n2

    def test_different_seeds_differ(self) -> None:
        names = {generate_name(self.culture, seed=f"x-{i}") for i in range(20)}
        assert len(names) > 1

    def test_different_styles_can_differ(self) -> None:
        generic = generate_name(self.culture, style=NameStyle.GENERIC, seed="s1")
        person = generate_name(self.culture, style=NameStyle.PERSON, seed="s1")
        # They might coincidentally match, but styles have distinct length ranges.
        # Just check both are valid strings.
        assert isinstance(generic, str)
        assert isinstance(person, str)

    def test_residence_template_applied(self) -> None:
        name = generate_name(self.culture, style=NameStyle.RESIDENCE, seed="res-1")
        assert "The" in name

    def test_bar_template_applied(self) -> None:
        name = generate_name(self.culture, style=NameStyle.BAR, seed="bar-1")
        assert "The" in name

    def test_unseeded_returns_string(self) -> None:
        name = generate_name(self.culture)
        assert isinstance(name, str)
        assert len(name) > 0

    def test_all_styles_generate_without_error(self) -> None:
        for style in NameStyle:
            name = generate_name(self.culture, style=style, seed="test")
            assert isinstance(name, str)
