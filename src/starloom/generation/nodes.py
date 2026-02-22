"""Node generation (design doc §11 — Nodes)."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from starloom.domain.models import Culture, Node
from starloom.domain.types import NameStyle, NodeType
from starloom.generation.naming import generate_entity_name

if TYPE_CHECKING:
    from starloom.config import GalaxyConfig

# ---------------------------------------------------------------------------
# Constants (design doc §11 — Nodes)
# ---------------------------------------------------------------------------

# Node count: density × random(1, 5)
_NODE_COUNT_MULTIPLIER_RANGE: tuple[int, int] = (1, 5)

# ~75–85% in-town
_IN_TOWN_PROBABILITY: float = 0.80

_ALL_NODE_TYPES = sorted(NodeType, key=lambda nt: nt.value)


def _compute_distinctiveness(node_type: NodeType, in_town: bool) -> float:
    """Simple heuristic for Phase 03; refined in Phase 05 with rarity scores."""
    # Out-of-town nodes are rarer → slightly more distinctive.
    base = 0.3 if in_town else 0.5
    return round(base, 4)


# ---------------------------------------------------------------------------
# Public generation function
# ---------------------------------------------------------------------------


def generate_nodes_for_location(
    location_id: str,
    density: int,
    config: "GalaxyConfig",
    cultures: list[tuple[Culture, float]],
    *,
    node_rng: random.Random,
    naming_rng: random.Random,
) -> list[Node]:
    """Generate all nodes for one location.

    Count = density × random(1, 5).
    ~80% in-town, ~20% outside.
    """
    multiplier = node_rng.randint(*_NODE_COUNT_MULTIPLIER_RANGE)
    count = max(1, density * multiplier)

    nodes: list[Node] = []
    for n_idx in range(count):
        node_id = f"{location_id}-nd-{n_idx}"

        node_type: NodeType = node_rng.choice(_ALL_NODE_TYPES)
        in_town: bool = node_rng.random() < _IN_TOWN_PROBABILITY
        distinctiveness = _compute_distinctiveness(node_type, in_town)

        if cultures:
            style = NameStyle.BAR if node_type == NodeType.GENERIC else NameStyle.GENERIC
            name = generate_entity_name(cultures, style, naming_rng)
        else:
            name = f"Node-{n_idx}"

        nodes.append(
            Node(
                id=node_id,
                name=name,
                node_type=node_type,
                in_town=in_town,
                distinctiveness=distinctiveness,
            )
        )

    return nodes
