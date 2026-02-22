"""Node generation (design doc §11 — Nodes)."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from starloom.domain.models import Culture, Node
from starloom.domain.types import ClimateType, NameStyle, NodeType, TopographyType
from starloom.generation.errors import EligibilityExhaustedError
from starloom.generation.naming import generate_entity_name

if TYPE_CHECKING:
    from starloom.config import GalaxyConfig
    from starloom.content.loader import ContentPack

_NODE_COUNT_MULTIPLIER_RANGE: tuple[int, int] = (1, 5)
_IN_TOWN_PROBABILITY: float = 0.80
_ALL_NODE_TYPES = sorted(NodeType, key=lambda nt: nt.value)


def _compute_distinctiveness(node_type: NodeType, in_town: bool) -> float:
    base = 0.3 if in_town else 0.5
    return round(base, 4)


def generate_nodes_for_location(
    location_id: str,
    density: int,
    config: "GalaxyConfig",
    cultures: list[tuple[Culture, float]],
    *,
    node_rng: random.Random,
    naming_rng: random.Random,
    content_pack: "ContentPack | None" = None,
    topography: TopographyType | None = None,
    climate: ClimateType | None = None,
) -> list[Node]:
    """Generate all nodes for one location.

    Count = density × random(1, 5).  ~80% in-town, ~20% outside.
    When content_pack + topography + climate are provided, node type
    eligibility is read from the pack's eligibility matrix.
    """
    multiplier = node_rng.randint(*_NODE_COUNT_MULTIPLIER_RANGE)
    count = max(1, density * multiplier)

    nodes: list[Node] = []
    for n_idx in range(count):
        node_id = f"{location_id}-nd-{n_idx}"
        in_town: bool = node_rng.random() < _IN_TOWN_PROBABILITY

        # Resolve eligible node types
        if content_pack is not None and topography is not None and climate is not None:
            eligible_values = content_pack.eligible_node_types(topography, climate, density, in_town)
            eligible_types: list[NodeType] = [NodeType(v) for v in eligible_values]
        else:
            eligible_types = _ALL_NODE_TYPES

        if not eligible_types:
            if config.fallback_policy == "allow":
                eligible_types = _ALL_NODE_TYPES
            else:
                raise EligibilityExhaustedError(
                    f"ELIGIBILITY_EXHAUSTED: no eligible node types for location {location_id!r} "
                    f"at density={density}, in_town={in_town}."
                )

        node_type: NodeType = node_rng.choice(sorted(eligible_types, key=lambda nt: nt.value))
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
