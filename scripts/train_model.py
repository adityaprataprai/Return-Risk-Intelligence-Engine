#!/usr/bin/env python3
"""Phase 3: Model Training and Calibration Orchestrator Script.

Executes end-to-end model training, benchmarking (LightGBM vs XGBoost vs Logistic Regression),
probability calibration on validation split, evaluation on test split (including scenario-wise recall),
reliability curve visualization, and model bundle registration under model_registry/.
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

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.models.calibrate import Calibrator
from src.models.evaluate import ModelEvaluator
from src.models.registry import ModelRegistry
from src.models.train import ModelTrainer


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and calibrate return-risk intelligence model")
    parser.add_argument("--config", type=str, default="config/model_training.yaml", help="Path to training config YAML")
    parser.add_argument("--features-dir", type=str, default="data/features", help="Path to features directory")
    parser.add_argument("--gt-path", type=str, default="data/ground_truth/hidden_labels.parquet", help="Path to ground truth labels")
    parser.add_argument("--registry-dir", type=str, default="model_registry", help="Path to model registry directory")
    parser.add_argument("--model-name", type=str, default="return-risk", help="Model name in registry")
    parser.add_argument("--version", type=str, default="1.0.0", help="Model version to register")
    args = parser.parse_args()

    start_time = time.time()
    print("=" * 70)
    print(f"PHASE 3: MODEL TRAINING & CALIBRATION ({args.model_name}@{args.version})")
    print("=" * 70)

    # 1. Load Data
    features_dir = Path(args.features_dir)
    train_path = features_dir / "train_features.parquet"
    val_path = features_dir / "validation_features.parquet"
    test_path = features_dir / "test_features.parquet"

    print(f"Loading datasets from {features_dir}...")
    train_df = pl.read_parquet(train_path)
    val_df = pl.read_parquet(val_path)
    test_df = pl.read_parquet(test_path)

    print(f"  Train:      {train_df.shape[0]} rows, {train_df.shape[1]} columns")
    print(f"  Validation: {val_df.shape[0]} rows, {val_df.shape[1]} columns")
    print(f"  Test:       {test_df.shape[0]} rows, {test_df.shape[1]} columns")

    # 2. Prepare features and labels
    trainer = ModelTrainer(config=args.config)
    X_train, y_train, X_val, y_val, X_test, y_test = trainer.prepare_data(
        train_df=train_df,
        val_df=val_df,
        test_df=test_df,
        target_col="is_fraud",
    )
    print(f"Extracted {len(trainer.feature_names)} features for modeling.")

    # 3. Benchmark Models
    print("\n--- Benchmarking Models on Validation Set ---")
    benchmark_res = trainer.train_and_benchmark(X_train, y_train, X_val, y_val)
    for model_type, scores in benchmark_res.items():
        print(f"  {model_type.upper():20s} | Val AUROC: {scores['val_auroc']:.4f} | Val AUPRC: {scores['val_auprc']:.4f}")

    best_model_name, best_model = trainer.select_best_model()
    print(f"\nChampion model selected: {best_model_name.upper()}")

    # 4. Calibration
    calib_method = trainer.config.get("calibration", {}).get("method", "isotonic")
    print(f"\n--- Calibrating Model Probabilities ({calib_method}) ---")
    calibrator = Calibrator(base_estimator=best_model, method=calib_method)
    calibrator.fit(X_val, y_val)
    print("Calibration on validation split completed.")

    # 5. Evaluation on Test Set
    print("\n--- Evaluating Champion Model on Held-Out Test Set ---")
    raw_test_probs = best_model.predict_proba(X_test)[:, 1]
    cal_test_probs = calibrator.predict_risk_score(X_test)

    # Load ground truth scenarios for test split
    gt_path = Path(args.gt_path)
    test_scenarios = None
    if gt_path.exists():
        gt_df = pl.read_parquet(gt_path)
        test_gt = test_df.select(["return_id"]).join(gt_df, on="return_id", how="left")
        test_scenarios = test_gt.select("true_scenario").to_series().to_list()

    evaluator = ModelEvaluator()
    test_metrics = evaluator.evaluate_all(
        y_true=y_test,
        y_prob=cal_test_probs,
        scenarios=test_scenarios,
        threshold=0.5,
    )

    print(f"  Test AUROC:               {test_metrics['auroc']:.4f}")
    print(f"  Test AUPRC:               {test_metrics['auprc']:.4f}  (Acceptance: > 0.50)")
    print(f"  Test Brier Score:         {test_metrics['brier_score']:.4f}  (Acceptance: < 0.25)")
    print(f"  Test Recall @ 5% FPR:     {test_metrics['recall_at_5pct_fpr']:.4f}")
    print(f"  Test Precision @ Top 10%: {test_metrics['precision_at_top_10pct']:.4f}")
    print(f"  Test Precision:           {test_metrics['precision']:.4f}")
    print(f"  Test Recall:              {test_metrics['recall']:.4f}")
    print(f"  Test F1-Score:            {test_metrics['f1_score']:.4f}")

    if "scenario_breakdown" in test_metrics:
        print("\n--- Scenario-Wise Recall Breakdown ---")
        for scen, s_info in test_metrics["scenario_breakdown"].items():
            if s_info["fraud_samples"] > 0:
                print(f"  Scenario: {scen:25s} | Recall: {s_info['recall']:.4f} ({s_info['detected_samples']}/{s_info['fraud_samples']})")

    # 6. Plot & Save Reliability Curve
    version_dir = Path(args.registry_dir) / args.model_name / args.version
    plot_path = version_dir / "calibration_curve.png"
    calibrator.plot_reliability_curve(
        y_true=y_test,
        y_prob=cal_test_probs,
        save_path=plot_path,
        uncalibrated_prob=raw_test_probs,
        title=f"Reliability Curve - {args.model_name} v{args.version}",
    )
    print(f"\nReliability curve plotted and saved to: {plot_path}")

    # 7. Model Registry
    print("\n--- Registering Model Artifacts ---")
    registry = ModelRegistry(registry_dir=args.registry_dir)
    saved_dir = registry.save_version(
        model_name=args.model_name,
        version=args.version,
        model=best_model,
        calibrator=calibrator,
        feature_schema=trainer.feature_names,
        metrics=test_metrics,
        training_config=trainer.config,
        metadata={
            "champion_algorithm": best_model_name,
            "calibration_method": calib_method,
            "benchmark_scores": benchmark_res,
        },
    )

    duration = time.time() - start_time
    print("=" * 70)
    print(f"Phase 3 training & registration complete in {duration:.2f}s!")
    print(f"Bundle registered at: {saved_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
