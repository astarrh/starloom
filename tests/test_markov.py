"""Tests for starloom.culture.markov."""

import random

import pytest

from starloom.culture.markov import (
    MIN_EXAMPLES,
    apply_drift,
    generate,
    supplement_sparse_model,
    train,
)

# A plausible set of sci-fi planet names used throughout these tests.
EXAMPLES = [
    "Valdris", "Korveth", "Almara", "Selindra", "Tharion",
    "Elyndra", "Morvek", "Zephalon", "Briskon", "Caelith",
]

MINIMAL = ["Zhal", "Zhora", "Zhelik", "Zhaveth"]  # exactly MIN_EXAMPLES


class TestTrain:
    def test_returns_dict_with_required_keys(self) -> None:
        model = train(EXAMPLES)
        assert "n" in model
        assert "starts" in model
        assert "table" in model
        assert "min_len" in model
        assert "max_len" in model

    def test_default_order_is_2(self) -> None:
        model = train(EXAMPLES)
        assert model["n"] == 2

    def test_custom_order(self) -> None:
        model = train(EXAMPLES, order=3)
        assert model["n"] == 3

    def test_table_probabilities_sum_to_one(self) -> None:
        model = train(EXAMPLES)
        for ctx, transitions in model["table"].items():
            total = sum(transitions.values())
            assert abs(total - 1.0) < 1e-9, f"Context {ctx!r} sums to {total}"

    def test_starts_are_sorted(self) -> None:
        model = train(EXAMPLES)
        assert model["starts"] == sorted(model["starts"])

    def test_too_few_examples_raises(self) -> None:
        with pytest.raises(ValueError, match="At least"):
            train(["Alpha", "Beta", "Gamma"])

    def test_exactly_min_examples_ok(self) -> None:
        train(MINIMAL)  # should not raise

    def test_model_is_json_serialisable(self) -> None:
        import json
        model = train(EXAMPLES)
        dumped = json.dumps(model)
        loaded = json.loads(dumped)
        assert loaded["n"] == model["n"]


class TestGenerate:
    def setup_method(self) -> None:
        self.model = train(EXAMPLES)
        self.rng = random.Random(42)

    def test_returns_non_empty_string(self) -> None:
        name = generate(self.model, self.rng)
        assert isinstance(name, str)
        assert len(name) > 0

    def test_no_sentinel_characters(self) -> None:
        for _ in range(50):
            name = generate(self.model, random.Random(random.randint(0, 10**9)))
            assert "\x00" not in name
            assert "\x01" not in name

    def test_length_within_bounds(self) -> None:
        for _ in range(50):
            name = generate(self.model, random.Random(random.randint(0, 10**9)))
            assert self.model["min_len"] <= len(name) <= self.model["max_len"]

    def test_capitalized(self) -> None:
        name = generate(self.model, self.rng)
        assert name[0].isupper()

    def test_deterministic_with_same_rng_state(self) -> None:
        r1 = random.Random(7)
        r2 = random.Random(7)
        assert generate(self.model, r1) == generate(self.model, r2)

    def test_different_seeds_usually_differ(self) -> None:
        names = {generate(self.model, random.Random(i)) for i in range(20)}
        assert len(names) > 1, "Expected some variation across 20 seeds"


class TestApplyDrift:
    def setup_method(self) -> None:
        self.base = train(EXAMPLES)
        self.rng = random.Random(99)

    def test_zero_drift_identical_table(self) -> None:
        drifted = apply_drift(self.base, 0.0, self.rng)
        assert drifted["table"] == self.base["table"]

    def test_nonzero_drift_changes_weights(self) -> None:
        drifted = apply_drift(self.base, 0.5, self.rng)
        # At least some entries should differ.
        assert drifted["table"] != self.base["table"]

    def test_drifted_probabilities_still_sum_to_one(self) -> None:
        drifted = apply_drift(self.base, 0.4, self.rng)
        for ctx, transitions in drifted["table"].items():
            total = sum(transitions.values())
            assert abs(total - 1.0) < 1e-9, f"Context {ctx!r} sums to {total}"

    def test_drift_is_deterministic(self) -> None:
        d1 = apply_drift(self.base, 0.3, random.Random(42))
        d2 = apply_drift(self.base, 0.3, random.Random(42))
        assert d1["table"] == d2["table"]

    def test_higher_drift_diverges_more(self) -> None:
        low = apply_drift(self.base, 0.1, random.Random(5))
        high = apply_drift(self.base, 0.9, random.Random(5))
        # Measure total variation distance for one context.
        ctx = next(iter(self.base["table"]))
        base_w = self.base["table"][ctx]
        low_w = low["table"][ctx]
        high_w = high["table"][ctx]
        diff_low = sum(abs(base_w.get(c, 0) - low_w.get(c, 0)) for c in base_w)
        diff_high = sum(abs(base_w.get(c, 0) - high_w.get(c, 0)) for c in base_w)
        assert diff_high >= diff_low

    def test_generate_still_works_after_drift(self) -> None:
        drifted = apply_drift(self.base, 0.5, self.rng)
        name = generate(drifted, random.Random(1))
        assert isinstance(name, str)
        assert len(name) >= self.base["min_len"]


class TestSupplementSparseModel:
    def test_supplement_does_not_raise(self) -> None:
        model = train(MINIMAL)
        supplemented = supplement_sparse_model(model, MINIMAL)
        assert "table" in supplemented

    def test_supplemented_still_generates(self) -> None:
        model = train(MINIMAL)
        supplemented = supplement_sparse_model(model, MINIMAL)
        name = generate(supplemented, random.Random(3))
        assert isinstance(name, str)
        assert len(name) > 0

    def test_supplemented_probabilities_sum_to_one(self) -> None:
        model = supplement_sparse_model(train(MINIMAL), MINIMAL)
        for ctx, transitions in model["table"].items():
            total = sum(transitions.values())
            assert abs(total - 1.0) < 1e-9
