"""Post-generation hook system (design doc §14.3).

Hooks allow developers to run custom logic immediately after each pipeline
stage, at generation time, without modifying the generator.  A hook receives
the freshly generated entity and may do anything with it — populate external
data structures, assign faction ownership, seed resource tables — but returns
nothing and has no effect on the generator's output.

Usage
-----
::

    from starloom.hooks import HookMap

    def assign_faction(planet):
        if planet.distinctiveness > 0.8:
            my_system.register_capital(planet.id)
        else:
            my_system.register_territory(planet.id)

    galaxy, report = generate_galaxy(
        seed="my-campaign-001",
        content_pack=content,
        hooks=HookMap(after_planet=assign_faction),
    )

Execution guarantees
--------------------
- Hooks are synchronous.  There is no async support.
- Exceptions raised inside a hook propagate immediately and halt generation.
  The generator never catches or swallows hook exceptions.
- Hooks are called in pipeline order: after_system → after_planet →
  after_sector → after_location → after_node → after_galaxy.
- The generator's return value is identical whether hooks are provided or not.

Reproducibility constraints
---------------------------
- In ``repro_mode="strict"`` any non-``None`` hook is rejected at validation
  time with a ``HookError``.
- In ``repro_mode="compatible"`` hooks may run freely; only the returned
  ``Galaxy`` object is part of the reproducibility contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from starloom.domain.models import (
        Galaxy,
        Location,
        Node,
        Planet,
        Sector,
        SolarSystem,
    )


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class HookError(RuntimeError):
    """Raised when a hook configuration violates strict-mode constraints."""

    def __init__(self, message: str, *, code: str = "HOOK_ERROR") -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# HookMap
# ---------------------------------------------------------------------------


@dataclass
class HookMap:
    """Container for per-stage hook callables.

    Each field is optional.  Pass only the hooks you need; unused fields add
    zero overhead during generation.

    Parameters
    ----------
    after_system:
        Called with each ``SolarSystem`` immediately after it is assembled.
    after_planet:
        Called with each ``Planet`` (primary and satellite) immediately after
        it is assembled.
    after_sector:
        Called with each ``Sector`` immediately after it is assembled.
    after_location:
        Called with each ``Location`` immediately after it is assembled.
    after_node:
        Called with each ``Node`` immediately after it is assembled.
    after_galaxy:
        Called with the completed ``Galaxy`` before the generator returns.
    """

    after_system:   Callable[["SolarSystem"], None] | None = field(default=None)
    after_planet:   Callable[["Planet"],      None] | None = field(default=None)
    after_sector:   Callable[["Sector"],      None] | None = field(default=None)
    after_location: Callable[["Location"],    None] | None = field(default=None)
    after_node:     Callable[["Node"],        None] | None = field(default=None)
    after_galaxy:   Callable[["Galaxy"],      None] | None = field(default=None)

    def is_empty(self) -> bool:
        """Return True when every hook slot is None (no-op HookMap)."""
        return all(
            hook is None
            for hook in (
                self.after_system, self.after_planet, self.after_sector,
                self.after_location, self.after_node, self.after_galaxy,
            )
        )

    def validate_strict(self) -> None:
        """Raise HookError if any hook is set while in strict repro mode."""
        if not self.is_empty():
            raise HookError(
                "Hooks are not permitted in repro_mode='strict'.  "
                "Set all hooks to None or omit the hooks argument.",
                code="HOOK_STRICT_MODE_VIOLATION",
            )


# ---------------------------------------------------------------------------
# Runner helpers (called from galaxy.py)
# ---------------------------------------------------------------------------


def run_hook_system(hooks: HookMap | None, system: "SolarSystem") -> None:
    if hooks is not None and hooks.after_system is not None:
        hooks.after_system(system)


def run_hook_planet(hooks: HookMap | None, planet: "Planet") -> None:
    if hooks is not None and hooks.after_planet is not None:
        hooks.after_planet(planet)


def run_hook_sector(hooks: HookMap | None, sector: "Sector") -> None:
    if hooks is not None and hooks.after_sector is not None:
        hooks.after_sector(sector)


def run_hook_location(hooks: HookMap | None, location: "Location") -> None:
    if hooks is not None and hooks.after_location is not None:
        hooks.after_location(location)


def run_hook_node(hooks: HookMap | None, node: "Node") -> None:
    if hooks is not None and hooks.after_node is not None:
        hooks.after_node(node)


def run_hook_galaxy(hooks: HookMap | None, galaxy: "Galaxy") -> None:
    if hooks is not None and hooks.after_galaxy is not None:
        hooks.after_galaxy(galaxy)
