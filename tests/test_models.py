"""Unit and integration tests for Phase 3 Model Training and Calibration."""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import polars as pl
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.models.calibrate import Calibrator
from src.models.evaluate import ModelEvaluator
from src.models.registry import ModelRegistry
from src.models.train import ModelTrainer


@pytest.fixture
def dummy_train_val_data():
    """Generates synthetic dataset for rapid unit testing."""
    np.random.seed(42)
    n = 200
    features = [f"feat_{i}" for i in range(10)]

    X = pd.DataFrame(np.random.randn(n, 10), columns=features)
    # Simple rule for target
    y = ((X["feat_0"] + X["feat_1"] * 2.0) > 0.5).astype(int)

    train_X, val_X = X.iloc[:140], X.iloc[140:]
    train_y, val_y = y.iloc[:140], y.iloc[140:]
    return train_X, train_y, val_X, val_y, features


def test_model_trainer_training(dummy_train_val_data):
    """Verifies that ModelTrainer can train candidate models and benchmark them."""
    train_X, train_y, val_X, val_y, features = dummy_train_val_data

    trainer = ModelTrainer({
        "model": {
            "num_leaves": 15,
            "learning_rate": 0.1,
            "n_estimators": 20,
            "early_stopping_rounds": 10,
        },
        "benchmarks": {
            "xgboost": {"n_estimators": 20, "max_depth": 3, "learning_rate": 0.1, "early_stopping_rounds": 10},
            "logistic_regression": {"max_iter": 200},
        }
    })

    benchmark_res = trainer.train_and_benchmark(train_X, train_y, val_X, val_y)
    assert "lightgbm" in benchmark_res
    assert "xgboost" in benchmark_res
    assert "logistic_regression" in benchmark_res

    best_name, best_model = trainer.select_best_model()
    assert best_name in ["lightgbm", "xgboost"]
    assert best_model is not None


def test_model_calibrator(dummy_train_val_data):
    """Verifies that Calibrator fits and produces strictly bounded probabilities."""
    train_X, train_y, val_X, val_y, features = dummy_train_val_data

    trainer = ModelTrainer({
        "model": {"n_estimators": 20, "num_leaves": 15, "early_stopping_rounds": 10}
    })
    lgb_model = trainer.train_lightgbm(train_X, train_y, val_X, val_y)

    calibrator = Calibrator(base_estimator=lgb_model, method="isotonic")
    calibrator.fit(val_X, val_y)

    cal_probs = calibrator.predict_risk_score(val_X)
    assert len(cal_probs) == len(val_X)
    assert np.all(cal_probs >= 0.0)
    assert np.all(cal_probs <= 1.0)

    # Reliability curve computation
    prob_true, prob_pred = Calibrator.compute_reliability_curve(val_y, cal_probs, n_bins=5)
    assert len(prob_true) == len(prob_pred)


def test_model_evaluator():
    """Verifies metric computation including FPR recall and top-K precision."""
    y_true = np.array([0, 0, 0, 1, 1, 1, 0, 1, 0, 0])
    y_prob = np.array([0.1, 0.2, 0.15, 0.85, 0.9, 0.75, 0.3, 0.8, 0.05, 0.2])
    scenarios = ["legitimate"] * 3 + ["serial_return_abuse"] * 3 + ["legitimate"] + ["wardrobing"] + ["legitimate"] * 2

    evaluator = ModelEvaluator()
    metrics = evaluator.evaluate_all(y_true, y_prob, scenarios=scenarios, threshold=0.5)

    assert "auroc" in metrics
    assert "auprc" in metrics
    assert "brier_score" in metrics
    assert "recall_at_5pct_fpr" in metrics
    assert "precision_at_top_10pct" in metrics
    assert "scenario_breakdown" in metrics

    assert metrics["scenario_breakdown"]["serial_return_abuse"]["recall"] == 1.0
    assert metrics["scenario_breakdown"]["wardrobing"]["recall"] == 1.0


def test_model_registry_save_and_load(tmp_path, dummy_train_val_data):
    """Verifies saving and loading full model bundles through ModelRegistry."""
    train_X, train_y, val_X, val_y, features = dummy_train_val_data

    trainer = ModelTrainer({"model": {"n_estimators": 10, "num_leaves": 10, "early_stopping_rounds": 5}})
    model = trainer.train_lightgbm(train_X, train_y, val_X, val_y)

    calibrator = Calibrator(base_estimator=model, method="isotonic")
    calibrator.fit(val_X, val_y)

    registry = ModelRegistry(registry_dir=tmp_path)
    metrics = {"auroc": 0.95, "auprc": 0.80}

    save_dir = registry.save_version(
        model_name="test-model",
        version="0.1.0",
        model=model,
        calibrator=calibrator,
        feature_schema=features,
        metrics=metrics,
        training_config={"n_estimators": 10},
    )
    assert save_dir.exists()
    assert (save_dir / "model.txt").exists()
    assert (save_dir / "calibration.pkl").exists()
    assert (save_dir / "feature_schema.json").exists()

    loaded = registry.load_version("test-model", "0.1.0")
    assert loaded["model_name"] == "test-model"
    assert loaded["version"] == "0.1.0"
    assert loaded["feature_names"] == features
    assert loaded["metrics"]["auroc"] == 0.95
    assert loaded["calibrator"] is not None

    loaded_probs = loaded["calibrator"].predict_risk_score(val_X)
    assert len(loaded_probs) == len(val_X)
