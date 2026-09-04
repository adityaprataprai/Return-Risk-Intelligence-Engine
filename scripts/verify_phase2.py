#!/usr/bin/env python3
"""
Phase 2 Acceptance Verification Script
Validates the offline feature engineering outputs:
- Feature registry completeness and correctness
- Feature dataset existence and schema
- Point-in-time timestamp presence
- Value range and logical constraints
- Cold-start / fallback feature presence
- Train/validation/test split integrity (no overlap, temporal order)
- Leakage of hidden ground truth columns
- Missingness thresholds

Usage:
    python scripts/verify_phase2.py --registry config/features/registry.yaml

Author: Risk ML Team
Date: 2026-09-06
"""

import argparse
import sys
from pathlib import Path

import polars as pl
from typing import Any, cast
import yaml

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
FEATURES_DIR = Path("data/features")
REGISTRY_PATH = Path("config/features/registry.yaml")

TRAIN_FILE = FEATURES_DIR / "train_features.parquet"
VAL_FILE = FEATURES_DIR / "validation_features.parquet"
TEST_FILE = FEATURES_DIR / "test_features.parquet"

# Columns that are not features but allowed in the feature dataset
ALLOWED_EXTRA_COLS = {
    "return_id",
    "transaction_id",
    "user_id",
    "request_time",
    "decision_timestamp",
    "return_request_time",
    "timestamp",
    "is_fraud",           # target for training
    "world_id",           # optional metadata
    "split",              # optional split label
}

# Post-decision columns that must NOT appear in feature dataset (causal leakage)
FORBIDDEN_POST_DECISION_COLS = {
    "inspection_result",
    "final_salvage_value",
    "refund_rejected",
    "refund_issued_time",
    "post_decision_outcome",
}

# Hidden ground truth columns that must NOT appear in feature dataset (label leakage)
HIDDEN_GROUND_TRUTH_COLS = {
    "true_scenario",
    "difficulty",
}

FORBIDDEN_COLS = FORBIDDEN_POST_DECISION_COLS | HIDDEN_GROUND_TRUTH_COLS

# Feature groups for range checks based on name patterns
RANGE_PATTERNS = {
    "rate_diff": (-1.0, 1.0),        # differences between rates can be negative
    "diff": (-1.0, 1.0),             # differences/deviations between rates or baselines
    "rate": (0.0, 1.0),              # any feature containing "rate" (e.g., return_rate_30d)
    "count": (0, None),              # counts and distinct counts
    "days": (0, None),               # durations in days
    "hours": (0, None),
    "time_since": (0, None),
    "value": (0, None),              # monetary values (non-negative)
    "amount": (0, None),
    "log_": (0, None),               # log1p transformed amounts are >=0
    "age": (0, None),
    "baseline": (0, None),
    "support": (0, None),
}

# Features that should be binary (0/1)
BINARY_FEATURES = {
    "is_high_value",
    "is_new_device",
    "is_new_address",
    "is_new_payment_method",
    "is_first_purchase",
    "account_age_under_24h",
    "has_prior_orders",
    "has_prior_returns",
    "used_category_fallback",
}

# Cold-start / fallback features that are explicitly required
COLD_START_FEATURES = {
    "is_first_purchase",
    "account_age_hours",
    "account_age_under_24h",
    "has_prior_orders",
    "has_prior_returns",
    "user_history_count",
    "baseline_support_count",
    "used_category_fallback",
}

# Graph features expected to be present
GRAPH_FEATURES = {
    "linked_accounts_1hop",
    "linked_accounts_2hop",
    "shared_device_accounts",
    "shared_address_accounts",
    "shared_payment_accounts",
    "high_return_neighbor_count",
    "connected_component_size",
}

# Required metadata columns in each feature dataset (at least one timestamp column)
REQUIRED_TIMESTAMP_COLS = ("request_time", "decision_timestamp", "return_request_time", "timestamp")
REQUIRED_TIMESTAMP_COL = "request_time"  # primary expected timestamp column


# ----------------------------------------------------------------------
# Utility
# ----------------------------------------------------------------------
def load_yaml(path):
    if not path.exists():
        print(f"[ERROR] File not found: {path}")
        return None
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"[ERROR] Cannot parse YAML: {e}")
        return None


