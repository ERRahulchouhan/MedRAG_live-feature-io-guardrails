from __future__ import annotations

import argparse
import json

from src.core.service import RAGService

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAG toolkit CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Parse documents and build an index")
    index_parser.add_argument("--project", default="medrag")
    index_parser.add_argument("--skip-if-exists", action="store_true")

    query_parser = subparsers.add_parser("query", help="Query an existing index")
    query_parser.add_argument("question")
    query_parser.add_argument("--project", default="medrag")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    service = RAGService.from_project_name(args.project)

    if args.command == "index":
        if args.skip_if_exists and service.collection_ready():
            print(
                f"Collection '{service.config.collection_name}' already exists for "
                f"project '{args.project}'. Skipping reindex."
            )
            return
        count = service.build_index()
        print(f"Indexed {count} documents for project '{args.project}'.")
        return

    if args.command == "query":
        result = service.query(args.question)
        print(json.dumps(result.response.model_dump(), indent=2))
        return

    raise ValueError(f"Unsupported command: {args.command}")



if __name__ == "__main__":
    main()