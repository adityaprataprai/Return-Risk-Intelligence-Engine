#!/usr/bin/env python3
"""Phase 5: Graph Processor Worker Script.

Ingests entity relationship edges, computes multi-hop connectivity metrics,
and materializes graph states into Redis under risk:user:{user_id}:graph:v2.

Usage:
    python scripts/run_graph_processor.py
"""

import argparse
import io
import sys
import time
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass
if sys.stderr.encoding != "utf-8":
    try:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.features.graph_processor import GraphProcessor
from src.inference.redis_client import RedisClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Process identity graph relationships and materialize to Redis")
    parser.add_argument("--rels-path", type=str, default="data/raw/relationships.parquet", help="Path to relationships.parquet")
    parser.add_argument("--returns-path", type=str, default="data/raw/returns.parquet", help="Path to returns.parquet")
    parser.add_argument("--graph-version", type=str, default="g0000", help="Graph snapshot partition version")
    parser.add_argument("--daemon", action="store_true", help="Run continuously as background daemon")
    parser.add_argument("--interval", type=float, default=60.0, help="Interval in seconds between refreshes in daemon mode")
    args = parser.parse_args()

    print("=" * 65)
    print("PHASE 5: ASYNCHRONOUS GRAPH PROCESSOR WORKER")
    print("=" * 65)

    redis = RedisClient()
    health = redis.health_check()
    print(f"Redis Backend: {health['backend']} | Host: {health['host']}:{health['port']}")

    processor = GraphProcessor(redis_client=redis, graph_version=args.graph_version)

    def run_once():
        start_time = time.time()
        print(f"\nLoading relationships from {args.rels_path}...")
        processor.load_from_parquet(
            relationships_path=args.rels_path,
            returns_path=args.returns_path,
        )
        print(f"  Indexed {len(processor.user_entities)} users and {len(processor.entity_users)} shared entities.")

        print("\nMaterializing graph features to Redis under risk:user:{user_id}:graph:v2...")
        total_materialized = processor.materialize_to_redis()

        duration = time.time() - start_time
        print(f"  Successfully materialized {total_materialized} user graph keys in {duration:.2f}s!")
        return total_materialized

    run_once()

    if args.daemon:
        print(f"\nGraph processor entering daemon loop (interval={args.interval}s)...")
        try:
            while True:
                time.sleep(args.interval)
                print(f"\n[Daemon] Refreshing identity graph materialization at {time.strftime('%Y-%m-%d %H:%M:%S')}...")
                run_once()
        except KeyboardInterrupt:
            print("\nGraph processor daemon stopped by user.")
    print("=" * 65)


if __name__ == "__main__":
    main()
