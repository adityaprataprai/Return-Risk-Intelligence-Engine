"""Model training and benchmarking module.

Supports LightGBM (primary), XGBoost (benchmark), and Logistic Regression (baseline),
with automated early stopping on validation sets and benchmark comparison.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import lightgbm as lgb
import numpy as np
import pandas as pd
import polars as pl
import xgboost as xgb
import yaml
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler


DEFAULT_EXCLUDE_COLUMNS = {
    "return_id",
    "transaction_id",
    "user_id",
    "timestamp",
    "request_time",
    "graph_last_updated_at",
    "is_fraud",
    "split",
}


class ModelTrainer:
    """Orchestrates model training, benchmarking, and hyperparameter ingestion."""

    def __init__(self, config: Optional[Union[str, Path, Dict[str, Any]]] = None):
        self.config: Dict[str, Any] = {}
        if config is not None:
            if isinstance(config, (str, Path)):
                self.load_config(config)
            elif isinstance(config, dict):
                self.config = config

        self.feature_names: List[str] = []
        self.target_name: str = "is_fraud"
        self.trained_models: Dict[str, Any] = {}
        self.benchmark_results: Dict[str, Dict[str, float]] = {}

    def load_config(self, path: Union[str, Path]) -> None:
        """Loads model training configuration from YAML."""
        with open(path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

    def prepare_data(
        self,
        train_df: pl.DataFrame,
        val_df: pl.DataFrame,
        test_df: Optional[pl.DataFrame] = None,
        target_col: str = "is_fraud",
        exclude_cols: Optional[Union[List[str], Set[str]]] = None,
    ) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, Optional[pd.DataFrame], Optional[pd.Series]]:
        """Separates features from targets and non-feature metadata."""
        if exclude_cols is None:
            config_excludes = self.config.get("data", {}).get("exclude_columns", [])
            exclude = DEFAULT_EXCLUDE_COLUMNS | set(config_excludes)
        else:
            exclude = set(exclude_cols) | {target_col}

        self.target_name = target_col
        self.feature_names = [c for c in train_df.columns if c not in exclude]

        X_train = train_df.select(self.feature_names).to_pandas()
        y_train = train_df.select(target_col).to_series().to_pandas()

        X_val = val_df.select(self.feature_names).to_pandas()
        y_val = val_df.select(target_col).to_series().to_pandas()

        if test_df is not None:
            X_test = test_df.select(self.feature_names).to_pandas()
            y_test = test_df.select(target_col).to_series().to_pandas()
        else:
            X_test, y_test = None, None

        return X_train, y_train, X_val, y_val, X_test, y_test

    def train_lightgbm(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
    ) -> lgb.LGBMClassifier:
        """Trains LightGBM classifier with early stopping on validation split."""
        model_cfg = self.config.get("model", {})
        num_leaves = model_cfg.get("num_leaves", 63)
        learning_rate = model_cfg.get("learning_rate", 0.05)
        n_estimators = model_cfg.get("n_estimators", 500)
        early_stopping_rounds = model_cfg.get("early_stopping_rounds", 50)
        reg_alpha = model_cfg.get("reg_alpha", 0.1)
        reg_lambda = model_cfg.get("reg_lambda", 0.1)
        min_child_samples = model_cfg.get("min_child_samples", 50)
        subsample = model_cfg.get("subsample", 0.9)
        colsample_bytree = model_cfg.get("colsample_bytree", 0.9)
        random_state = model_cfg.get("random_state", 42)

        clf = lgb.LGBMClassifier(
            objective="binary",
            num_leaves=num_leaves,
            learning_rate=learning_rate,
            n_estimators=n_estimators,
            reg_alpha=reg_alpha,
            reg_lambda=reg_lambda,
            min_child_samples=min_child_samples,
            subsample=subsample,
            colsample_bytree=colsample_bytree,
            random_state=random_state,
            verbose=-1,
        )

        callbacks = [lgb.early_stopping(stopping_rounds=early_stopping_rounds, verbose=False)]
        clf.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            callbacks=callbacks,
        )
        self.trained_models["lightgbm"] = clf
        return clf

    def train_xgboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
    ) -> xgb.XGBClassifier:
        """Trains XGBoost classifier benchmark with early stopping."""
        xgb_cfg = self.config.get("benchmarks", {}).get("xgboost", {})
        n_estimators = xgb_cfg.get("n_estimators", 300)
        max_depth = xgb_cfg.get("max_depth", 6)
        learning_rate = xgb_cfg.get("learning_rate", 0.05)
        early_stopping_rounds = xgb_cfg.get("early_stopping_rounds", 50)
        subsample = xgb_cfg.get("subsample", 0.9)
        colsample_bytree = xgb_cfg.get("colsample_bytree", 0.9)
        random_state = xgb_cfg.get("random_state", 42)

        clf = xgb.XGBClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            early_stopping_rounds=early_stopping_rounds,
            subsample=subsample,
            colsample_bytree=colsample_bytree,
            random_state=random_state,
            eval_metric=["auc", "logloss"],
        )

        clf.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )
        self.trained_models["xgboost"] = clf
        return clf

    def train_logistic_regression(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
    ) -> Pipeline:
        """Trains Logistic Regression baseline with median imputation and standard scaling."""
        lr_cfg = self.config.get("benchmarks", {}).get("logistic_regression", {})
        max_iter = lr_cfg.get("max_iter", 1000)
        random_state = lr_cfg.get("random_state", 42)

        pipe = make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            LogisticRegression(max_iter=max_iter, random_state=random_state),
        )
        pipe.fit(X_train, y_train)
        self.trained_models["logistic_regression"] = pipe
        return pipe

    def train_and_benchmark(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
    ) -> Dict[str, Dict[str, float]]:
        """Trains all candidate models and benchmarks their AUROC and AUPRC on validation set."""
        print("Training LightGBM primary model...")
        lgb_model = self.train_lightgbm(X_train, y_train, X_val, y_val)
        lgb_probs = lgb_model.predict_proba(X_val)[:, 1]

        print("Training XGBoost benchmark model...")
        xgb_model = self.train_xgboost(X_train, y_train, X_val, y_val)
        xgb_probs = xgb_model.predict_proba(X_val)[:, 1]

        print("Training Logistic Regression baseline...")
        lr_model = self.train_logistic_regression(X_train, y_train)
        lr_probs = lr_model.predict_proba(X_val)[:, 1]

        results = {
            "lightgbm": {
                "val_auroc": float(roc_auc_score(y_val, lgb_probs)),
                "val_auprc": float(average_precision_score(y_val, lgb_probs)),
            },
            "xgboost": {
                "val_auroc": float(roc_auc_score(y_val, xgb_probs)),
                "val_auprc": float(average_precision_score(y_val, xgb_probs)),
            },
            "logistic_regression": {
                "val_auroc": float(roc_auc_score(y_val, lr_probs)),
                "val_auprc": float(average_precision_score(y_val, lr_probs)),
            },
        }
        self.benchmark_results = results
        return results

    def select_best_model(self) -> Tuple[str, Any]:
        """Selects top model between LightGBM and XGBoost based on validation AUPRC/AUROC."""
        if not self.benchmark_results:
            raise ValueError("Must run train_and_benchmark before selecting best model.")

        # LightGBM is primary by architecture spec, but choose best validation AUPRC
        lgb_score = self.benchmark_results["lightgbm"]["val_auprc"]
        xgb_score = self.benchmark_results["xgboost"]["val_auprc"]

        # If performance is very close (within 0.01), favor primary LightGBM for latency/deployment
        if xgb_score > lgb_score + 0.02:
            best_name = "xgboost"
        else:
            best_name = "lightgbm"

        return best_name, self.trained_models[best_name]
