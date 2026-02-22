"""Tests for the post-generation hook system (Phase 05)."""

from __future__ import annotations

import pytest

from starloom.config import GalaxyConfig, SystemConfig
from starloom.domain.models import Galaxy, Location, Node, Planet, Sector, SolarSystem
from starloom.domain.types import ReproMode
from starloom.hooks import HookError, HookMap


# ---------------------------------------------------------------------------
# HookMap unit tests
# ---------------------------------------------------------------------------


class TestHookMap:
    def test_empty_hookmap_is_empty(self) -> None:
        hm = HookMap()
        assert hm.is_empty()

    def test_hookmap_with_one_hook_not_empty(self) -> None:
        hm = HookMap(after_system=lambda s: None)
        assert not hm.is_empty()

    def test_all_hooks_set_not_empty(self) -> None:
        noop = lambda x: None  # noqa: E731
        hm = HookMap(
            after_system=noop,
            after_planet=noop,
            after_sector=noop,
            after_location=noop,
            after_node=noop,
            after_galaxy=noop,
        )
        assert not hm.is_empty()

    def test_validate_strict_raises_when_hooks_set(self) -> None:
        hm = HookMap(after_system=lambda s: None)
        with pytest.raises(HookError) as exc_info:
            hm.validate_strict()
        assert exc_info.value.code == "HOOK_STRICT_MODE_VIOLATION"

    def test_validate_strict_passes_when_empty(self) -> None:
        hm = HookMap()
        hm.validate_strict()  # should not raise


# ---------------------------------------------------------------------------
# Hook firing via generate_galaxy
# ---------------------------------------------------------------------------


def _small_config(depth: str = "nodes") -> GalaxyConfig:
    return GalaxyConfig(system=SystemConfig(count=2), depth=depth)


class TestHookFiring:
    def test_after_system_fired(self) -> None:
        from starloom.generation.galaxy import generate_galaxy
        seen: list[str] = []
        hooks = HookMap(after_system=lambda s: seen.append(s.id))
        config = _small_config("systems")
        generate_galaxy(1, config=config, hooks=hooks)
        assert len(seen) == 2  # 2 systems

    def test_after_planet_fired(self) -> None:
        from starloom.generation.galaxy import generate_galaxy
        seen: list[str] = []
        hooks = HookMap(after_planet=lambda p: seen.append(p.id))
        config = _small_config("planets")
        generate_galaxy(1, config=config, hooks=hooks)
        assert len(seen) > 0

    def test_after_sector_fired(self) -> None:
        from starloom.generation.galaxy import generate_galaxy
        seen: list[str] = []
        hooks = HookMap(after_sector=lambda s: seen.append(s.id))
        config = _small_config("sectors")
        generate_galaxy(1, config=config, hooks=hooks)
        assert len(seen) > 0

    def test_after_location_fired(self) -> None:
        from starloom.generation.galaxy import generate_galaxy
        seen: list[str] = []
        hooks = HookMap(after_location=lambda loc: seen.append(loc.id))
        config = _small_config("locations")
        generate_galaxy(1, config=config, hooks=hooks)
        assert len(seen) > 0

    def test_after_node_fired(self) -> None:
        from starloom.generation.galaxy import generate_galaxy
        seen: list[str] = []
        hooks = HookMap(after_node=lambda n: seen.append(n.id))
        config = _small_config("nodes")
        generate_galaxy(1, config=config, hooks=hooks)
        assert len(seen) > 0

    def test_after_galaxy_fired_once(self) -> None:
        from starloom.generation.galaxy import generate_galaxy
        seen: list[str] = []
        hooks = HookMap(after_galaxy=lambda g: seen.append("galaxy"))
        config = _small_config("systems")
        generate_galaxy(1, config=config, hooks=hooks)
        assert seen == ["galaxy"]

    def test_after_galaxy_fired_at_each_depth(self) -> None:
        from starloom.generation.galaxy import generate_galaxy
        for depth in ("systems", "planets", "sectors", "locations", "nodes"):
            seen: list[str] = []
            hooks = HookMap(after_galaxy=lambda g: seen.append("g"))
            config = _small_config(depth)
            generate_galaxy(1, config=config, hooks=hooks)
            assert seen == ["g"], f"after_galaxy not fired at depth={depth!r}"

    def test_no_hooks_produces_same_galaxy(self) -> None:
        from starloom.generation.galaxy import generate_galaxy
        config = _small_config("planets")
        galaxy_no_hooks, _ = generate_galaxy(42, config=config)
        galaxy_hooks, _ = generate_galaxy(42, config=config, hooks=HookMap())
        # Systems should be identical
        assert len(galaxy_no_hooks.systems) == len(galaxy_hooks.systems)
        for sa, sb in zip(galaxy_no_hooks.systems, galaxy_hooks.systems):
            assert sa.id == sb.id
            assert sa.x == sb.x
            assert sa.y == sb.y


# ---------------------------------------------------------------------------
# Hook receives correct entity type
# ---------------------------------------------------------------------------