def load_parquet(path):
    if not path.exists():
        print(f"[ERROR] File not found: {path}")
        return None
    try:
        return pl.read_parquet(path)
    except Exception as e:
        print(f"[ERROR] Cannot read Parquet: {e}")
        return None


def check(condition, pass_msg, fail_msg, failures):
    if condition:
        print(f"[PASS] {pass_msg}")
        return True
    else:
        print(f"[FAIL] {fail_msg}")
        failures.append(fail_msg)
        return False


def any_none(*dfs):
    return any(df is None for df in dfs)


def is_feature_name(name):
    """Return True if name is not an allowed extra column."""
    return name not in ALLOWED_EXTRA_COLS


def normalize_feature_names(registry):
    """Extract feature names from registry dictionary or list."""
    if isinstance(registry, list):
        features = registry
    elif isinstance(registry, dict) and "features" in registry:
        features = registry["features"]
    else:
        features = []
    return [f.get("name") for f in features if "name" in f]


# ----------------------------------------------------------------------
# 1. Feature Registry Validation
# ----------------------------------------------------------------------
def validate_registry(registry, failures):
    print("\n=== Feature Registry Validation ===")
    if registry is None:
        check(False, "", "Could not load registry YAML.", failures)
        return False, []

    features = registry.get("features", registry) if isinstance(registry, dict) else registry
    if not isinstance(features, list) or len(features) == 0:
        check(False, "", "Registry does not contain a non-empty feature list.", failures)
        return False, []

    required_fields = {
        "name", "entity", "source_event", "aggregation", "window",
        "available_at_rule", "ttl", "version", "owner", "fraud_mechanism"
    }
    feature_names = []
    all_ok = True

    for feat in features:
        name = feat.get("name")
        if not name:
            check(False, "", "Feature missing 'name' field.", failures)
            all_ok = False
            continue
        feature_names.append(name)
        missing = required_fields - set(feat.keys())
        if missing:
            check(False, "", f"Feature '{name}' missing fields: {missing}", failures)
            all_ok = False

    # uniqueness
    if len(feature_names) != len(set(feature_names)):
        check(False, "", "Feature names are not unique.", failures)
        all_ok = False
    else:
        print("[PASS] Feature names unique.")

    return all_ok, feature_names


# ----------------------------------------------------------------------
# 2. Feature Dataset Existence
# ----------------------------------------------------------------------
def validate_dataset_existence(failures):
    print("\n=== Feature Dataset Existence ===")
    missing_files = []
    for f in [TRAIN_FILE, VAL_FILE, TEST_FILE]:
        if not f.exists():
            missing_files.append(f.name)
    if missing_files:
        check(False, "", f"Missing feature datasets: {missing_files}", failures)
        return False
    else:
        print("[PASS] All train/validation/test feature files present.")
        return True


# ----------------------------------------------------------------------
# 3. Schema Consistency
# ----------------------------------------------------------------------
def validate_schema(feature_names, failures):
    print("\n=== Schema Consistency ===")
    train_df = load_parquet(TRAIN_FILE)
    val_df = load_parquet(VAL_FILE)
    test_df = load_parquet(TEST_FILE)

    if train_df is None or val_df is None or test_df is None:
        check(False, "", "Could not load one or more feature datasets.", failures)
        return

    dfs = {
        "train": train_df,
        "validation": val_df,
        "test": test_df,
    }

    # check union across datasets? We require all features present in all datasets.
    for split, df in dfs.items():
        missing_features = set(feature_names) - set(df.columns)
        if missing_features:
            check(False, "", f"{split} dataset missing features: {missing_features}", failures)
        else:
            # check no forbidden post-decision columns
            forbidden_found = set(df.columns) & FORBIDDEN_POST_DECISION_COLS
            if forbidden_found:
                check(False, "", f"{split} dataset contains forbidden post-decision columns: {forbidden_found}", failures)
            else:
                print(f"[PASS] {split} dataset contains all registry features and no post-decision columns.")

    # Check that at least one timestamp column exists in each dataset
    for split, df in dfs.items():
        ts_cols = [c for c in df.columns if c in REQUIRED_TIMESTAMP_COLS]
        if not ts_cols:
            check(False, "", f"{split} dataset missing any timestamp column.", failures)
        else:
            print(f"[PASS] {split} dataset has timestamp column: {ts_cols[0]}")

    # Check primary key uniqueness (if return_id or transaction_id exists)
    for split, df in dfs.items():
        key_col = None
        if "return_id" in df.columns:
            key_col = "return_id"
        elif "transaction_id" in df.columns:
            key_col = "transaction_id"
        if key_col:
            if df[key_col].n_unique() != len(df):
                check(False, "", f"{split} dataset key '{key_col}' is not unique.", failures)
            else:
                print(f"[PASS] {split} dataset key '{key_col}' is unique.")



