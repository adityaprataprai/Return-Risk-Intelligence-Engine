import sys
from pathlib import Path

# Ensure project root and src are in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

import polars as pl
import pytest

try:
    from src.features.registry import FeatureRegistry
    from src.features.validation import FeatureValidator
except ModuleNotFoundError:
    from features.registry import FeatureRegistry  # type: ignore
    from features.validation import FeatureValidator  # type: ignore


def test_feature_registry_loading():
    """Verify registry loads all 53 features with correct metadata."""
    registry = FeatureRegistry.load_from_yaml("config/features/registry.yaml")
    feature_names = registry.get_feature_names()
    assert len(feature_names) == 53
    assert "returns_24h" in feature_names
    assert "linked_accounts_1hop" in feature_names
    assert "is_first_purchase" in feature_names
    assert "estimated_return_loss" in feature_names

    # Check query helpers
    serial_feats = registry.get_by_fraud_mechanism("serial_return_abuse")
    assert len(serial_feats) >= 3


def test_feature_datasets_exist_and_valid():
    """Verify train, validation, and test parquets exist and pass schema validation."""
    registry = FeatureRegistry.load_from_yaml("config/features/registry.yaml")
    validator = FeatureValidator("config/features/registry.yaml")

    for split in ["train", "validation", "test"]:
        path = Path(f"data/features/{split}_features.parquet")
        assert path.exists(), f"Missing {path}"
        df = pl.read_parquet(path)
        assert len(df) > 0

        # Schema check
        schema_res = validator.check_schema(df)
        assert schema_res["passed"], f"Schema check failed on {split}: {schema_res['missing_features']}"

        # Range check
        range_res = validator.check_ranges(df)
        assert range_res["passed"], f"Range check failed on {split}: {range_res['violations']}"

        # Missingness check
        miss_res = validator.generate_missingness_report(df)
        assert miss_res["columns_with_missing_values"] == 0, f"Missing values in {split}: {miss_res['missingness']}"


def test_point_in_time_leakage_safety():
    """Verify that features obey strict point-in-time causality."""
    validator = FeatureValidator("config/features/registry.yaml")
    train_df = pl.read_parquet("data/features/train_features.parquet")
    leak_res = validator.check_point_in_time_leakage(train_df, raw_data_dir="data/raw", sample_size=50)
    assert leak_res["passed"], f"Point-in-time leakage detected: {leak_res['leakage_violations']}"


if __name__ == "__main__":
    test_feature_registry_loading()
    print("  [PASSED] test_feature_registry_loading")
    test_feature_datasets_exist_and_valid()
    print("  [PASSED] test_feature_datasets_exist_and_valid")
    test_point_in_time_leakage_safety()
    print("  [PASSED] test_point_in_time_leakage_safety")
    print("\nAll feature tests passed successfully!")
