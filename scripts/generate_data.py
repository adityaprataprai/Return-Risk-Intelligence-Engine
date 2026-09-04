"""CLI script for running synthetic data generation."""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.common.config import Config
from src.simulation.generator import SimulationGenerator


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate synthetic e-commerce data and fraud scenarios for Return-Risk Intelligence Engine."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="simulation/world_a",
        help="Configuration name or path (e.g. simulation/world_a)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data",
        help="Output root directory for generated datasets",
    )
    return parser.parse_args()


def validate_generated_data(output_dir: str):
    """Validates referential integrity and event temporal sequence."""
    import polars as pl

    raw_dir = Path(output_dir) / "raw"
    gt_dir = Path(output_dir) / "ground_truth"

    print("\nValidating generated datasets...")
    orders_df = pl.read_parquet(raw_dir / "orders.parquet")
    returns_df = pl.read_parquet(raw_dir / "returns.parquet")
    events_df = pl.read_parquet(raw_dir / "events.parquet")
    hidden_df = pl.read_parquet(gt_dir / "hidden_labels.parquet")

    # 1. Referential integrity: returns transaction_id exists in orders
    order_ids = set(orders_df["transaction_id"].to_list())
    ret_txn_ids = set(returns_df["transaction_id"].to_list())
    missing_txns = ret_txn_ids - order_ids
    assert len(missing_txns) == 0, f"Found {len(missing_txns)} returns without matching orders"
    print("  [OK] Referential integrity: all returns link to valid orders.")

    # 2. Hidden labels match returns 1-to-1
    assert len(returns_df) == len(hidden_df), "Mismatch between returns and hidden labels row count"
    print("  [OK] Hidden ground truth matches returns 1-to-1.")

    # 3. Temporal consistency: events are chronologically sorted
    ts_list = events_df["timestamp"].to_list()
    assert ts_list == sorted(ts_list), "Events are not sorted chronologically"
    print("  [OK] Event stream is strictly sorted chronologically.")

    print("\n[SUCCESS] All data validation checks passed.")


def main():
    args = parse_args()
    print(f"Loading configuration from '{args.config}'...")
    cfg = Config(args.config)
    generator = SimulationGenerator(cfg.to_dict())

    print("\nGenerating population entities...")
    generator.generate_entities()

    print("\nSimulating transactions and fraud scenarios...")
    generator.simulate_traffic()

    print("\nExporting datasets...")
    stats = generator.export_data(output_dir=args.output_dir)

    validate_generated_data(output_dir=args.output_dir)


if __name__ == "__main__":
    main()
