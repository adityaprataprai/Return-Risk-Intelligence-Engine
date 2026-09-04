#!/usr/bin/env python3
"""Phase 3 Acceptance Verification Script.

Validates the trained and calibrated ML models against acceptance criteria:
- Registry artifacts presence and completeness
- Model and calibrator loadability and inference verification
- Test AUPRC > 0.50
- Test Brier score < 0.25
- Detection for all three fraud families (scenario-wise recall > 0)
- Reliability calibration curve artifact existence
- Feature schema and version integrity

Usage:
    python scripts/verify_phase3.py --version 1.0.0
"""

import argparse
import io
import json
from pathlib import Path
import sys
import numpy as np
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

from src.models.evaluate import ModelEvaluator
from src.models.registry import ModelRegistry


def check(condition: bool, pass_msg: str, fail_msg: str, failures: list) -> bool:
    if condition:
        print(f"[PASS] {pass_msg}")
        return True
    else:
        print(f"[FAIL] {fail_msg}")
        failures.append(fail_msg)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 3 Model Acceptance Verification")
    parser.add_argument("--registry-dir", type=str, default="model_registry", help="Model registry root")
    parser.add_argument("--model-name", type=str, default="return-risk", help="Model name")
    parser.add_argument("--version", type=str, default="1.0.0", help="Model version")
    parser.add_argument("--test-features", type=str, default="data/features/test_features.parquet", help="Test features")
    parser.add_argument("--gt-labels", type=str, default="data/ground_truth/hidden_labels.parquet", help="Ground truth labels")
    args = parser.parse_args()

    failures = []
    print("=" * 60)
    print("PHASE 3 ACCEPTANCE VERIFICATION")
    print(f"Model: {args.model_name} | Version: {args.version}")
    print("=" * 60)

    # 1. Model Registry Artifacts Existence
    print("\n=== 1. Model Registry Artifacts Existence ===")
    version_dir = Path(args.registry_dir) / args.model_name / args.version
    check(version_dir.exists(), f"Version directory exists: {version_dir}", f"Version directory missing: {version_dir}", failures)

    expected_files = [
        "model.txt",
        "model.joblib",
        "calibration.pkl",
        "feature_schema.json",
        "feature_version.json",
        "training_config.json",
        "metrics.json",
        "metadata.json",
        "calibration_curve.png",
    ]

    for fname in expected_files:
        fpath = version_dir / fname
        check(fpath.exists() and fpath.stat().st_size > 0, f"Artifact present: {fname}", f"Artifact missing or empty: {fname}", failures)

    # 2. Model Loading and Inference Check
    print("\n=== 2. Model Registry Loadability & Inference ===")
    registry = ModelRegistry(registry_dir=args.registry_dir)
    try:
        bundle = registry.load_version(model_name=args.model_name, version=args.version)
        check(bundle["model"] is not None, "Model weights loaded successfully.", "Model failed to load.", failures)
        check(bundle["calibrator"] is not None, "Calibrator loaded successfully.", "Calibrator failed to load.", failures)
        check(len(bundle["feature_names"]) > 0, f"Loaded {len(bundle['feature_names'])} features in schema.", "Feature schema empty.", failures)
    except Exception as e:
        check(False, "", f"Failed to load model bundle from registry: {e}", failures)
        bundle = None

    if bundle is None:
        print("\n[ABORT] Cannot proceed without loaded model bundle.")
        sys.exit(1)

    # 3. Model Evaluation on Test Features
    print("\n=== 3. Performance & Acceptance Thresholds ===")
    test_path = Path(args.test_features)
    if not test_path.exists():
        check(False, "", f"Test features file missing: {test_path}", failures)
        sys.exit(1)

    test_df = pl.read_parquet(test_path)
    feature_names = bundle["feature_names"]
    missing_feats = [f for f in feature_names if f not in test_df.columns]
    check(len(missing_feats) == 0, "All schema features present in test dataset.", f"Missing features in test dataset: {missing_feats}", failures)

    X_test = test_df.select(feature_names).to_pandas()
    y_test = test_df.select("is_fraud").to_series().to_pandas()

    calibrator = bundle["calibrator"]
    cal_probs = calibrator.predict_risk_score(X_test)

    # Bound checks on calibrated probabilities
    check(
        np.all((cal_probs >= 0.0) & (cal_probs <= 1.0)),
        "All calibrated probabilities strictly bounded in [0.0, 1.0].",
        "Calibrated probabilities out of bounds [0, 1].",
        failures,
    )

    # Ground truth scenarios
    gt_path = Path(args.gt_labels)
    scenarios = None
    if gt_path.exists():
        gt_df = pl.read_parquet(gt_path)
        test_gt = test_df.select(["return_id"]).join(gt_df, on="return_id", how="left")
        scenarios = test_gt.select("true_scenario").to_series().to_list()

    evaluator = ModelEvaluator()
    metrics = evaluator.evaluate_all(y_true=y_test, y_prob=cal_probs, scenarios=scenarios, threshold=0.5)

    auprc = metrics["auprc"]
    brier = metrics["brier_score"]
    auroc = metrics["auroc"]

    print(f"  Test AUROC:       {auroc:.4f}")
    print(f"  Test AUPRC:       {auprc:.4f}")
    print(f"  Test Brier Score: {brier:.4f}")

    # Acceptance Criterion: AUPRC > 0.50
    check(auprc > 0.50, f"AUPRC ({auprc:.4f}) exceeds acceptance threshold > 0.50.", f"AUPRC ({auprc:.4f}) failed threshold > 0.50.", failures)

    # Acceptance Criterion: Brier score < 0.25
    check(brier < 0.25, f"Brier score ({brier:.4f}) is well calibrated (< 0.25).", f"Brier score ({brier:.4f}) failed threshold < 0.25.", failures)

    # 4. Scenario-wise Recall for All Three Fraud Families
    print("\n=== 4. Scenario-Wise Fraud Detection ===")
    required_fraud_scenarios = ["serial_return_abuse", "multi_account_abuse", "wardrobing"]
    scen_breakdown = metrics.get("scenario_breakdown", {})

    for req_scen in required_fraud_scenarios:
        if req_scen in scen_breakdown:
            s_rec = scen_breakdown[req_scen]["recall"]
            s_det = scen_breakdown[req_scen]["detected_samples"]
            s_tot = scen_breakdown[req_scen]["fraud_samples"]
            check(
                s_rec > 0.0,
                f"Detection confirmed for '{req_scen}': recall={s_rec:.4f} ({s_det}/{s_tot})",
                f"No detection for fraud scenario '{req_scen}' (recall=0.0)",
                failures,
            )
        else:
            check(False, "", f"Scenario '{req_scen}' not found in scenario breakdown.", failures)

    # 5. Calibration Curve Artifact Check
    print("\n=== 5. Reliability Diagram Artifact ===")
    curve_png = version_dir / "calibration_curve.png"
    check(
        curve_png.exists() and curve_png.stat().st_size > 1000,
        f"Calibration curve plot verified ({curve_png.stat().st_size} bytes).",
        "Calibration curve plot missing or invalid.",
        failures,
    )

    # Summary
    print("\n" + "=" * 60)
    print("PHASE 3 VALIDATION SUMMARY")
    print("=" * 60)
    if not failures:
        print("[SUCCESS] ALL PHASE 3 ACCEPTANCE CHECKS PASSED.")
        print(f"Model {args.model_name}@{args.version} is production-ready.")
        sys.exit(0)
    else:
        print(f"[FAILED] {len(failures)} check(s) failed:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
