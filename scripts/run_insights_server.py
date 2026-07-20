"""Serve static dashboards and the secure same-origin Get Insights API."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from cepe_fynsp.insights.http_server import create_insights_server


def main() -> None:
    """Start the loopback-bound service until interrupted."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--allowed-host",
        action="append",
        default=[],
        help="Additional reverse-proxy Host name; repeat only for approved deployment hosts.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    server = create_insights_server(
        args.project_root,
        host=args.host,
        port=args.port,
        allowed_hosts=tuple(args.allowed_host),
    )
    print(f"Serving dashboards and secure insights on http://{args.host}:{server.server_port}/web/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
