"""Tests for starloom.rng — seed normalisation, stream derivation, RNG helpers."""

import random

import pytest

from starloom.rng import (
    ALL_STREAMS,
    ENGINE_MAJOR_VERSION,
    STREAM_CULTURE,
    STREAM_NAMING,
    STREAM_NODES,
    STREAM_SYSTEMS,
    hash64,
    make_rng,
    normalise_seed,
    sorted_choice,
    sorted_choices,
    sorted_sample,
)


class TestHash64:
    def test_returns_int(self) -> None:
        assert isinstance(hash64("hello"), int)

    def test_deterministic(self) -> None:
        assert hash64("starloom") == hash64("starloom")

    def test_different_inputs_differ(self) -> None:
        assert hash64("alpha") != hash64("beta")

    def test_fits_64_bits(self) -> None:
        val = hash64("test")
        assert 0 <= val < 2**64


class TestNormaliseSeed:
    def test_int_passthrough(self) -> None:
        assert normalise_seed(42) == 42
        assert normalise_seed(-1) == -1

    def test_str_returns_int(self) -> None:
        result = normalise_seed("my-campaign")
        assert isinstance(result, int)

    def test_str_deterministic(self) -> None:
        assert normalise_seed("starloom") == normalise_seed("starloom")

    def test_str_nfc_normalisation(self) -> None:
        # é encoded two ways: precomposed NFC vs decomposed NFD
        nfc = "\u00e9"          # é (single code point)
        nfd = "e\u0301"         # e + combining accent
        # After NFC normalisation both should produce the same seed.
        assert normalise_seed(nfc) == normalise_seed(nfd)

    def test_invalid_type_raises(self) -> None:
        with pytest.raises(TypeError, match="int or str"):
            normalise_seed(3.14)  # type: ignore[arg-type]


class TestMakeRng:
    def test_returns_random_instance(self) -> None:
        rng = make_rng(42, STREAM_SYSTEMS)
        assert isinstance(rng, random.Random)

    def test_same_inputs_same_sequence(self) -> None:
        rng1 = make_rng(42, STREAM_SYSTEMS, "ctx-1")
        rng2 = make_rng(42, STREAM_SYSTEMS, "ctx-1")
        assert [rng1.random() for _ in range(10)] == [rng2.random() for _ in range(10)]

    def test_different_streams_differ(self) -> None:
        rng_sys = make_rng(42, STREAM_SYSTEMS)
        rng_nam = make_rng(42, STREAM_NAMING)
        # With overwhelming probability these will not match.
        assert rng_sys.random() != rng_nam.random()

    def test_different_context_keys_differ(self) -> None:
        rng_a = make_rng(42, STREAM_NODES, "loc-001")
        rng_b = make_rng(42, STREAM_NODES, "loc-002")
        assert rng_a.random() != rng_b.random()

    def test_strict_mode_differs_from_compatible(self) -> None:
        rng_compat = make_rng(42, STREAM_SYSTEMS, repro_mode="compatible")
        rng_strict = make_rng(
            42, STREAM_SYSTEMS,
            repro_mode="strict",
            content_pack_hash="abc123",
            metric_versions={"distinctiveness": "v1"},
        )
        assert rng_compat.random() != rng_strict.random()

    def test_strict_mode_deterministic(self) -> None:
        kwargs = dict(
            repro_mode="strict",
            content_pack_hash="deadbeef",
            metric_versions={"distinctiveness": "v1", "character_axes": "v1"},
        )
        rng1 = make_rng(99, STREAM_CULTURE, **kwargs)  # type: ignore[arg-type]
        rng2 = make_rng(99, STREAM_CULTURE, **kwargs)  # type: ignore[arg-type]
        assert [rng1.random() for _ in range(5)] == [rng2.random() for _ in range(5)]


class TestAllStreams:
    def test_named_constants_in_set(self) -> None:
        for name in (
            STREAM_SYSTEMS, STREAM_NAMING, STREAM_NODES, STREAM_CULTURE
        ):
            assert name in ALL_STREAMS

    def test_eight_named_streams(self) -> None:
        assert len(ALL_STREAMS) == 8


class TestSortedHelpers:
    def setup_method(self) -> None:
        self.rng = random.Random(42)

    def test_sorted_choice_deterministic(self) -> None:
        population = [3, 1, 4, 1, 5, 9, 2, 6]
        r1 = random.Random(42)
        r2 = random.Random(42)
        assert sorted_choice(r1, population) == sorted_choice(r2, population)

    def test_sorted_choice_insertion_order_invariant(self) -> None:
        pop_a = [3, 1, 4]
        pop_b = [4, 3, 1]  # same elements, different order
        r1 = random.Random(42)
        r2 = random.Random(42)
        assert sorted_choice(r1, pop_a) == sorted_choice(r2, pop_b)

    def test_sorted_sample_returns_correct_count(self) -> None:
        result = sorted_sample(self.rng, list(range(20)), k=5)
        assert len(result) == 5

    def test_sorted_sample_insertion_order_invariant(self) -> None:
        pop_a = [10, 2, 8, 4, 6]
        pop_b = [6, 4, 8, 2, 10]
        r1 = random.Random(99)
        r2 = random.Random(99)
        assert sorted_sample(r1, pop_a, k=3) == sorted_sample(r2, pop_b, k=3)

    def test_sorted_choices_weighted(self) -> None:
        rng = random.Random(7)
        results = sorted_choices(rng, ["a", "b", "c"], weights=[0.0, 0.0, 1.0], k=10)
        assert all(r == "c" for r in results)

    def test_sorted_choices_insertion_order_invariant(self) -> None:
        pop_a = ["x", "y"]
        wts_a = [0.8, 0.2]
        pop_b = ["y", "x"]
        wts_b = [0.2, 0.8]
        r1 = random.Random(1)
        r2 = random.Random(1)
        assert sorted_choices(r1, pop_a, wts_a, k=5) == sorted_choices(r2, pop_b, wts_b, k=5)