class TestHookEntityTypes:
    def test_after_system_receives_solar_system(self) -> None:
        from starloom.generation.galaxy import generate_galaxy
        received: list[object] = []
        hooks = HookMap(after_system=lambda s: received.append(s))
        config = _small_config("systems")
        generate_galaxy(1, config=config, hooks=hooks)
        assert all(isinstance(obj, SolarSystem) for obj in received)

    def test_after_planet_receives_planet(self) -> None:
        from starloom.generation.galaxy import generate_galaxy
        received: list[object] = []
        hooks = HookMap(after_planet=lambda p: received.append(p))
        config = _small_config("planets")
        generate_galaxy(1, config=config, hooks=hooks)
        assert all(isinstance(obj, Planet) for obj in received)

    def test_after_sector_receives_sector(self) -> None:
        from starloom.generation.galaxy import generate_galaxy
        received: list[object] = []
        hooks = HookMap(after_sector=lambda s: received.append(s))
        config = _small_config("sectors")
        generate_galaxy(1, config=config, hooks=hooks)
        assert all(isinstance(obj, Sector) for obj in received)

    def test_after_location_receives_location(self) -> None:
        from starloom.generation.galaxy import generate_galaxy
        received: list[object] = []
        hooks = HookMap(after_location=lambda loc: received.append(loc))
        config = _small_config("locations")
        generate_galaxy(1, config=config, hooks=hooks)
        assert all(isinstance(obj, Location) for obj in received)

    def test_after_node_receives_node(self) -> None:
        from starloom.generation.galaxy import generate_galaxy
        received: list[object] = []
        hooks = HookMap(after_node=lambda n: received.append(n))
        config = _small_config("nodes")
        generate_galaxy(1, config=config, hooks=hooks)
        assert all(isinstance(obj, Node) for obj in received)

    def test_after_galaxy_receives_galaxy(self) -> None:
        from starloom.generation.galaxy import generate_galaxy
        received: list[object] = []
        hooks = HookMap(after_galaxy=lambda g: received.append(g))
        config = _small_config("systems")
        generate_galaxy(1, config=config, hooks=hooks)
        assert all(isinstance(obj, Galaxy) for obj in received)


# ---------------------------------------------------------------------------
# Exception propagation
# ---------------------------------------------------------------------------


class TestHookExceptionPropagation:
    def test_exception_in_after_system_propagates(self) -> None:
        from starloom.generation.galaxy import generate_galaxy

        def bad_hook(s: SolarSystem) -> None:
            raise ValueError("hook bomb")

        hooks = HookMap(after_system=bad_hook)
        config = _small_config("systems")
        with pytest.raises(ValueError, match="hook bomb"):
            generate_galaxy(1, config=config, hooks=hooks)

    def test_exception_in_after_planet_propagates(self) -> None:
        from starloom.generation.galaxy import generate_galaxy

        def bad_hook(p: Planet) -> None:
            raise RuntimeError("planet hook error")

        hooks = HookMap(after_planet=bad_hook)
        config = _small_config("planets")
        with pytest.raises(RuntimeError, match="planet hook error"):
            generate_galaxy(1, config=config, hooks=hooks)

    def test_exception_in_after_galaxy_propagates(self) -> None:
        from starloom.generation.galaxy import generate_galaxy

        def bad_hook(g: Galaxy) -> None:
            raise TypeError("galaxy hook error")

        hooks = HookMap(after_galaxy=bad_hook)
        config = _small_config("systems")
        with pytest.raises(TypeError, match="galaxy hook error"):
            generate_galaxy(1, config=config, hooks=hooks)


# ---------------------------------------------------------------------------
# Strict mode
# ---------------------------------------------------------------------------


class TestStrictModeHooks:
    def test_strict_mode_rejects_non_empty_hooks(self) -> None:
        from starloom.generation.galaxy import generate_galaxy
        config = GalaxyConfig(
            system=SystemConfig(count=2),
            repro_mode=ReproMode.STRICT,
            depth="systems",
        )
        hooks = HookMap(after_system=lambda s: None)
        with pytest.raises(HookError) as exc_info:
            generate_galaxy(1, config=config, hooks=hooks)
        assert exc_info.value.code == "HOOK_STRICT_MODE_VIOLATION"

    def test_strict_mode_allows_none_hooks(self) -> None:
        from starloom.generation.galaxy import generate_galaxy
        config = GalaxyConfig(
            system=SystemConfig(count=2),
            repro_mode=ReproMode.STRICT,
            depth="systems",
        )
        # hooks=None should pass silently
        galaxy, report = generate_galaxy(1, config=config, hooks=None)
        assert len(galaxy.systems) == 2

    def test_strict_mode_allows_empty_hookmap(self) -> None:
        from starloom.generation.galaxy import generate_galaxy
        config = GalaxyConfig(
            system=SystemConfig(count=2),
            repro_mode=ReproMode.STRICT,
            depth="systems",
        )
        # Empty HookMap is equivalent to no hooks
        galaxy, report = generate_galaxy(1, config=config, hooks=HookMap())
        assert len(galaxy.systems) == 2

    def test_compatible_mode_allows_hooks(self) -> None:
        from starloom.generation.galaxy import generate_galaxy
        seen: list[str] = []
        config = GalaxyConfig(
            system=SystemConfig(count=2),
            repro_mode=ReproMode.COMPATIBLE,
            depth="systems",
        )
        hooks = HookMap(after_system=lambda s: seen.append(s.id))
        generate_galaxy(1, config=config, hooks=hooks)
        assert len(seen) == 2
