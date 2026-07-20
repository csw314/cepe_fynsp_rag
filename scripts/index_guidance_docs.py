"""Build the approval-gated local guidance chunk index."""

from __future__ import annotations

import argparse
from pathlib import Path

from cepe_fynsp.insights.documents import index_approved_documents


def main() -> None:
    """Index only documents explicitly approved in the configured manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--approval-manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    chunks = index_approved_documents(
        args.project_root,
        approval_manifest=args.approval_manifest,
        output_path=args.output,
    )
    print(f"Indexed {len(chunks)} approved guidance chunks.")


if __name__ == "__main__":
    main()
