#!/usr/bin/env python3
"""Phase 5: Event Replayer Script.

Reads historical event logs, orders, and returns from Parquet files and replays them
through the OnlineFeatureBuilder to populate real-time feature states in Redis.

Usage:
    python scripts/replay_events.py --max-events 50000
"""

import argparse
import io
import sys
import time
from pathlib import Path
import polars as pl

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

from src.features.online_builder import OnlineFeatureBuilder
from src.inference.redis_client import RedisClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay events to populate online Redis feature store")
    parser.add_argument("--raw-dir", type=str, default="data/raw", help="Directory containing raw parquets")
    parser.add_argument("--max-orders", type=int, default=None, help="Maximum orders to replay (default all)")
    parser.add_argument("--max-returns", type=int, default=None, help="Maximum returns to replay (default all)")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    start_time = time.time()
    print("=" * 65)
    print("PHASE 5: EVENT REPLAYER FOR REDIS ONLINE FEATURE STATE")
    print("=" * 65)

    redis = RedisClient()
    health = redis.health_check()
    print(f"Redis Backend: {health['backend']} | Host: {health['host']}:{health['port']}")

    builder = OnlineFeatureBuilder(redis_client=redis)

    # 1. Populate Economic Profiles
    print("\n--- 1. Populating Economic Profiles into Redis ---")
    builder.populate_economics()
    print("  Merchant and product category profiles stored in Redis.")

    # 2. Replay Account Creation Events
    events_path = raw_dir / "events.parquet"
    if events_path.exists():
        print("\n--- 2. Ingesting Account Creations ---")
        df_events = pl.read_parquet(events_path)
        acct_events = df_events.filter(pl.col("event_type") == "ACCOUNT_CREATED")
        for row in acct_events.iter_rows(named=True):
            builder.record_account_created(user_id=row["actor_id"], timestamp=row["timestamp"])
        print(f"  Processed {len(acct_events)} user account creation events.")

    # 3. Replay Orders
    orders_path = raw_dir / "orders.parquet"
    if orders_path.exists():
        print("\n--- 3. Ingesting Orders ---")
        df_orders = pl.read_parquet(orders_path).sort("timestamp")
        if args.max_orders:
            df_orders = df_orders.head(args.max_orders)

        # Products map for categories
        prod_map = {}
        prod_path = raw_dir / "products.parquet"
        if prod_path.exists():
            df_prod = pl.read_parquet(prod_path)
            for p in df_prod.iter_rows(named=True):
                prod_map[p["product_id"]] = p.get("category", "default")

        for row in df_orders.iter_rows(named=True):
            cat = prod_map.get(row.get("product_id"), "default")
            builder.record_order(
                user_id=row["user_id"],
                timestamp=row["timestamp"],
                price=float(row["price"]),
                category=cat,
                device_id=row.get("device_id"),
                address_id=row.get("address_id"),
                payment_id=row.get("payment_id"),
            )
        print(f"  Processed {len(df_orders)} order purchase events.")

    # 4. Replay Returns
    returns_path = raw_dir / "returns.parquet"
    if returns_path.exists():
        print("\n--- 4. Ingesting Returns ---")
        df_rets = pl.read_parquet(returns_path).sort("request_time")
        if args.max_returns:
            df_rets = df_rets.head(args.max_returns)

        # Map orders to get metadata for returns
        order_dict = {}
        if orders_path.exists():
            for row in pl.read_parquet(orders_path).iter_rows(named=True):
                order_dict[row["transaction_id"]] = row

        for row in df_rets.iter_rows(named=True):
            txn_id = row["transaction_id"]
            o_info = order_dict.get(txn_id, {})
            u_id = o_info.get("user_id")
            if not u_id:
                continue

            builder.record_return(
                user_id=u_id,
                timestamp=row["request_time"],
                refund_amount=float(row["refund_amount"]),
                days_to_return=float(row.get("days_to_return", 1.0)),
                category=prod_map.get(o_info.get("product_id"), "default"),
                device_id=o_info.get("device_id"),
                address_id=o_info.get("address_id"),
                payment_id=o_info.get("payment_id"),
            )
        print(f"  Processed {len(df_rets)} return request events.")

    # 5. Flush to Redis
    print("\n--- 5. Materializing Feature Keys into Redis ---")
    keys_written = builder.flush_to_redis()
    duration = time.time() - start_time
    print(f"  Successfully wrote {keys_written} keys to Redis in {duration:.2f}s!")
    print("=" * 65)


if __name__ == "__main__":
    main()
