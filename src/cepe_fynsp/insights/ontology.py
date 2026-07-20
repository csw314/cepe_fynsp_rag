"""Deterministic bounded ontology-subgraph resolution for visualization context."""

from __future__ import annotations

import hashlib
import json
from collections import deque
from pathlib import Path
from typing import Iterable

from cepe_fynsp.insights.schemas import (
    OntologyContext,
    OntologyEdgeContext,
    OntologyNodeContext,
    OntologyPathContext,
)


def _edge_id(source: str, relationship: str, target: str) -> str:
    value = json.dumps([source, relationship, target], separators=(",", ":"))
    return f"edge:{hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]}"


def _path_id(node_ids: tuple[str, ...], edge_ids: tuple[str, ...]) -> str:
    value = json.dumps([node_ids, edge_ids], separators=(",", ":"))
    return f"path:{hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]}"


def resolve_ontology_context(
    graph_path: Path,
    *,
    seed_node_ids: Iterable[str],
    seed_labels: Iterable[str] = (),
    max_depth: int = 2,
    max_nodes: int = 40,
    max_edges: int = 80,
    max_paths: int = 20,
) -> OntologyContext:
    """Load, validate, and traverse all relevant graph context within explicit limits."""
    if not graph_path.is_file():
        return OntologyContext(
            graph_id=None,
            nodes=(),
            edges=(),
            paths=(),
            truncated=False,
            unavailable_reason="The validated ontology graph artifact is unavailable.",
        )
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    raw_nodes = graph.get("nodes")
    raw_edges = graph.get("edges")
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        raise ValueError("Ontology graph requires node and edge arrays.")
    nodes: dict[str, OntologyNodeContext] = {}
    for raw in raw_nodes:
        node = OntologyNodeContext(
            id=str(raw["id"]),
            label=str(raw["label"]),
            node_type=str(raw["node_type"]),
        )
        if node.id in nodes:
            raise ValueError(f"Ontology graph contains a duplicate node ID: {node.id}")
        nodes[node.id] = node
    edges: dict[str, OntologyEdgeContext] = {}
    adjacency: dict[str, list[tuple[str, str]]] = {identifier: [] for identifier in nodes}
    for raw in raw_edges:
        source = str(raw["source"])
        target = str(raw["target"])
        relationship = str(raw.get("edge_type") or raw.get("relationship_type"))
        if source not in nodes or target not in nodes:
            raise ValueError("Ontology graph contains a dangling relationship.")
        identifier = _edge_id(source, relationship, target)
        edge = OntologyEdgeContext(
            id=identifier,
            source=source,
            target=target,
            relationship_type=relationship,
        )
        if identifier in edges and edges[identifier] != edge:
            raise ValueError(f"Ontology edge identifier collision: {identifier}")
        edges[identifier] = edge
        adjacency[source].append((identifier, target))
        adjacency[target].append((identifier, source))
    for neighbors in adjacency.values():
        neighbors.sort(key=lambda item: (item[0], item[1]))

    requested_labels = {value.casefold() for value in seed_labels if value.strip()}
    seeds = {identifier for identifier in seed_node_ids if identifier in nodes}
    seeds.update(
        identifier
        for identifier, node in nodes.items()
        if node.label.casefold() in requested_labels
    )
    if not seeds:
        return OntologyContext(
            graph_id=str(graph.get("graph_id")) if graph.get("graph_id") else None,
            nodes=(),
            edges=(),
            paths=(),
            truncated=False,
            unavailable_reason="No validated ontology seed matched this visualization context.",
        )

    selected_nodes: set[str] = set()
    selected_edges: set[str] = set()
    path_records: dict[str, OntologyPathContext] = {}
    queue: deque[tuple[str, int, tuple[str, ...], tuple[str, ...]]] = deque(
        (seed, 0, (seed,), ()) for seed in sorted(seeds)
    )
    best_depth: dict[str, int] = {}
    truncated = False
    while queue:
        current, depth, path_nodes, path_edges = queue.popleft()
        known_depth = best_depth.get(current)
        if known_depth is not None and known_depth < depth:
            continue
        best_depth[current] = depth
        if current not in selected_nodes and len(selected_nodes) >= max_nodes:
            truncated = True
            continue
        selected_nodes.add(current)
        if path_edges and len(path_records) < max_paths:
            identifier = _path_id(path_nodes, path_edges)
            path_records.setdefault(
                identifier,
                OntologyPathContext(
                    id=identifier,
                    node_ids=path_nodes,
                    edge_ids=path_edges,
                ),
            )
        elif path_edges:
            truncated = True
        if depth >= max_depth:
            if adjacency[current]:
                truncated = True
            continue
        for edge_identifier, neighbor in adjacency[current]:
            if neighbor in path_nodes:
                continue
            if len(selected_edges) >= max_edges and edge_identifier not in selected_edges:
                truncated = True
                continue
            selected_edges.add(edge_identifier)
            queue.append(
                (neighbor, depth + 1, (*path_nodes, neighbor), (*path_edges, edge_identifier))
            )
    included_edges = tuple(
        edges[identifier]
        for identifier in sorted(selected_edges)
        if edges[identifier].source in selected_nodes and edges[identifier].target in selected_nodes
    )
    return OntologyContext(
        graph_id=str(graph.get("graph_id")) if graph.get("graph_id") else None,
        nodes=tuple(nodes[identifier] for identifier in sorted(selected_nodes)),
        edges=included_edges,
        paths=tuple(path_records[identifier] for identifier in sorted(path_records)),
        truncated=truncated,
    )
