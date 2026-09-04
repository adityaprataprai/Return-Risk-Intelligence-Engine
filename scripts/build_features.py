#!/usr/bin/env python3
"""Offline Feature Generation Script.

Builds point-in-time features from raw data, validates against schema,
runs leakage checks, and outputs partitioned train/validation/test feature datasets.
"""

import argparse
import io
from pathlib import Path
import sys
import time

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.features.offline_builder import OfflineFeatureBuilder
from src.features.validation import FeatureValidator


def main() -> None:
    parser = argparse.ArgumentParser(description="Build offline features for return risk engine")
    parser.add_argument("--raw-dir", type=str, default="data/raw", help="Path to raw parquet datasets")
    parser.add_argument("--gt-dir", type=str, default="data/ground_truth", help="Path to ground truth labels")
    parser.add_argument("--output-dir", type=str, default="data/features", help="Output directory for feature datasets")
    parser.add_argument("--registry", type=str, default="config/features/registry.yaml", help="Path to registry YAML")
    args = parser.parse_args()

    start_time = time.time()
    print("=" * 70)
    print("PHASE 2: OFFLINE FEATURE ENGINEERING")
    print("=" * 70)

    # 1. Initialize Builder & Build Features
    builder = OfflineFeatureBuilder(
        raw_data_dir=args.raw_dir,
        gt_data_dir=args.gt_dir,
        registry_path=args.registry,
    )
    features_df = builder.build_all_features()

    # 2. Validation
    print("\n--- Running Feature Validation Suite ---")
    validator = FeatureValidator(registry_path=args.registry)
    val_report = validator.run_all_validations(features_df, raw_data_dir=args.raw_dir)

    print(f"Schema Check: {'PASSED [✔]' if val_report['schema_check']['passed'] else 'FAILED [✘]'}")
    if not val_report['schema_check']['passed']:
        print(f"  Missing features: {val_report['schema_check']['missing_features']}")

    print(f"Range Check:  {'PASSED [✔]' if val_report['range_check']['passed'] else 'FAILED [✘]'}")
    if not val_report['range_check']['passed']:
        print(f"  Range violations: {val_report['range_check']['violations']}")

    print(f"Leakage Check: {'PASSED [✔]' if val_report['leakage_check']['passed'] else 'FAILED [✘]'}")
    if not val_report['leakage_check']['passed']:
        print(f"  Leakage violations: {val_report['leakage_check']['leakage_violations']}")

    missing_cols = val_report["missingness_report"]["columns_with_missing_values"]
    print(f"Missingness Check: {'PASSED (0 missing) [✔]' if missing_cols == 0 else f'WARNING ({missing_cols} cols have nulls) [!]'}")

    if not val_report["all_passed"]:
        print("\n[WARNING] Validation suite found discrepancies. Please review above logs.")
    else:
        print("\n[SUCCESS] All feature validation checks passed cleanly!")

    # 3. Partition and Save Datasets
    print("\n--- Partitioning & Saving Feature Parquets ---")
    saved_paths = builder.split_and_save(features_df, output_dir=args.output_dir)

    duration = time.time() - start_time
    print("=" * 70)
    print(f"Phase 2 Feature Engineering complete in {duration:.2f}s!")
    print(f"Output files:")
    for split, p in saved_paths.items():
        print(f"  - {split.upper()}: {p}")
    print("=" * 70)


if __name__ == "__main__":
    main()
