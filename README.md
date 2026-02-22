# starloom / pq_galaxy

**pq_galaxy** is a procedural galaxy generation library for games, tools, and interactive applications.

Generate deterministic, seed-based fictional galaxies with full hierarchical structure: solar systems → planets → sectors → locations → nodes.

> **Status:** In development (v0.1 pre-release). See [docs/roadmap/](docs/roadmap/) for the current plan.

## Features (planned for v0.1)

- Deterministic generation from a seed + config + content pack
- Culturally-driven naming via Markov models
- Fully hierarchical world structure (galaxy → system → planet → sector → location → node)
- YAML-based content packs for world-building rules
- Schema validation and structured error reporting
- Pure Python, no mandatory external dependencies
- Framework-agnostic (works with PyGame, Django, CLI, or any custom engine)

## Requirements

- Python 3.11+

## Development Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
```

## Documentation

- [Design Document](docs/design_doc.md)
- [Roadmap](docs/roadmap/README.md)
