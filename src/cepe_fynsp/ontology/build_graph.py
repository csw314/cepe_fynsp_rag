"""Build a lightweight ontology graph from curated FORMEX data."""

from __future__ import annotations

import networkx as nx
import pandas as pd


def build_formex_graph(df: pd.DataFrame) -> nx.MultiDiGraph:
    """Build a graph with funding lines connected to key analytic dimensions."""
    graph = nx.MultiDiGraph()
    for _, row in df.iterrows():
        line_id = str(row.get("source_row_id"))
        graph.add_node(line_id, node_type="FundingLine")
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
            node_id = f"{node_type}:{value}"
            graph.add_node(node_id, node_type=node_type, label=str(value))
            graph.add_edge(line_id, node_id, edge_type=edge)
    return graph
