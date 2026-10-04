from __future__ import annotations

import argparse
import socket
import time

from src.core.projects import get_project_definition
from src.core.settings import get_settings

def wait_for_tcp(host: str, port: int, timeout: int, interval: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=5):
                return
        except OSError:
            time.sleep(interval)
    raise TimeoutError(f"Timed out waiting for {host}:{port}")



def wait_for_collection(project: str, timeout: int, interval: float = 2.0) -> None:
    from qdrant_client import QdrantClient

    settings = get_settings()
    config = get_project_definition(project).config
    deadline = time.time() + timeout
    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

    while time.time() < deadline:
        try:
            client.get_collection(config.collection_name)
            return
        except Exception:
            time.sleep(interval)
    raise TimeoutError(f"Timed out waiting for collection '{config.collection_name}'")



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Wait for external dependencies")
    subparsers = parser.add_subparsers(dest="target", required=True)

    tcp_parser = subparsers.add_parser("qdrant", help="Wait for a TCP host and port")
    tcp_parser.add_argument("--host", required=True)
    tcp_parser.add_argument("--port", type=int, required=True)
    tcp_parser.add_argument("--timeout", type=int, default=120)

    collection_parser = subparsers.add_parser("collection", help="Wait for a Qdrant collection")
    collection_parser.add_argument("--project", default="medrag")
    collection_parser.add_argument("--timeout", type=int, default=300)

    return parser




def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.target == "qdrant":
        wait_for_tcp(host=args.host, port=args.port, timeout=args.timeout)
        return

    if args.target == "collection":
        wait_for_collection(project=args.project, timeout=args.timeout)
        return

    raise ValueError(f"Unsupported wait target: {args.target}")


if __name__ == "__main__":
    main()

