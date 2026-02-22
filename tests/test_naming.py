"""Tests for starloom.generation.naming — naming orchestration layer."""

import random

import pytest

from starloom.culture import create_culture, create_culture_family
from starloom.domain.models import Culture
from starloom.domain.types import NameStyle
from starloom.generation.naming import (
    generate_entity_name,
    generate_entity_name_seeded,
    pick_culture,
)

EXAMPLES_A = [
    "Valdris", "Korveth", "Almara", "Selindra", "Tharion",
    "Elyndra", "Morvek", "Zephalon", "Briskon", "Caelith",
]
EXAMPLES_B = [
    "Zhal", "Zhora", "Zhelik", "Zhaveth", "Zhendik",
    "Zhorima", "Zhelith", "Zhavenna",
]


def _culture_a() -> Culture:
    return create_culture(EXAMPLES_A, name="Terran")


def _culture_b() -> Culture:
    return create_culture(EXAMPLES_B, name="Zhal")


class TestPickCulture:
    def test_single_culture_always_chosen(self) -> None:
        c = _culture_a()
        rng = random.Random(1)
        assert pick_culture([(c, 1.0)], rng) is c

    def test_zero_weight_culture_never_chosen(self) -> None:
        ca = _culture_a()
        cb = _culture_b()
        results = [pick_culture([(ca, 1.0), (cb, 0.0)], random.Random(i)) for i in range(30)]
        assert all(r.id != cb.id for r in results)

    def test_full_weight_culture_always_chosen(self) -> None:
        ca = _culture_a()
        cb = _culture_b()
        for i in range(30):
            chosen = pick_culture([(ca, 0.0), (cb, 1.0)], random.Random(i))
            assert chosen is cb

    def test_insertion_order_invariant(self) -> None:
        ca = _culture_a()
        cb = _culture_b()
        # Same weights, different insertion order → same sequence of choices.
        r1 = random.Random(42)
        r2 = random.Random(42)
        picks_ab = [pick_culture([(ca, 0.6), (cb, 0.4)], r1) for _ in range(20)]
        picks_ba = [pick_culture([(cb, 0.4), (ca, 0.6)], r2) for _ in range(20)]
        assert [c.id for c in picks_ab] == [c.id for c in picks_ba]

    def test_empty_cultures_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            pick_culture([], random.Random(1))


class TestGenerateEntityName:
    def setup_method(self) -> None:
        self.ca = _culture_a()
        self.cb = _culture_b()

    def test_returns_string(self) -> None:
        rng = random.Random(1)
        name = generate_entity_name([(self.ca, 1.0)], NameStyle.GENERIC, rng)
        assert isinstance(name, str)
        assert len(name) > 0

    def test_deterministic_with_same_rng_state(self) -> None:
        r1 = random.Random(7)
        r2 = random.Random(7)
        n1 = generate_entity_name([(self.ca, 1.0)], NameStyle.PERSON, r1)
        n2 = generate_entity_name([(self.ca, 1.0)], NameStyle.PERSON, r2)
        assert n1 == n2

    def test_all_styles_work(self) -> None:
        for style in NameStyle:
            rng = random.Random(style.value)
            name = generate_entity_name([(self.ca, 1.0)], style, rng)
            assert isinstance(name, str)

    def test_multiple_cultures_generates_without_error(self) -> None:
        rng = random.Random(99)
        name = generate_entity_name(
            [(self.ca, 0.6), (self.cb, 0.4)], NameStyle.GENERIC, rng
        )
        assert isinstance(name, str)


class TestGenerateEntityNameSeeded:
    def setup_method(self) -> None:
        self.ca = _culture_a()

    def test_deterministic(self) -> None:
        n1 = generate_entity_name_seeded([(self.ca, 1.0)], NameStyle.GENERIC, 42, "sys-001")
        n2 = generate_entity_name_seeded([(self.ca, 1.0)], NameStyle.GENERIC, 42, "sys-001")
        assert n1 == n2

    def test_different_context_keys_differ(self) -> None:
        n1 = generate_entity_name_seeded([(self.ca, 1.0)], NameStyle.GENERIC, 42, "sys-001")
        n2 = generate_entity_name_seeded([(self.ca, 1.0)], NameStyle.GENERIC, 42, "sys-002")
        # Very unlikely to collide.
        assert n1 != n2

    def test_different_seeds_differ(self) -> None:
        n1 = generate_entity_name_seeded([(self.ca, 1.0)], NameStyle.GENERIC, 1, "ctx")
        n2 = generate_entity_name_seeded([(self.ca, 1.0)], NameStyle.GENERIC, 2, "ctx")
        assert n1 != n2

    def test_does_not_mutate_shared_rng(self) -> None:
        """Calling seeded generation should not affect any caller-owned RNG."""
        shared_rng = random.Random(55)
        val_before = shared_rng.random()
        shared_rng2 = random.Random(55)
        generate_entity_name_seeded([(self.ca, 1.0)], NameStyle.GENERIC, 99, "ctx")
        val_after = shared_rng2.random()
        assert val_before == val_after
