"""Top-level generation pipeline orchestration (design doc §10).

Pipeline steps:
  1. Validate config
  2. Derive root seed
  3. Instantiate RNG streams
  4. Generate solar systems (names + placement)
  5. For each system: generate planets + satellites
  6. For each planet: generate sectors
  7. For each sector: generate locations
  8. For each location: generate nodes
  9. Assemble immutable Galaxy + ValidationReport
 10. (Hooks: Phase 05)
 11. (Constraint validation: Phase 04)

Depth flag:
  "systems"   → stop after step 4 (planets empty)
  "planets"   → stop after step 5 (sectors empty)
  "sectors"   → stop after step 6 (locations empty)
  "locations" → stop after step 7 (nodes empty)
  "nodes" / "galaxy" → full pipeline
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from starloom.config import CONFIG_VERSION, GalaxyConfig
from starloom.domain.models import (
    Culture,
    Galaxy,
    Location,
    Node,
    Planet,
    Sector,
    SolarSystem,
    ValidationReport,
)
from starloom.generation.locations import generate_locations_for_sector
from starloom.generation.nodes import generate_nodes_for_location
from starloom.generation.planets import generate_planets_for_system
from starloom.generation.sectors import generate_sectors_for_planet
from starloom.generation.systems import generate_systems
from starloom.rng import (
    STREAM_CULTURE,
    STREAM_LOCATIONS,
    STREAM_NAMING,
    STREAM_NODES,
    STREAM_PLANETS,
    STREAM_SATELLITES,
    STREAM_SECTORS,
    STREAM_SYSTEMS,
    make_rng,
    normalise_seed,
)

# Sentinel content-pack version used when no pack is loaded (Phase 03).
_NO_PACK_VERSION = "none"


def generate_galaxy(
    seed: int | str,
    config: GalaxyConfig | None = None,
    cultures: list[tuple[Culture, float]] | None = None,
    *,
    metadata: dict[str, Any] | None = None,
) -> tuple[Galaxy, ValidationReport]:
    """Generate a complete Galaxy from a seed.

    Parameters
    ----------
    seed:
        Root seed (int or str).  Strings are NFC-normalised and hashed.
    config:
        GalaxyConfig instance.  Defaults to GalaxyConfig() if not supplied.
    cultures:
        List of (Culture, weight) pairs used for name generation throughout
        the galaxy.  If None or empty, fallback indexed names are used.
    metadata:
        Extra key/value pairs stored in Galaxy.metadata.

    Returns
    -------
    (Galaxy, ValidationReport)
        The generated galaxy and a (currently empty) validation report.
        Constraint validation is implemented in Phase 04.
    """
    if config is None:
        config = GalaxyConfig()
    config.validate()

    root_seed = normalise_seed(seed)
    cultures = cultures or []

    depth = config.depth

    # ------------------------------------------------------------------
    # Instantiate RNG streams
    # ------------------------------------------------------------------
    naming_rng = make_rng(root_seed, STREAM_NAMING)
    placement_rng = make_rng(root_seed, STREAM_SYSTEMS)
    culture_rng = make_rng(root_seed, STREAM_CULTURE)
    planet_rng = make_rng(root_seed, STREAM_PLANETS)
    satellite_rng = make_rng(root_seed, STREAM_SATELLITES)
    sector_rng = make_rng(root_seed, STREAM_SECTORS)
    location_rng = make_rng(root_seed, STREAM_LOCATIONS)
    node_rng = make_rng(root_seed, STREAM_NODES)

    # ------------------------------------------------------------------
    # Step 4 — Generate solar systems (names + placement)
    # ------------------------------------------------------------------
    raw_systems, culture_registry = generate_systems(
        root_seed,
        config,
        cultures,
        naming_rng=naming_rng,
        placement_rng=placement_rng,
        culture_rng=culture_rng,
    )

    if depth == "systems":
        galaxy = Galaxy(
            seed=seed,
            config_version=CONFIG_VERSION,
            content_pack_version=_NO_PACK_VERSION,
            cultures=culture_registry,
            systems=tuple(raw_systems),
            metadata=_build_metadata(root_seed, config, metadata),
        )
        return galaxy, ValidationReport()

    # ------------------------------------------------------------------
    # Steps 5–8 — Planets → sectors → locations → nodes
    # ------------------------------------------------------------------
    final_systems: list[SolarSystem] = []

    for sys_idx, system in enumerate(raw_systems):
        # Per-system RNG contexts keep each system's generation independent.
        sys_planet_rng = make_rng(root_seed, STREAM_PLANETS, system.id)
        sys_naming_rng = make_rng(root_seed, STREAM_NAMING, system.id)
        sys_placement_rng = make_rng(root_seed, STREAM_SATELLITES, system.id)

        # Step 5 — Planets
        raw_planets = generate_planets_for_system(
            system.id,
            system.size,
            root_seed,
            config,
            cultures,
            planet_rng=sys_planet_rng,
            naming_rng=sys_naming_rng,
            placement_rng=sys_placement_rng,
        )

        if depth == "planets":
            final_systems.append(_replace_planets(system, raw_planets))
            continue

        # Steps 6–8 — Sectors → Locations → Nodes per planet
        final_planets: list[Planet] = []
        for planet in raw_planets:
            planet_sector_rng = make_rng(root_seed, STREAM_SECTORS, planet.id)
            planet_naming_rng = make_rng(root_seed, STREAM_NAMING, planet.id)

            # Step 6 — Sectors
            raw_sectors = generate_sectors_for_planet(
                planet.id,
                planet.size.value,
                config,
                cultures,
                sector_rng=planet_sector_rng,
                naming_rng=planet_naming_rng,
            )

            if depth == "sectors":
                final_planets.append(_replace_sectors(planet, raw_sectors))
                continue

            # Steps 7–8 — Locations + Nodes
            final_sectors: list[Sector] = []
            for sector in raw_sectors:
                sector_loc_rng = make_rng(root_seed, STREAM_LOCATIONS, sector.id)
                sector_naming_rng = make_rng(root_seed, STREAM_NAMING, sector.id)

                # Step 7 — Locations
                raw_locations = generate_locations_for_sector(
                    sector.id,
                    sector.density,
                    config,
                    cultures,
                    location_rng=sector_loc_rng,
                    naming_rng=sector_naming_rng,
                )

                if depth == "locations":
                    final_sectors.append(_replace_locations(sector, raw_locations))
                    continue

                # Step 8 — Nodes
                final_locations: list[Location] = []
                for location in raw_locations:
                    loc_node_rng = make_rng(root_seed, STREAM_NODES, location.id)
                    loc_naming_rng = make_rng(root_seed, STREAM_NAMING, location.id)

                    raw_nodes = generate_nodes_for_location(
                        location.id,
                        sector.density,
                        config,
                        cultures,
                        node_rng=loc_node_rng,
                        naming_rng=loc_naming_rng,
                    )
                    final_locations.append(_replace_nodes(location, raw_nodes))

                final_sectors.append(_replace_locations(sector, final_locations))

            final_planets.append(_replace_sectors(planet, final_sectors))

        final_systems.append(_replace_planets(system, final_planets))

    galaxy = Galaxy(
        seed=seed,
        config_version=CONFIG_VERSION,
        content_pack_version=_NO_PACK_VERSION,
        cultures=culture_registry,
        systems=tuple(final_systems),
        metadata=_build_metadata(root_seed, config, metadata),
    )
    return galaxy, ValidationReport()


# ---------------------------------------------------------------------------
# Immutable assembly helpers (frozen dataclasses can't be mutated in-place)
# ---------------------------------------------------------------------------


def _replace_planets(system: SolarSystem, planets: list[Planet]) -> SolarSystem:
    return SolarSystem(
        id=system.id,
        name=system.name,
        size=system.size,
        x=system.x,
        y=system.y,
        z=system.z,
        culture_ids=system.culture_ids,
        planets=tuple(planets),
    )


def _replace_sectors(planet: Planet, sectors: list[Sector]) -> Planet:
    return Planet(
        id=planet.id,
        name=planet.name,
        size=planet.size,
        classification=planet.classification,
        x=planet.x,
        y=planet.y,
        z=planet.z,
        parent_planet_id=planet.parent_planet_id,
        distinctiveness=planet.distinctiveness,
        sectors=tuple(sectors),
    )


def _replace_locations(sector: Sector, locations: list[Location]) -> Sector:
    return Sector(
        id=sector.id,
        name=sector.name,
        topography=sector.topography,
        climate=sector.climate,
        density=sector.density,
        urbanization=sector.urbanization,
        hostility=sector.hostility,
        remoteness=sector.remoteness,
        locations=tuple(locations),
    )


def _replace_nodes(location: Location, nodes: list[Node]) -> Location:
    return Location(
        id=location.id,
        name=location.name,
        location_type=location.location_type,
        size=location.size,
        features=location.features,
        distinctiveness=location.distinctiveness,
        nodes=tuple(nodes),
    )


def _build_metadata(
    root_seed: int,
    config: GalaxyConfig,
    extra: dict[str, Any] | None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "root_seed_int": root_seed,
        "repro_mode": config.repro_mode.value,
        "depth": config.depth,
    }
    if extra:
        meta.update(extra)
    return meta
