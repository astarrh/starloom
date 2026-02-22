# Seeded Galaxy Generator — Design Document (v0.2)

## Status
- Draft
- Date: 2026-02-21
- Author: Adam Starrh
- Updated: 2026-02-21 (culture system added)

---

## 1) Purpose
Create a standalone Python package for procedural galaxy generation that is:
- deterministic (seed-based),
- framework-agnostic,
- reusable in multiple games/tools (PyGame, CLI, tests),
- extensible via content packs and generation profiles.

This document defines architecture and constraints before implementation. The package is written from scratch as an independent library; no code is ported from existing projects.

---

## 2) Goals
1. Deterministic generation from a root seed.
2. Pure-Python core with no mandatory external dependencies.
3. Stable domain model independent of any storage or web framework.
4. Configurable world rules (sizes, densities, constraints).
5. Content-pack driven type definitions (YAML).
6. Good developer ergonomics and documentation.

---

## 3) Non-Goals (v0.x)
- No mandatory visual renderer.
- No networked/multiplayer synchronization layer.
- No save-game persistence format.
- No hard dependency on Django, PyGame, or any ORM.

---

## 4) Design Principles
- **Determinism first**: same seed + config + content pack + engine version => same output.
- **Pure core, thin adapters**: generation logic has no knowledge of databases or UI.
- **Explicit inputs**: no hidden global state; all randomness flows from the root seed.
- **Schema-driven content**: validate external data before generation begins.
- **Composability**: users may run only part of the pipeline (e.g., systems only, planets only).
- **Immutable outputs**: returned domain objects are immutable snapshots; generation may use internal mutable builders before finalization.

---

## 5) Package Layout
Primary package name: `pq_galaxy`.

```
pq_galaxy/
  __init__.py
  api.py                  # public entry points
  config.py               # dataclass-based config models and validators (no mandatory external deps)
  rng.py                  # deterministic RNG helpers, stream derivation
  domain/
    types.py              # enums and constants
    models.py             # dataclasses (Galaxy, System, Planet, Sector, Location, Node)
  content/
    schema.py             # content pack validation schema
    loader.py             # load and validate content packs
  culture/
    models.py             # Culture and CultureFamily dataclasses
    factory.py            # create_culture(), create_culture_family(), generate_culture_family()
    markov.py             # character n-gram model, trained per culture
  generation/
    galaxy.py             # top-level orchestration
    systems.py            # solar system generation
    planets.py            # planet and satellite generation
    sectors.py            # sector generation
    locations.py          # location generation
    nodes.py              # node generation
    naming.py             # name generation engine (delegates to culture)
  geometry.py             # pure spatial query helpers (distance, radius, nearest, character)
  hooks.py                # post-generation hook protocol and runner
  constraints/
    rules.py              # hard constraints and post-generation checks
  validation/
    reports.py            # warning/error report objects
  adapters/               # optional, kept separate from core
    django_mapper.py
    pygame_mapper.py
```

---

## 6) Domain Model

Returned entities are immutable dataclasses (frozen snapshot semantics). Generation internals may use mutable builders/lists during construction, then finalize to immutable objects before return. No ORM annotations, no Django model inheritance.

### 6.1 Mutability Policy

- Public domain outputs (`Galaxy`, `SolarSystem`, `Planet`, `Sector`, `Location`, `Node`) are immutable.
- The generator may mutate temporary internal structures while assembling outputs.
- Post-generation hooks can read entities and write to external systems, but do not mutate generator-owned entities in place.
- Any post-generation enrichment should produce derived external data or new copied objects, not in-place mutation of returned domain objects.

### Entity Hierarchy
```
Galaxy
  └─ SolarSystem (name, size, 3D coordinates)
     └─ Planet (name, size, classification, 3D coordinates, optional parent_planet_id)
        └─ Sector (name, sector_type, density)
           └─ Location (name, location_type, size, features)
              └─ Node (name, node_type)
```

### Core Entities

**Galaxy**
- `seed`: root seed (int or str)
- `config_version`: str
- `content_pack_version`: str
- `cultures`: dict[str, CultureSpec] (output registry keyed by culture id for self-contained serialization)
- `systems`: list[SolarSystem]
- `metadata`: dict

**SolarSystem**
- `id`: deterministic str (e.g. `sys-0007`)
- `name`: str
- `size`: Size enum (1–5)
- `x`: float  (galactic plane position)
- `y`: float  (galactic plane position)
- `z`: float  (presentation layer, bounded ±5, not used for gameplay distance)
- `culture_ids`: list[tuple[str, float]]  (culture id + weight, weights sum to 1.0)
- `planets`: list[Planet]

**Planet**
- `id`: deterministic str (e.g. `sys-0007-pl-003`)
- `name`: str
- `size`: Size enum
- `classification`: PlanetClass enum
- `x`: float  (position relative to system center)
- `y`: float
- `z`: float  (presentation layer, bounded ±2)
- `parent_planet_id`: str | None  (None for primary planets, set for satellites)
- `distinctiveness`: float  (computed; 0.0–1.0)
- `sectors`: list[Sector]