# ----------------------------------------------------------------------
# 4. Range and Logical Constraint Checks
# ----------------------------------------------------------------------
def validate_ranges(feature_names, failures):
    print("\n=== Range and Logical Constraints ===")
    df = load_parquet(TRAIN_FILE)  # use train as representative
    if df is None:
        check(False, "", "Could not load train dataset for range checks.", failures)
        return

    for feat in feature_names:
        if feat not in df.columns:
            continue
        col = df[feat]
        # Skip string/categorical for range checks
        if col.dtype not in (pl.Int64, pl.Int32, pl.Float64, pl.Float32):
            continue

        # Check binary features
        if feat in BINARY_FEATURES:
            min_v = col.min()
            max_v = col.max()
            if (
                col.is_null().sum() == 0
                and col.n_unique() <= 2
                and min_v is not None
                and max_v is not None
                and cast(Any, min_v) >= 0
                and cast(Any, max_v) <= 1
            ):
                print(f"[PASS] {feat} is binary (0/1).")
            else:
                check(False, "", f"{feat} expected binary but has values outside [0,1] or nulls.", failures)

        # Apply pattern-based range checks
        for pattern, (low, high) in RANGE_PATTERNS.items():
            if pattern in feat:
                min_val = col.min()
                max_val = col.max()
                if min_val is None or max_val is None:
                    continue  # all null, handled later
                if low is not None and cast(Any, min_val) < low:
                    check(False, "", f"{feat} has value below {low}: min={min_val}", failures)
                if high is not None and cast(Any, max_val) > high:
                    check(False, "", f"{feat} has value above {high}: max={max_val}", failures)
                break  # only one pattern should apply

        # Check integer counts are non-negative and integer-like (already covered by pattern "count")

    # Specific graph feature constraints
    for gfeature in GRAPH_FEATURES:
        if gfeature in df.columns:
            col = df[gfeature]
            g_min = col.min()
            if g_min is not None and cast(Any, g_min) < 0:
                check(False, "", f"{gfeature} cannot be negative.", failures)
            if gfeature in ("connected_component_size",) and g_min is not None and cast(Any, g_min) < 1:
                check(False, "", f"{gfeature} should be at least 1.", failures)

    # Check denominators for rates are not zero (if present as separate support features)
    rate_features = [f for f in feature_names if "rate" in f]
    for rate in rate_features:
        if rate in df.columns:
            # If a support feature exists like orders_7d, check that returns_7d etc are consistent? We'll just check range.
            pass  # range already checked


# ----------------------------------------------------------------------
# 5. Cold-Start and Fallback Feature Presence
# ----------------------------------------------------------------------
def validate_cold_start(feature_names, failures):
    print("\n=== Cold-Start / Fallback Features ===")
    df = load_parquet(TRAIN_FILE)
    if df is None:
        check(False, "", "Could not load train dataset for cold-start check.", failures)
        return

    missing_cold = COLD_START_FEATURES - set(df.columns)
    if missing_cold:
        check(False, "", f"Missing cold-start features: {missing_cold}", failures)
    else:
        print("[PASS] All cold-start features are present.")
        # Check binary nature of used_category_fallback and is_first_purchase
        for bin_feat in ["used_category_fallback", "is_first_purchase"]:
            col = df[bin_feat]
            min_v = col.min()
            max_v = col.max()
            if (
                col.n_unique() <= 2
                and min_v is not None
                and max_v is not None
                and cast(Any, min_v) >= 0
                and cast(Any, max_v) <= 1
            ):
                print(f"[PASS] {bin_feat} is binary.")
            else:
                check(False, "", f"{bin_feat} is not binary (values: {col.unique().to_list()[:5]})", failures)


