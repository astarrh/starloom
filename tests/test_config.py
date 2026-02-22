"""Tests for starloom.config."""

import pytest

from starloom.config import ConfigurationError, GalaxyConfig, RetryPolicy, SystemConfig
from starloom.domain.types import ReproMode


class TestSystemConfig:
    def test_defaults_valid(self) -> None:
        SystemConfig().validate()  # should not raise

    def test_zero_count_raises(self) -> None:
        with pytest.raises(ConfigurationError, match="CONFIG_OUT_OF_RANGE"):
            SystemConfig(count=0).validate()

    def test_negative_count_raises(self) -> None:
        with pytest.raises(ConfigurationError, match="CONFIG_OUT_OF_RANGE"):
            SystemConfig(count=-5).validate()

    def test_negative_bound_raises(self) -> None:
        with pytest.raises(ConfigurationError, match="CONFIG_OUT_OF_RANGE"):
            SystemConfig(placement_bound=-1.0).validate()

    def test_negative_precision_raises(self) -> None:
        with pytest.raises(ConfigurationError, match="CONFIG_OUT_OF_RANGE"):
            SystemConfig(coordinate_precision_digits=-1).validate()


class TestRetryPolicy:
    def test_defaults_valid(self) -> None:
        RetryPolicy().validate()

    def test_zero_retries_raises(self) -> None:
        with pytest.raises(ConfigurationError, match="CONFIG_OUT_OF_RANGE"):
            RetryPolicy(max_coordinate_retries=0).validate()


class TestGalaxyConfig:
    def test_defaults_valid(self) -> None:
        GalaxyConfig().validate()

    def test_default_repro_mode(self) -> None:
        assert GalaxyConfig().repro_mode == ReproMode.COMPATIBLE

    def test_strict_mode(self) -> None:
        cfg = GalaxyConfig(repro_mode=ReproMode.STRICT)
        cfg.validate()
        assert cfg.repro_mode == ReproMode.STRICT

    def test_invalid_depth_raises(self) -> None:
        with pytest.raises(ConfigurationError, match="CONFIG_INVALID_ENUM"):
            GalaxyConfig(depth="moon").validate()

    def test_valid_depths(self) -> None:
        for depth in ("galaxy", "systems", "planets", "sectors", "locations", "nodes"):
            GalaxyConfig(depth=depth).validate()  # should not raise

    def test_invalid_fallback_policy_raises(self) -> None:
        with pytest.raises(ConfigurationError, match="CONFIG_INVALID_ENUM"):
            GalaxyConfig(fallback_policy="maybe").validate()