**Sector**
- `id`: deterministic str
- `name`: str
- `sector_type`: SectorType (topography × climate combination)
- `density`: int (1–10, capped by sector_type's max_density)
- `urbanization`: float  (computed from density; 0.0–1.0)
- `hostility`: float  (computed from climate; 0.0–1.0)
- `remoteness`: float  (computed from topography; 0.0–1.0)
- `locations`: list[Location]

**Location**
- `id`: deterministic str
- `name`: str
- `location_type`: LocationType
- `size`: Size enum
- `features`: list[str]
- `distinctiveness`: float  (computed; 0.0–1.0)
- `nodes`: list[Node]

**Node**
- `id`: deterministic str
- `name`: str
- `node_type`: NodeType
- `in_town`: bool
- `distinctiveness`: float  (computed; 0.0–1.0)

**Culture**
- `id`: deterministic str
- `name`: str (developer-assigned label, not generated)
- `markov_model`: trained character n-gram model (opaque Python object)
- `name_styles`: dict[NameStyle, StyleConfig] (per-style length and template rules)
- `metadata`: dict (origin examples, drift value, parent culture id if derived)

**CultureFamily**
- `id`: deterministic str
- `name`: str
- `cultures`: list[Culture]
- `base_examples`: list[str] (the seed words the family was derived from; minimum 4, recommended 8–15)
- `seed`: int | None (set if procedurally generated)

**CultureSpec**
- `id`: deterministic str
- `name`: str
- `markov_model_data`: JSON-serializable model payload (not a runtime model object)
- `name_styles`: dict[NameStyle, StyleConfig]
- `metadata`: dict

`Culture` and `CultureFamily` are plain Python dataclasses owned by the developer and passed as explicit inputs. The generator remains stateless between calls and does not retain culture objects internally. For self-contained output and round-trip serialization, the returned `Galaxy` includes a `cultures` registry of `CultureSpec` entries keyed by culture id, and entities store culture references by id.

### ID Strategy
IDs are stable deterministic strings derived from the generation path and index:
- `sys-0007`
- `sys-0007-pl-003`
- `sys-0007-pl-003-sec-01`
- `sys-0007-pl-003-sec-01-loc-2`
- `sys-0007-pl-003-sec-01-loc-2-nd-4`

---

## 7) Type System (domain/types.py)

All types are Python enums. Numeric values carry semantic weight (e.g. size affects counts and ranges).

### Sizes
```
TINY = 1
SMALL = 2
MEDIUM = 3
LARGE = 4
ENORMOUS = 5
```

### Planet Classifications
```
TELLURIC   # solid, habitable or habitable-adjacent
GASEOUS    # gas giants
ICE
LAVA
LIQUID
ASTEROID
```

### Topographies (7)
```
CANYON, BASIN, KARST, PLAINS, HILLS, CLIFFS, PEAKS
```

### Climates (7)
```
VOLCANIC, ARID, STEPPE, TEMPERATE, HUMID, RAINY, FROZEN
```

SectorType is the cross product of Topography × Climate. Each combination has a `max_density` value defined in the content pack.

### Location Types
```
TRIBAL, TRADING, CITY, METROPOLIS
```
Each has a density range determining when it can appear in a sector.

---

## 8) Deterministic RNG Strategy

### 8.1 Root Seed
Accept seed as `int | str`. Strings are hashed to int before use.

String seed normalization for deterministic hashing:
- Normalize with Unicode NFC.
- Encode as UTF-8 bytes.
- Hash with SHA-256.
- Use the first 8 bytes as unsigned 64-bit integer (big-endian).

### 8.2 Stream Derivation
Each generation stage gets its own isolated RNG stream, preventing changes in one stage from cascading to another:

```
stream_seed = hash64(f"{root_seed}:{stream_name}:{context_key}")
rng = random.Random(stream_seed)
```

RNG algorithm for v0.x is Python `random.Random` (MT19937). Any future RNG change is a breaking reproducibility change and must bump engine major version.

Named streams:
- `systems`
- `planets`
- `satellites`
- `sectors`
- `locations`
- `nodes`
- `naming`
- `culture`  (used during culture sampling at name generation time)

### 8.3 Sorted Inputs
Any collection used as input to a random choice is sorted before selection. This prevents output from depending on insertion order or dict ordering.

### 8.4 Version Pinning
Generator version is stored in output metadata. In `repro_mode="strict"`, stream derivation includes: engine major version, content-pack hash, and metric formula versions.

### 8.5 Reproducibility Contract

`generate_galaxy()` is reproducible when all of the following are identical:
- root seed
- config values
- content pack content hash
- engine major version
- RNG algorithm/version policy
- metric formula versions (for optional computed scores)

`repro_mode` options:
- `compatible` (default): preserve deterministic structure while allowing non-breaking metric refinements.
- `strict`: include version/materialization pins in derived stream context and fail if strict prerequisites are not met.

### 8.6 Deterministic Hooks Policy

Hooks never mutate generator output, but hook side effects are outside the reproducibility contract.
- In `repro_mode="strict"`, `hooks` must be `None` (or no-op hooks only).
- In `compatible` mode, hooks may run, but only generated `Galaxy` data is considered reproducible output.

---

## 9) Content Pack Model

A content pack is a directory containing YAML files that define the world's type system, naming data, and type affinities. YAML is the standard authoring and exchange format for content packs in v0.x. At load time, YAML is normalized to JSON-compatible objects and validated against JSON Schema before generation begins.

### 9.1 Default Pack

The package ships with a default content pack (`packs/default/`) that makes `generate_galaxy()` work out of the box with no configuration. Developers who do not specify a content pack get the default automatically.

### 9.2 Custom Packs

Developers may provide their own content pack in place of the default. In v0.x, custom packs **replace** the default entirely — there is no merging. A developer who wants to extend the defaults should copy the default pack directory and modify it. This keeps the loader simple and pack interactions predictable.

Custom packs are independent of cultures. A developer can use a sci-fi content pack (spaceports, relay stations, mining rigs) with culture families derived from player-provided names, or a fantasy pack with fully procedural cultures. The two systems do not depend on each other.

### 9.3 Content Pack Contents
- `planet_classes.yaml` — classification definitions (state, temperature range, gravity range)
- `sector_types.yaml` — topography × climate combinations with `max_density` and optional flags (e.g. `undersea`)
- `location_types.yaml` — types with density thresholds, climate/topography affinities, rarity score, adjective pools, descriptor pools
- `node_types.yaml` — POI types with density thresholds, in_town flag, name style, climate/topography affinities, rarity score, optional naming templates
- `naming/` — fallback word lists used when no cultures are provided (one file per name domain)

### 9.4 Affinity System

Location and node types may declare affinities in the content pack. Affinities filter or weight the eligible pool of types during generation based on the sector's topography and climate — without requiring any input from the developer at generation time.

```yaml
name: Fishing Village
type: TRIBAL
density_min: 1
density_max: 5
affinity:
  climates: [RAINY, HUMID]
  topographies: [BASIN, PLAINS]
```

Types with no affinity defined are eligible in any sector. Types with affinity defined are weighted higher in matching sectors and may be excluded from non-matching sectors (configurable strictness).

### 9.5 Rarity and Distinctiveness

These are two complementary read-only properties the generator produces to help developers identify notable entities without having to interpret raw type data themselves.

**Rarity** is a content-pack property on location and node types. It is a float in [0.0, 1.0] that controls how frequently a type is selected when it is eligible — independently of density thresholds and affinity. A type with `rarity: 1.0` (the default) is selected as often as chance allows. A type with `rarity: 0.05` appears in roughly 5% of eligible cases across the galaxy.

```yaml
name: Ruined Temple
type: TRIBAL
density_min: 1
density_max: 10
rarity: 0.03
```

Content pack authors use rarity to designate types that should feel like genuine discoveries — things a player remembers finding. The generator enforces the rarity weight at selection time; the developer doesn't need to do anything.

**Distinctiveness** is a computed float in [0.0, 1.0] on `Planet`, `Location`, and `Node`. It is derived by the generator after all types are assigned, based on a combination of:
- The rarity scores of the entity's assigned types
- How far the entity's density deviates from the median for its context
- The number of high-affinity type matches (more specific placement = more distinctive)

Distinctiveness is a read-only output — the developer never sets it. It is a convenience signal for finding entities worth surfacing in a game. The developer decides what to do with it:

```python
# Find landmark planets across reachable systems
landmarks = [
    p for s in reachable
    for p in s.planets
    if p.distinctiveness > 0.85
]

# Flag rare nodes for a special UI marker
rare_nodes = [
    n for n in location.nodes
    if n.distinctiveness > 0.9
]
```

A developer who never reads `distinctiveness` loses nothing. One who uses it gets a ranked signal for what's worth surfacing — without the generator making any narrative decisions on their behalf.

### 9.6 Sector Character Axes

Each generated `Sector` exposes three computed float properties derived from its `sector_type` and `density`. These are read-only outputs, not inputs — the generator derives them, the developer reads them if useful.

- `urbanization` — derived from density (low → frontier, high → metropolitan)
- `hostility` — derived from climate (e.g. VOLCANIC/ARID skew high, TEMPERATE/HUMID skew low)
- `remoteness` — derived from topography (e.g. PEAKS/CANYON skew high, PLAINS/BASIN skew low)

The mapping from sector_type to hostility/remoteness scores is defined in `sector_types.yaml`, giving content pack authors control over the character of each environment. Developers may use these axes to drive encounter tables, NPC behavior, quest availability, or any other game logic — or ignore them entirely.

### 9.7 Content Pack Schema Requirements
- Semantic version string.
- All referenced enums must map to valid domain types.
- Density values must be integers in [1, 10].
- Affinity climate and topography values must reference valid enum members.
- Hostility and remoteness scores must be floats in [0.0, 1.0].
- Rarity values must be floats in (0.0, 1.0]; 0.0 is disallowed (would make a type permanently inaccessible).
- Pack version hash is included in generated output metadata to support reproducibility claims.
- Loader builds a precomputed eligibility matrix `(sector_type, density) -> eligible location/node types` during validation to guarantee coverage checks in bounded time.

### 9.9 Optional Metrics Versioning

`distinctiveness`, `urbanization`, `hostility`, `remoteness`, and relevance ranking formulas are versioned independently from structural generation.

- Structural world layout/typing is the core deterministic output.
- Optional convenience metrics are deterministic for a fixed metric version but may evolve between versions.
- Output metadata includes `metric_versions` (e.g. `distinctiveness=v1`, `character_axes=v1`) so snapshots can pin expected values.

### 9.8 Data Exchange Patterns

To keep integrations predictable across engines and save systems, the package follows standard data exchange patterns:

- **Content packs:** canonical YAML documents (UTF-8).
- **Schema validation:** JSON Schema (Draft 2020-12) applied to normalized JSON-compatible objects derived from YAML.
- **Runtime API:** Python dataclasses for in-memory ergonomics.
- **Persistence recommendation (non-mandatory):** developer save files should store normalized JSON (or equivalent structured format) with explicit schema versions.
- **Binary alternatives:** MessagePack or CBOR are appropriate for compact saves when developers want smaller payloads; the logical schema remains the same.
- **TOML scope:** not used for content packs in v0.x to avoid multi-format ambiguity at generation APIs.

---

## 10) Generation Pipeline

```
1.  Load config
2.  Load and validate content pack
3.  Resolve cultures (accept developer-provided Culture/CultureFamily objects,
    or generate procedurally from seed if none provided)
4.  Derive root seed (int)
5.  Instantiate RNG streams
6.  Generate solar systems → run after_system hook per system
7.  For each system: generate planets + satellites → run after_planet hook per planet
8.  For each planet: generate sectors → run after_sector hook per sector
9.  For each sector: generate locations → run after_location hook per location
10. For each location: generate nodes → run after_node hook per node
11. Run constraint validation → produce report
12. Run after_galaxy hook
13. Return Galaxy dataclass + ValidationReport
```

Pipeline supports partial execution via flags (e.g. `depth="systems"` stops after step 6).
Culture objects may be passed at any level; lower levels inherit from their parent unless overridden.
Hooks are optional at every stage; omitted hooks are no-ops.

### 10.1 Validation Strategy

Validation runs in three phases to keep failures clear and actionable:

1. **Input/config validation (pre-generation)**
  - Validate config shape, ranges, and enum references.
  - Fail fast with `ConfigurationError` before RNG streams are instantiated.

2. **Content-pack validation (pre-generation)**
  - Parse YAML, normalize to JSON-compatible objects, validate against JSON Schema.
  - Run semantic checks (cross-file references, density bounds, affinity coverage).
  - Fail fast with `ContentPackValidationError` and structured field-level details.

3. **Constraint validation (post-generation)**
  - Run structural and soft-rule checks on the generated `Galaxy`.
  - Structural failures raise `GenerationConstraintError`.
  - Soft-rule violations are appended to `ValidationReport` as warnings unless `strict=True`.

4. **Retry exhaustion handling**
  - Placement/name selection operations use bounded retries.
  - On exhaustion, raise explicit typed errors (`PlacementExhaustedError`, `NameGenerationExhaustedError`) with stage context and attempted bounds.

`strict=True` behavior:
- Any warning-category validation issue is promoted to an exception.
- Default (`strict=False`) preserves warnings in `ValidationReport` and returns output when structural integrity is intact.

Validation reports should include stable machine-readable codes (e.g. `DENSITY_OUT_OF_RANGE`, `UNKNOWN_CULTURE_ID`) in addition to human-readable messages to support CI and tooling.

---

## 11) Generation Rules

### Solar Systems
- Count determined by config (e.g. 100 per galaxy).
- Name generated from system naming word list.
- Size chosen from weighted distribution.
- (x, y) placed within a configurable bounding area; uniqueness enforced on quantized keys `(qx, qy)` where `qx = round(x, coordinate_precision_digits)` and same for `y`.
- z assigned within ±5; not used for uniqueness or distance checks.
- System placement uses bounded retries per system and raises `PlacementExhaustedError` if uniqueness cannot be satisfied.

### Planets
- Count per system: function of system size (e.g. TINY → 1–5, ENORMOUS → 15–25).
- Classification split: roughly 1/3 TELLURIC, 2/3 other (gaseous, ice, lava, etc.).
- (x, y) placed relative to system center; range scales with system size; uniqueness enforced on quantized `(qx, qy)`.
- z assigned within ±2 for presentation purposes.
- Name drawn from planet naming word list.
- Planet placement uses bounded retries per planet and raises `PlacementExhaustedError` on exhaustion.

### Satellites
- Only medium, large, or enormous planets may have satellites.
- Satellite count caps: MEDIUM → max 2, LARGE → max 6, ENORMOUS → max 8.
- Satellites are always SMALL or TINY.
- (x, y) are small offsets from parent planet's position; z matches parent.
- Satellite offset placement uses bounded retries and raises `PlacementExhaustedError` on exhaustion.

### Sectors
- Count per planet: function of planet size (TINY → 2–5, ENORMOUS → 18–21).
- Each sector assigned a random SectorType and a density within [1, max_density for that type].
- Character axes (urbanization, hostility, remoteness) computed from sector_type and density using scores from content pack.
- Name generated by the naming engine seeded with a per-sector word sample.

### Locations
- Count per sector: 3–7.
- Eligible LocationTypes filtered by density range requirement AND climate/topography affinity.
- Name generated by naming engine using the sector's name sample.
- Size chosen randomly.

### Nodes
- Count per location: `density × random(1, 5)`.
- ~75–85% of nodes are in-town; ~15–25% are outside.
- Eligible NodeTypes filtered by density range, in_town flag, AND climate/topography affinity.
- Name generated from naming template or naming scheme per node type's style.

### 11.1 Retry Policy

Generation operations with collision/eligibility risk use bounded retries with explicit failure behavior:
- coordinate placement retries (`max_coordinate_retries`)
- name uniqueness retries (`max_name_retries`)
- affinity fallback retries (`max_affinity_retries`)

If retries are exhausted:
- raise typed exception in strict flows (`PlacementExhaustedError`, `NameGenerationExhaustedError`, `EligibilityExhaustedError`)
- or record a warning + deterministic fallback only when policy explicitly allows (`fallback_policy="allow"`)

---

## 12) Culture System (culture/)

Culture is the mechanism by which naming acquires local coherence and global variety. Each `Culture` holds a trained character-level model derived from a set of example names. All name generation for an entity uses the cultures attached to that entity, weighted by the provided ratios.

### 12.1 Culture Construction

Three paths produce a `Culture` or `CultureFamily`. All three return identical, serializable objects — the generator does not know or care which path was used.

**Path 1: Example-driven (developer or player provides examples)**
```python
from pq_galaxy.culture import create_culture_family

family = create_culture_family(
    examples=["Valdris", "Korveth", "Almara", "Selindra"],
    variant_count=3,    # number of related sub-cultures to derive
    drift=0.25,         # how far siblings diverge from each other (0.0–1.0)
    seed=12345,         # for reproducible drift variation
    name="Terran",
)
# family.cultures -> [Culture, Culture, Culture]
# each shares phonemic ancestry with the examples but varies by drift
```

This path is suitable for player-facing name input ("name a few worlds and we'll build your galaxy from them") or for developer hand-authoring of distinct civilizations.

**Path 2: Fully procedural (seed-driven, no examples)**
```python
from pq_galaxy.culture import generate_culture_family

family = generate_culture_family(
    seed=99887,
    variant_count=4,
    drift=0.3,
    name="Outer Rim",
)
```

The seed is used to generate the base example set internally before deriving the family. The developer never specifies phonemes. Useful when the developer wants variety without hand-authoring.

**Path 3: Single manual culture (full control)**
```python
from pq_galaxy.culture import create_culture

culture = create_culture(
    examples=["Zhal", "Zhora", "Zhelik", "Zhaveth"],
    name="Zhal",
)
```

### 12.2 Culture Drift

Drift controls how far a derived culture's n-gram weights shift away from the base model. At `drift=0.0`, all siblings are identical. At `drift=1.0`, siblings share only broad phonemic tendencies. Values around `0.2–0.4` produce the feel of regional dialects; values around `0.6–0.8` produce the feel of related but distinct languages.

Drift is applied by perturbing the base n-gram frequency tables using the generation seed, so drift is deterministic given the same inputs.

### 12.3 Assigning Cultures to Entities

Any entity that generates names accepts a `cultures` parameter: a list of `(Culture, weight)` pairs. Weights are normalized to sum to 1.0. At name generation time, a culture is sampled from the weighted distribution using the entity's RNG stream, then that culture's model generates the name.

```python
# A border system with two cultural influences
system = generate_system(
    seed="my-campaign-001",
    index=7,
    cultures=[(culture_a, 0.6), (culture_b, 0.4)],
    config=config,
    content_pack=content,
)

# A monocultural planet
planet = generate_planet(
    seed="my-campaign-001",
    system_id="sys-0007",
    index=3,
    cultures=[(culture_a, 1.0)],
    ...
)
```

If no `cultures` argument is provided, the generator falls back to the parent entity's cultures. If no cultures are specified anywhere in the call chain, the generator uses the content pack's default naming data (backwards-compatible behaviour).

Input APIs accept `(Culture, weight)` pairs for ergonomics. Output entities store culture references as `(culture_id, weight)` pairs, and the returned `Galaxy.cultures` registry carries `CultureSpec` entries for self-describing serialization. Runtime `Culture` objects can be reconstructed from `CultureSpec` on load.

### 12.4 Naming Engine (generation/naming.py)

`naming.py` is a thin orchestration layer. It receives an entity's resolved culture list, samples a culture, and delegates name generation to that culture's Markov model in `culture/markov.py`.

**Name Styles** are defined in `domain/types.py` and configured per culture:
- `GENERIC` — place-style names
- `PERSON` — personal names
- `RESIDENCE` — dwelling names (e.g. "The [Name] House")
- `BAR` — tavern/pub names (e.g. "The [Name] & [Name]")

Template strings use a `+` placeholder replaced with a generated name fragment at generation time. Style configs (length ranges, template patterns) can be overridden per culture in `CultureFamily` construction.

### 12.5 Name Generation Utility (culture/factory.py)

The culture system exposes a standalone name generation utility callable outside the generation pipeline. This is intended for developers who need culturally consistent names at runtime — NPC names, faction names, ship names, quest-giver names — without running a full generation pass.

```python
from pq_galaxy.culture import generate_name

# Generate a personal name consistent with a planet's dominant culture
npc_name = generate_name(
    culture=galaxy.cultures[planet.culture_ids[0][0]].to_runtime(),
    style=NameStyle.PERSON,
)
# -> "Selindra"

# Generate a place name consistent with a system's dominant culture
outpost_name = generate_name(culture=system_culture, style=NameStyle.GENERIC)
# -> "Korthavel"
```

The function is stateless and deterministic when a `seed` argument is provided:

```python
npc_name = generate_name(culture=culture, style=NameStyle.PERSON, seed="npc-0042")
# Same output every time for the same inputs
```

Without a seed, the function draws from the process-level random state and is not reproducible. For game-critical names (quest givers, faction leaders) the developer should supply a seed derived from their own game state.

This utility does not add the generated name to any entity or register it anywhere. It is a pure function that returns a string.

---

## 13) Constraint Validation (constraints/rules.py)

Post-generation checks run against the completed Galaxy object. Each violation produces an entry in the `ValidationReport` with a severity level. Severity is determined by the generator based on whether a violation breaks structural integrity or merely violates a soft rule.

### ERROR (structural integrity) — always raises an exception
- No two solar systems share the same quantized `(x, y)` key.
- No two planets within a system share the same quantized `(x, y)` key.
- Satellite `parent_planet_id` references a valid planet id in the same system.
- Every id in the galaxy is unique.

### WARNING (soft rules) — included in report, non-fatal by default
- Sector density exceeds its sector_type's max_density.
- Location type appears outside its defined density range.
- Node type appears outside its defined density range.
- A `culture_id` referenced by an entity is not present in `Galaxy.cultures`.

Developers may promote all warnings to errors via config (`strict=True`) for content pack validation workflows or CI environments. Individual warning categories can also be suppressed.

### 13.1 ValidationReport Contract

`ValidationReport` is a structured container of issues with stable machine-readable codes.

Suggested shape:

- `ok`: bool (true when no `ERROR` issues are present)
- `issues`: list[`ValidationIssue`]

Each `ValidationIssue` includes:

- `code`: str (stable identifier, e.g. `DENSITY_OUT_OF_RANGE`)
- `severity`: `ERROR` | `WARNING`
- `stage`: `config` | `content_pack` | `constraints`
- `path`: str | None (field/path context such as `sector_types[12].max_density`)
- `entity_id`: str | None (for post-generation entities such as `sys-0007-pl-003`)
- `message`: str (human-readable summary)

Example:

```json
{
  "ok": false,
  "issues": [
    {
      "code": "UNKNOWN_CULTURE_ID",
      "severity": "WARNING",
      "stage": "constraints",
      "path": "systems[7].culture_ids[1]",
      "entity_id": "sys-0007",
      "message": "culture_id 'culture-999' is not present in Galaxy.cultures"
    }
  ]
}
```

### 13.2 Error Code Catalog (Initial)

Initial stable codes for v0.x:

| Code | Severity | Stage | Meaning |
|------|----------|-------|---------|
| `CONFIG_INVALID_ENUM` | ERROR | config | Config field references an unknown enum member. |
| `CONFIG_OUT_OF_RANGE` | ERROR | config | Numeric config value is outside allowed range. |
| `PACK_SCHEMA_VIOLATION` | ERROR | content_pack | Content pack fails JSON Schema validation. |
| `PACK_UNKNOWN_REFERENCE` | ERROR | content_pack | Content pack references a missing or unknown type/id. |
| `PACK_AFFINITY_EMPTY_POOL` | WARNING | content_pack | Affinity rules produce no eligible type pool for at least one context. |
| `DUPLICATE_SYSTEM_COORD` | ERROR | constraints | Two systems share the same `(x, y)` coordinate. |
| `DUPLICATE_PLANET_COORD` | ERROR | constraints | Two planets in the same system share the same `(x, y)` coordinate. |
| `INVALID_PARENT_PLANET_ID` | ERROR | constraints | Satellite references a non-existent parent planet in its system. |
| `DUPLICATE_ENTITY_ID` | ERROR | constraints | Two entities share the same deterministic id. |
| `PLACEMENT_EXHAUSTED` | ERROR | constraints | Coordinate placement retries were exhausted before finding a valid unique placement. |
| `NAME_GENERATION_EXHAUSTED` | ERROR | constraints | Name generation retries were exhausted before producing a valid unique name. |
| `ELIGIBILITY_EXHAUSTED` | ERROR | constraints | No eligible type remained after filtering/fallback policy and retry budget. |
| `DENSITY_OUT_OF_RANGE` | WARNING | constraints | Entity appears outside allowed density range constraints. |
| `UNKNOWN_CULTURE_ID` | WARNING | constraints | Entity references a `culture_id` not present in `Galaxy.cultures`. |

Code identifiers are append-only in v0.x (new codes may be added, existing code names should not be repurposed).

### 13.3 Recommended Action by Code

| Code | Recommended Developer Action |
|------|-------------------------------|
| `CONFIG_INVALID_ENUM` | Correct enum value in config; rerun generation. |
| `CONFIG_OUT_OF_RANGE` | Adjust numeric config into allowed bounds; rerun generation. |
| `PACK_SCHEMA_VIOLATION` | Fix schema errors in YAML pack file(s); rerun pack validation before generation. |
| `PACK_UNKNOWN_REFERENCE` | Add or correct referenced ids/types in pack files; rerun pack validation. |
| `PACK_AFFINITY_EMPTY_POOL` | Relax affinity filters or add missing compatible types for affected contexts. |
| `DUPLICATE_SYSTEM_COORD` | Increase coordinate space/placement retries or adjust placement rules. |
| `DUPLICATE_PLANET_COORD` | Increase per-system placement space/retries; verify orbit/offset strategy. |
| `INVALID_PARENT_PLANET_ID` | Fix satellite parent assignment logic and id reference generation. |
| `DUPLICATE_ENTITY_ID` | Fix deterministic id derivation path/index inputs to ensure uniqueness. |
| `PLACEMENT_EXHAUSTED` | Increase placement bounds/retries or reduce density; verify coordinate quantization settings. |
| `NAME_GENERATION_EXHAUSTED` | Increase name retries, relax uniqueness constraints, or enrich source examples. |
| `ELIGIBILITY_EXHAUSTED` | Expand eligible type definitions or relax affinity strictness/fallback policy. |
| `DENSITY_OUT_OF_RANGE` | Correct density thresholds or selection filters in content/generation rules. |
| `UNKNOWN_CULTURE_ID` | Ensure `culture_id` references match entries present in `Galaxy.cultures`. |

In CI, treat all `ERROR` codes as build-breaking. Optionally treat selected `WARNING` codes as build-breaking via `strict=True`.

---

## 14) Public API

### 14.1 Generation

```python
from pq_galaxy.api import generate_galaxy, load_content_pack

content = load_content_pack("./packs/classic")
galaxy, report = generate_galaxy(
    seed="my-campaign-001",
    config={"system_count": 100, "profile": "classic"},
    content_pack=content,
)
```

Lower-level API for partial generation:
```python
from pq_galaxy.api import generate_system, generate_planet

system = generate_system(seed="my-campaign-001", index=7, config=config, content_pack=content)
planet = generate_planet(seed="my-campaign-001", system_id="sys-0007", index=3, ...)
```

Validation only:
```python
from pq_galaxy.api import validate_galaxy
report = validate_galaxy(galaxy, content_pack=content)
```

### 14.2 Geometry Helpers (pq_galaxy.geometry)

Pure functions that accept a `Galaxy` object and return filtered or sorted results. They use only (x, y) for distance calculations and have no side effects. The developer holds the `Galaxy` and passes it in — the module stores nothing.

```python
from pq_galaxy.geometry import systems_within_radius, nearest_systems, system_distance

# All systems within a discovery radius of a known system
reachable = systems_within_radius(galaxy, origin="sys-0007", radius=350.0)

# All systems within radius of an arbitrary coordinate (e.g. ship position)
reachable = systems_within_radius(galaxy, origin=(142.3, -87.1), radius=350.0)

# The N closest systems to a given origin
nearby = nearest_systems(galaxy, origin="sys-0007", count=5)

# Raw distance between two systems
d = system_distance(galaxy, "sys-0007", "sys-0042")
```

```python
from pq_galaxy.geometry import planets_by_distinctiveness

# Most distinctive planets across the whole galaxy, descending
landmarks = planets_by_distinctiveness(galaxy, threshold=0.8)

# Most distinctive within a set of systems (e.g. reachable ones)
landmarks = planets_by_distinctiveness(galaxy, systems=reachable, threshold=0.8)
```

Character axis queries let developers find sectors matching conditions relevant to their game systems — without the generator knowing what those systems are:

```python
from pq_galaxy.geometry import sectors_by_character, nodes_by_character

# Sectors suitable for a lawless frontier faction
frontier = sectors_by_character(galaxy, remoteness_min=0.7, urbanization_max=0.3)

# Sectors suitable for a hostile wilderness encounter zone
danger_zones = sectors_by_character(galaxy, hostility_min=0.8)

# Nodes in low-hostility, high-urbanization sectors (good for trade NPC placement)
trade_nodes = nodes_by_character(galaxy, hostility_max=0.3, urbanization_min=0.7)
```

All character axis parameters are optional and combinable. Results are returned as lists sorted by relevance (closest match to the specified thresholds first).

`origin` accepts either a system id (str) or a coordinate pair (tuple[float, float]).

These helpers are the intended primitive for implementing player discovery radius progression and for seeding external systems (factions, resources, encounter tables) with plausible locations. Dynamic game state — which systems have been visited, what the current radius is, which faction controls which sector — is the developer's responsibility and lives outside this package.

### 14.3 Post-Generation Hooks (pq_galaxy.hooks)

Hooks allow developers to run their own logic immediately after each pipeline stage, at generation time, without modifying the generator. A hook receives the freshly generated entity and may do anything with it — populate external data structures, assign faction ownership, seed resource tables — but returns nothing and has no effect on the generator's output.

```python
from pq_galaxy.hooks import HookMap

def assign_faction(planet):
    if planet.distinctiveness > 0.8:
        my_faction_system.register_capital(planet.id)
    else:
        my_faction_system.register_territory(planet.id)

def seed_resources(sector):
    my_resource_system.seed(
        sector_id=sector.id,
        hostility=sector.hostility,
        remoteness=sector.remoteness,
    )

galaxy, report = generate_galaxy(
    seed="my-campaign-001",
    content_pack=content,
    hooks=HookMap(
        after_planet=assign_faction,
        after_sector=seed_resources,
    ),
)
```

Available hook points:

| Hook | Called with |
|------|-------------|
| `after_system` | `SolarSystem` |
| `after_planet` | `Planet` |
| `after_sector` | `Sector` |
| `after_location` | `Location` |
| `after_node` | `Node` |
| `after_galaxy` | `Galaxy` |

Hook functions must be synchronous. Exceptions raised inside a hook propagate normally and halt generation. The generator does not catch or swallow hook errors.

In `repro_mode="strict"`, hooks are disabled (or must be no-op) so reproducibility applies to the entire execution path, not only returned data.

Hooks are entirely optional. A `generate_galaxy()` call with no `hooks` argument behaves identically to the current design. The hook system adds no overhead when unused.

---

## 15) Testing Strategy
- Unit tests per generator stage with fixed seeds and known expected outputs.
- Snapshot tests comparing generated Python objects against reference fixtures for stable seeds.
- Property-based tests for structural invariants (e.g. no duplicate coordinates within a system, satellite sizes always SMALL or TINY).
- Regression fixtures for a set of reference seeds maintained across releases.
- Content pack schema validation tests with both valid and intentionally malformed packs.
- Geometry helper tests: verify radius and nearest queries against known coordinate fixtures; verify `origin` accepts both system id and coordinate pair; verify z is never used in distance calculations; verify character axis queries return correct filtered results.
- Hook system tests: verify each hook point fires at the correct stage; verify hook exceptions propagate and halt generation; verify omitted hooks produce identical output to no-hooks baseline.
- Name generation utility tests: verify deterministic output when seed is provided; verify generated names are phonemically consistent with the source culture.
- Affinity system tests: verify that sector character axes are consistent with sector_type scores; verify affinity filtering produces type pools that match expected climates and topographies.
- Content pack coverage tests: verify every sector_type has at least one eligible location type and node type at every density level.
- Culture system tests: verify drift produces distinct but related models; verify example-driven and seed-driven paths are both deterministic.
- Reproducibility mode tests: verify `compatible` vs `strict` behavior and that strict mode rejects non-no-op hooks.
- Retry/failure tests: verify exhaustion paths raise typed errors with stable validation/error codes.

### 15.1 Performance Envelope (v0.1 Targets)

Target envelope on a typical developer machine for default profile:
- `system_count=100` end-to-end generation: under 1.5s
- `system_count=1000` end-to-end generation: under 20s
- memory usage for `system_count=1000`: under 1.0 GB peak
- content pack validation (single pack): under 300ms after warm file cache

These are non-binding targets used to guide implementation and regression checks; they are not API guarantees.

---

## 16) Licensing
The naming engine is implemented from scratch with no dependency on GPLv3 or other copyleft upstream sources. The package license is TBD but should be permissive (MIT or Apache 2.0 preferred).

---

## 17) Risks and Mitigations
- **Risk:** Reproducibility breaks across Python versions (hash randomization, float precision).
  - **Mitigation:** Apply the full reproducibility contract in Section 8 (seed normalization, RNG policy pinning, strict mode version inputs, and quantized coordinate uniqueness).
- **Risk:** Hidden coupling to data ordering.
  - **Mitigation:** Sort all input collections before random selection and keep weighted candidate pools stably ordered.
- **Risk:** Scope creep into game engine features.
  - **Mitigation:** Package generates world data only; game mechanics are the consumer's responsibility. Hooks, geometry helpers, and name utilities are read-only or side-effect-free from the generator's perspective.
- **Risk:** Hook exceptions silently corrupt generation by being swallowed.
  - **Mitigation:** Generator never catches hook exceptions; they propagate immediately. Documentation should advise developers to guard their own hook logic.
- **Risk:** `generate_name()` without a seed produces non-reproducible results that break determinism guarantees.
  - **Mitigation:** Document clearly that seeded calls are reproducible and unseeded calls are not. Unseeded use is opt-in; the function signature makes the seed argument explicit.
- **Risk:** Name generator produces too many collisions or nonsense strings for small seed word sets.
  - **Mitigation:** Use bounded retry policy from Section 11.1; enforce minimum seed word count; expose deterministic fallback only when fallback policy allows it.
- **Risk:** Very small example sets (e.g. 2–3 player-provided names) produce a degenerate Markov model.
  - **Mitigation:** Enforce a minimum example count (e.g. 4); supplement sparse models with character-level padding before training.
- **Risk:** Affinity constraints are too strict, leaving some sector types with no eligible location or node types.
  - **Mitigation:** Build an eligibility matrix during content-pack validation (Section 9.7) and use explicit exhaustion behavior (`ELIGIBILITY_EXHAUSTED`) when fallback policy disallows recovery.
- **Risk:** Culture objects become large and expensive to hold in memory if duplicated across every entity.
  - **Mitigation:** Store serializable `CultureSpec` entries once in `Galaxy.cultures`, keyed by culture id, and store only `(culture_id, weight)` references on entities. Developers own and pass runtime `Culture` objects as inputs. The generator retains no internal cross-call state; the output registry exists only to keep serialized galaxies self-describing.

---

## 18) Resolved Design Decisions

| # | Question | Decision |
|---|----------|----------|
| 1 | 2D or 3D system coordinates? | 2.5D. X and Y define position on the galactic plane and are used for all gameplay distance calculations. Z is a small bounded value (±5) available to consumers for presentation (parallax, render order, visual depth) but ignored by the generator's own proximity logic. A 2D consumer ignores Z entirely. |
| 2 | Constraint violations: hard-fail or warning-based? | Violations are categorized by severity at the generator level. Structural integrity violations (e.g. broken parent references, duplicate coordinates) are always `ERROR` and raise an exception. Soft rule violations (e.g. a node appearing outside its density range due to content pack edge cases) are `WARNING` and appear in the report but do not halt generation. Developers may promote warnings to errors via config for strict enforcement. |
| 3 | Minimum Python version? | 3.11+. |
| 4 | Serialization format? | Generator returns plain Python dataclass objects at runtime. No mandatory save-game format is imposed in v0.x. Content packs standardize on YAML (validated via JSON Schema after normalization). Save data is developer-defined, with versioned normalized JSON recommended (MessagePack/CBOR optional for compact storage), and `CultureSpec` in `Galaxy.cultures` for round-tripping. |
| 5 | Remote URL support in content pack loader? | No. Local paths only. Package is designed for local import; no network dependency. |
| 6 | Minimum example set for `create_culture_family()`? | 4 examples (enforced, but tunable via config). Documentation should recommend 8–15 for best results and note that richness improves with set size. |
| 7 | `drift` scalar or per-style? | Single scalar in v0.x for simplicity. Per-style drift is a candidate for a future version. |
| 8 | Culture inheritance: implicit or explicit? | Implicit. Child entities inherit their parent's cultures unless explicitly overridden. |
| 9 | Where do cultures live across calls and in outputs? | Developers own and pass `Culture` objects as inputs. The generator remains stateless and stores no cross-call internal state. Returned `Galaxy` outputs include `cultures` as an output registry (keyed by id), and entities reference cultures by id/weight pairs for self-contained serialization and round-tripping. |
| 10 | Should the package depend on Pydantic? | No mandatory Pydantic dependency in core v0.x. Core domain and config use stdlib dataclasses plus explicit validators. Optional adapter modules may expose Pydantic models for consumers that want them. |
| 11 | Should domain dataclasses be mutable? | Public domain outputs are immutable snapshots. Internal generation may use mutable builders and finalize to immutable dataclass objects before return. |
| 12 | How is strict reproducibility defined? | Strict mode pins seed normalization, RNG policy, engine major version, content-pack hash, and metric formula versions; hooks are disabled or no-op only. |
| 13 | How is coordinate uniqueness defined for floats? | Uniqueness uses quantized `(x, y)` keys with configurable precision digits to avoid raw-float equality ambiguity. |
| 14 | What happens when placement/naming/eligibility retries are exhausted? | Generation raises explicit typed errors and emits stable codes (`PLACEMENT_EXHAUSTED`, `NAME_GENERATION_EXHAUSTED`, `ELIGIBILITY_EXHAUSTED`). |
| 15 | Are convenience metrics part of core deterministic compatibility? | Structural generation is the core deterministic contract; optional convenience metrics are versioned and pinned separately. |
| 16 | Is performance part of the design? | v0.1 includes a non-binding performance envelope used for implementation guidance and regression monitoring. |

---

## 19) v0.1 Milestones
1. Finalize domain model and config schema.
2. Implement seeded RNG stream infrastructure.
3. Implement culture system: `create_culture()`, `create_culture_family()`, `generate_culture_family()`, Markov model, drift.
4. Implement naming engine with culture delegation and tests.
5. Implement system and planet generation with tests.
6. Implement sector, location, and node generation with tests.
7.  Implement content pack loader and schema validation.
8.  Implement geometry helpers (spatial queries, character axis queries, distinctiveness queries) with tests.
9.  Implement post-generation hook system with tests.
10. Implement `generate_name()` utility with tests.
11. Add constraint validation and report objects.
12. Generate comprehensive usage document for easy reference for game designers that includes everything they need to know to take advantage of the package (with as much berevity as possible without losing clarity)
13. Publish as local package and integrate with one consumer project.