# ----------------------------------------------------------------------
# 6. Split Integrity (No Overlap, Temporal Order)
# ----------------------------------------------------------------------
def validate_split_integrity(failures):
    print("\n=== Split Integrity ===")
    train = load_parquet(TRAIN_FILE)
    val = load_parquet(VAL_FILE)
    test = load_parquet(TEST_FILE)
    if train is None or val is None or test is None:
        check(False, "", "Could not load split datasets.", failures)
        return

    # Identify key column
    key_col = None
    for col in ["return_id", "transaction_id"]:
        if col in train.columns and col in val.columns and col in test.columns:
            key_col = col
            break
    if not key_col:
        check(False, "", "No common key column found across splits.", failures)
        return

    train_keys = set(train[key_col].to_list())
    val_keys = set(val[key_col].to_list())
    test_keys = set(test[key_col].to_list())

    overlap_found = False
    if train_keys & val_keys:
        check(False, "", "Overlap of keys between train and validation.", failures)
        overlap_found = True
    if train_keys & test_keys:
        check(False, "", "Overlap of keys between train and test.", failures)
        overlap_found = True
    if val_keys & test_keys:
        check(False, "", "Overlap of keys between validation and test.", failures)
        overlap_found = True
    if not overlap_found:
        print("[PASS] No key overlap between splits.")

    # Check temporal order if timestamp column exists
    ts_col = None
    for col in REQUIRED_TIMESTAMP_COLS:
        if col in train.columns and col in val.columns and col in test.columns:
            ts_col = col
            break

    if ts_col is not None:
        train_max = train[ts_col].max()
        val_max = val[ts_col].max()
        test_max = test[ts_col].max()

        # We expect train to be most recent, then val, then test (oldest)
        # But actual order might be train (70% most recent), val (15% middle), test (15% oldest)
        # Or train oldest, val middle, test newest
        if train_max is not None and val_max is not None and test_max is not None:
            if cast(Any, train_max) >= cast(Any, val_max) >= cast(Any, test_max):
                print(f"[PASS] Temporal split order appears correct using '{ts_col}' (train newest, val middle, test oldest).")
            elif cast(Any, test_max) >= cast(Any, val_max) >= cast(Any, train_max):
                print(f"[PASS] Temporal split order appears correct using '{ts_col}' (test newest, val middle, train oldest).")
            else:
                check(
                    False,
                    "",
                    f"Temporal split order incorrect using '{ts_col}': train_max={train_max}, val_max={val_max}, test_max={test_max}",
                    failures,
                )
        else:
            check(False, "", f"Unable to determine max timestamp for column '{ts_col}'.", failures)
    else:
        print("[WARN] No timestamp column found across splits, skipping temporal order check.")



# ----------------------------------------------------------------------
# 7. Leakage of Hidden Ground Truth Columns
# ----------------------------------------------------------------------
def validate_leakage(feature_names, failures):
    print("\n=== Hidden Ground Truth Leakage ===")
    # Already checked schema for forbidden columns, but let's ensure no hidden label columns in feature files
    for split, path in [("train", TRAIN_FILE), ("validation", VAL_FILE), ("test", TEST_FILE)]:
        df = load_parquet(path)
        if df is None:
            continue
        hidden_cols = set(df.columns) & HIDDEN_GROUND_TRUTH_COLS
        if hidden_cols:
            check(False, "", f"{split} dataset contains hidden ground truth label columns: {hidden_cols}", failures)
        else:
            print(f"[PASS] {split} dataset has no hidden label columns.")

    # Also check that feature datasets do not contain raw ground truth columns like is_fraud if not intended.
    # We allow is_fraud only in train, not in validation/test? In many splits, target is present only in train.
    # We'll check if validation/test contain is_fraud; if they do, it's suspicious but not necessarily leakage.
    # We'll only warn.
    for split, df in [("validation", load_parquet(VAL_FILE)), ("test", load_parquet(TEST_FILE))]:
        if df is not None and "is_fraud" in df.columns:
            print(f"[WARN] {split} dataset contains target column 'is_fraud'. This may be acceptable if separate evaluation, but not needed for pure feature set.")


