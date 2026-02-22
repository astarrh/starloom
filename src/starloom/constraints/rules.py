"""Post-generation constraint validation (design doc §12).

Checks run after the full generation pipeline completes.  They produce
ValidationIssue objects collected into a ValidationReport.

Structural ERROR checks (always run):
  - DUPLICATE_SYSTEM_COORD  — two systems share the same (x, y) when rounded
  - DUPLICATE_PLANET_COORD  — two planets in the same system share (x, y)
  - INVALID_PARENT_ID       — satellite.parent_planet_id not in system's planet ids
  - DUPLICATE_ENTITY_ID     — any entity id appears more than once galaxy-wide

Soft WARNING checks (always run, promoted to ERROR in strict mode):
  - DENSITY_EXCEEDS_MAX     — sector density > content-pack max_density for its (topo, climate)
  - UNKNOWN_CULTURE_ID      — a culture_id referenced by a system not in Galaxy.cultures
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starloom.domain.models import ValidationIssue, ValidationReport
from starloom.domain.types import Severity, ValidationStage

if TYPE_CHECKING:
    from starloom.config import GalaxyConfig
    from starloom.content.loader import ContentPack
    from starloom.domain.models import Galaxy, Planet, SolarSystem

_COORD_PRECISION = 1  # digits used when quantising coordinates for uniqueness check


def validate_galaxy(
    galaxy: "Galaxy",
    config: "GalaxyConfig",
    *,
    content_pack: "ContentPack | None" = None,
) -> ValidationReport:
    """Run all structural and soft constraint checks against *galaxy*.

    Parameters
    ----------
    galaxy:
        Fully assembled Galaxy (any depth).
    config:
        The GalaxyConfig used to generate the galaxy.  ``config.strict`` controls
        whether warnings are promoted to errors.
    content_pack:
        When supplied, pack-aware checks (density caps) are also run.
    """
    issues: list[ValidationIssue] = []

    _check_duplicate_system_coords(galaxy, issues)
    _check_duplicate_entity_ids(galaxy, issues)
    _check_planet_coords_and_parents(galaxy, issues)
    _check_culture_ids(galaxy, issues)

    if content_pack is not None:
        _check_density_caps(galaxy, content_pack, issues)

    if config.strict:
        issues = [_promote(i) for i in issues]

    return ValidationReport(issues=tuple(issues))


# ---------------------------------------------------------------------------
# Structural checks
# ---------------------------------------------------------------------------


def _check_duplicate_system_coords(galaxy: "Galaxy", issues: list[ValidationIssue]) -> None:
    seen: dict[tuple[float, float], str] = {}
    for system in galaxy.systems:
        key = (round(system.x, _COORD_PRECISION), round(system.y, _COORD_PRECISION))
        if key in seen:
            issues.append(ValidationIssue(
                code="DUPLICATE_SYSTEM_COORD",
                severity=Severity.ERROR,
                stage=ValidationStage.CONSTRAINTS,
                message=(
                    f"Systems {seen[key]!r} and {system.id!r} share coordinate "
                    f"({key[0]}, {key[1]})."
                ),
                path="galaxy.systems",
                entity_id=system.id,
            ))
        else:
            seen[key] = system.id


def _check_duplicate_entity_ids(galaxy: "Galaxy", issues: list[ValidationIssue]) -> None:
    seen: dict[str, str] = {}  # id → path description

    def _register(entity_id: str, path: str) -> None:
        if entity_id in seen:
            issues.append(ValidationIssue(
                code="DUPLICATE_ENTITY_ID",
                severity=Severity.ERROR,
                stage=ValidationStage.CONSTRAINTS,
                message=f"Entity id {entity_id!r} appears at both {seen[entity_id]} and {path}.",
                path=path,
                entity_id=entity_id,
            ))
        else:
            seen[entity_id] = path

    for system in galaxy.systems:
        _register(system.id, f"galaxy.systems[{system.id}]")
        for planet in system.planets:
            _register(planet.id, f"{system.id}.planets[{planet.id}]")
            for sector in planet.sectors:
                _register(sector.id, f"{planet.id}.sectors[{sector.id}]")
                for location in sector.locations:
                    _register(location.id, f"{sector.id}.locations[{location.id}]")
                    for node in location.nodes:
                        _register(node.id, f"{location.id}.nodes[{node.id}]")


def _check_planet_coords_and_parents(galaxy: "Galaxy", issues: list[ValidationIssue]) -> None:
    for system in galaxy.systems:
        # Build set of primary planet ids for parent-reference checks
        planet_ids: set[str] = {p.id for p in system.planets}

        # Check for duplicate (x, y) among all planets in this system
        coord_seen: dict[tuple[float, float], str] = {}
        for planet in system.planets:
            key = (round(planet.x, _COORD_PRECISION), round(planet.y, _COORD_PRECISION))
            if key in coord_seen:
                issues.append(ValidationIssue(
                    code="DUPLICATE_PLANET_COORD",
                    severity=Severity.ERROR,
                    stage=ValidationStage.CONSTRAINTS,
                    message=(
                        f"Planets {coord_seen[key]!r} and {planet.id!r} in system "
                        f"{system.id!r} share coordinate ({key[0]}, {key[1]})."
                    ),
                    path=f"galaxy.systems[{system.id}].planets",
                    entity_id=planet.id,
                ))
            else:
                coord_seen[key] = planet.id

            # Validate parent_planet_id for satellites
            if planet.parent_planet_id is not None:
                if planet.parent_planet_id not in planet_ids:
                    issues.append(ValidationIssue(
                        code="INVALID_PARENT_ID",
                        severity=Severity.ERROR,
                        stage=ValidationStage.CONSTRAINTS,
                        message=(
                            f"Satellite {planet.id!r} references parent_planet_id "
                            f"{planet.parent_planet_id!r} which does not exist in "
                            f"system {system.id!r}."
                        ),
                        path=f"galaxy.systems[{system.id}].planets[{planet.id}]",
                        entity_id=planet.id,
                    ))


def _check_culture_ids(galaxy: "Galaxy", issues: list[ValidationIssue]) -> None:
    known = set(galaxy.cultures.keys())
    for system in galaxy.systems:
        for culture_id, _ in system.culture_ids:
            if culture_id not in known:
                issues.append(ValidationIssue(
                    code="UNKNOWN_CULTURE_ID",
                    severity=Severity.WARNING,
                    stage=ValidationStage.CONSTRAINTS,
                    message=(
                        f"System {system.id!r} references culture_id {culture_id!r} "
                        f"which is not present in Galaxy.cultures."
                    ),
                    path=f"galaxy.systems[{system.id}].culture_ids",
                    entity_id=system.id,
                ))


# ---------------------------------------------------------------------------
# Pack-aware soft checks
# ---------------------------------------------------------------------------


def _check_density_caps(
    galaxy: "Galaxy",
    content_pack: "ContentPack",
    issues: list[ValidationIssue],
) -> None:
    for system in galaxy.systems:
        for planet in system.planets:
            for sector in planet.sectors:
                entry = content_pack.sector_types.get(
                    (sector.topography.value, sector.climate.value)
                )
                if entry is None:
                    continue
                if sector.density > entry.max_density:
                    issues.append(ValidationIssue(
                        code="DENSITY_EXCEEDS_MAX",
                        severity=Severity.WARNING,
                        stage=ValidationStage.CONSTRAINTS,
                        message=(
                            f"Sector {sector.id!r} has density={sector.density} which "
                            f"exceeds max_density={entry.max_density} for "
                            f"topography={sector.topography.value!r}, "
                            f"climate={sector.climate.value!r}."
                        ),
                        path=f"galaxy.systems[{system.id}].planets[{planet.id}].sectors[{sector.id}]",
                        entity_id=sector.id,
                    ))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _promote(issue: ValidationIssue) -> ValidationIssue:
    """Promote a WARNING to an ERROR (used in strict mode)."""
    if issue.severity == Severity.WARNING:
        return ValidationIssue(
            code=issue.code,
            severity=Severity.ERROR,
            stage=issue.stage,
            message=issue.message,
            path=issue.path,
            entity_id=issue.entity_id,
        )
    return issue
