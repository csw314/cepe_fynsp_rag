"""Build a lightweight ontology graph from curated FORMEX data."""

from __future__ import annotations

import hashlib
import re

import networkx as nx
import pandas as pd


def stable_node_id(node_type: str, value: str) -> str:
    """Return a readable node identifier with a collision-resistant suffix."""
    normalized = re.sub(r"\s+", " ", value.strip())
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-") or "unspecified"
    suffix = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:10]
    return f"{node_type.casefold()}:{slug}:{suffix}"


def build_formex_graph(df: pd.DataFrame) -> nx.MultiDiGraph[str]:
    """Build a graph with funding lines connected to key analytic dimensions."""
    graph: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    for _, row in df.iterrows():
        line_value = row.get("source_record_id", row.get("source_row_id"))
        line_id = stable_node_id("FundingLine", str(line_value))
        graph.add_node(line_id, node_type="FundingLine", label=str(line_value))
        for col, node_type, edge in [
            ("scenario", "Scenario", "belongs_to"),
            ("submission_type", "SubmissionType", "represented_by"),
            ("fiscal_year", "FiscalYear", "has_fiscal_year"),
            ("funding_levels", "FundingLevel", "has_funding_level"),
            ("nnsa_appropriation", "Appropriation", "funded_by"),
            ("sub_office_number", "Organization", "owned_by"),
            ("site_planex", "Site", "split_to_site"),
            ("program_int_area", "IntegrationArea", "tagged_to"),
            ("process_imp_area", "ProcessImprovementArea", "tagged_to"),
            ("program_request", "ProgramRequest", "describes"),
            ("acquisition_id", "Acquisition", "supports_acquisition"),
            ("wbs", "WBS", "coded_to"),
        ]:
            value = row.get(col)
            if pd.isna(value) or str(value).strip() == "":
                continue
            identifier = stable_node_id(node_type, str(value))
            graph.add_node(identifier, node_type=node_type, label=str(value))
            graph.add_edge(line_id, identifier, edge_type=edge)
    return graph


def validate_graph_references(graph: nx.MultiDiGraph[str]) -> None:
    """Raise when an exported edge references a missing node."""
    nodes = set(graph.nodes)
    dangling = [
        (source, target)
        for source, target, _ in graph.edges(keys=True)
        if source not in nodes or target not in nodes
    ]
    if dangling:
        raise ValueError(f"Graph contains dangling references: {dangling[:3]}")