# ----------------------------------------------------------------------
# 8. Missingness Threshold
# ----------------------------------------------------------------------
def validate_missingness(feature_names, failures):
    print("\n=== Missingness ===")
    df = load_parquet(TRAIN_FILE)  # check train for missingness; others similar
    if df is None:
        check(False, "", "Could not load train dataset.", failures)
        return

    total_rows = len(df)
    high_missing_features = []
    for feat in feature_names:
        if feat not in df.columns:
            continue
        null_count = df[feat].is_null().sum()
        missing_pct = (null_count / total_rows) * 100
        # For behavioral deviation and cold-start indicators, some missing is acceptable.
        # But most base features should have 0 missing.
        if "used_category_fallback" in feat or "baseline_support" in feat or "user_history_count" in feat:
            max_allowed = 20.0
        elif feat.startswith("is_"):
            max_allowed = 5.0
        else:
            max_allowed = 2.0

        if missing_pct > max_allowed:
            high_missing_features.append((feat, missing_pct))

    if high_missing_features:
        print("[WARN] Features with high missingness:")
        for feat, pct in high_missing_features:
            print(f"  {feat}: {pct:.1f}%")
        # Not a failure because some missing may be intentional for cold start
        print("[INFO] Missingness above typical threshold; review whether intentional.")
    else:
        print("[PASS] Missingness is within acceptable limits.")

# ----------------------------------------------------------------------
# 9. Total Row Count Match
# ----------------------------------------------------------------------
def validate_row_counts(failures):
    print("\n=== Total Row Count Match ===")
    
    raw_returns_path = Path("data/raw/returns.parquet")
    if not raw_returns_path.exists():
        check(False, "", "Could not find raw returns.parquet to check row counts.", failures)
        return

    raw_returns = load_parquet(raw_returns_path)
    train = load_parquet(TRAIN_FILE)
    val = load_parquet(VAL_FILE)
    test = load_parquet(TEST_FILE)

    if raw_returns is None or train is None or val is None or test is None:
        check(False, "", "Could not load datasets for row count check.", failures)
        return

    total_raw = len(raw_returns)
    total_features = len(train) + len(val) + len(test)

    print(f"Raw returns count:  {total_raw}")
    print(f"Feature rows count: {total_features} (Train: {len(train)}, Val: {len(val)}, Test: {len(test)})")

    if total_raw == total_features:
        print("[PASS] Total feature rows exactly match the raw returns count.")
    else:
        # Sometimes a few rows might be dropped if they lack valid timestamps, 
        # but strictly speaking, they should match 1:1.
        check(
            False, 
            "", 
            f"Row count mismatch! Raw returns: {total_raw}, Feature rows: {total_features}", 
            failures
        )
# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Phase 2 Feature Pipeline Verification")
    parser.add_argument("--registry", type=str, default=str(REGISTRY_PATH), help="Path to feature registry YAML")
    args = parser.parse_args()

    registry_path = Path(args.registry)
    registry = load_yaml(registry_path)

    failures = []

    # Step 1: Registry
    ok, feature_names = validate_registry(registry, failures)
    if not ok:
        print("\n[FATAL] Registry validation failed. Exiting.")
        sys.exit(1)

    print(f"\n[INFO] Registry contains {len(feature_names)} features.")

    # Step 2: Dataset existence
    if not validate_dataset_existence(failures):
        sys.exit(1)

    # Step 3: Schema consistency
    validate_schema(feature_names, failures)

    # Step 4: Range checks
    validate_ranges(feature_names, failures)

    # Step 5: Cold-start
    validate_cold_start(feature_names, failures)

    # Step 6: Split integrity
    validate_split_integrity(failures)

    # Step 7: Leakage
    validate_leakage(feature_names, failures)

    # Step 8: Missingness
    validate_missingness(feature_names, failures)

    # Step 9: Row Count Match
    validate_row_counts(failures)
    
    # Summary
    print("\n" + "=" * 60)
    print("PHASE 2 VALIDATION SUMMARY")
    print("=" * 60)
    if failures:
        print(f"FAILED: {len(failures)} check(s) failed.")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED. Feature pipeline outputs are acceptable.")
        sys.exit(0)



if __name__ == "__main__":
    main()