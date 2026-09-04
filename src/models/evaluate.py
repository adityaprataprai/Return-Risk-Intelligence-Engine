"""Model evaluation and metrics module.

Computes comprehensive performance metrics on test sets:
AUROC, AUPRC, Brier score, Precision/Recall/F1, Recall at fixed FPR, Precision at top-K,
and scenario-wise fraud recall breakdown.
"""

from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd
import polars as pl
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)


class ModelEvaluator:
    """Evaluates fraud prediction models against statistical and business fraud metrics."""

    @staticmethod
    def compute_recall_at_fpr(
        y_true: Union[pd.Series, np.ndarray],
        y_prob: Union[pd.Series, np.ndarray],
        target_fpr: float = 0.05,
    ) -> float:
        """Computes true positive rate (recall) at a fixed false positive rate (e.g., 5% FPR)."""
        fpr, tpr, _ = roc_curve(y_true, y_prob)
        # Find indices where fpr <= target_fpr
        valid_indices = np.where(fpr <= target_fpr)[0]
        if len(valid_indices) == 0:
            return 0.0
        best_idx = valid_indices[-1]
        return float(tpr[best_idx])

    @staticmethod
    def compute_precision_at_top_k(
        y_true: Union[pd.Series, np.ndarray],
        y_prob: Union[pd.Series, np.ndarray],
        top_k_pct: float = 0.10,
    ) -> float:
        """Computes precision within the top K% highest-risk predicted return requests."""
        y_t = np.asarray(y_true)
        y_p = np.asarray(y_prob)
        n_samples = len(y_p)
        k = max(1, int(n_samples * top_k_pct))

        top_k_indices = np.argsort(y_p)[::-1][:k]
        top_k_labels = y_t[top_k_indices]
        return float(np.mean(top_k_labels))

    @staticmethod
    def compute_scenario_wise_recall(
        y_true: Union[pd.Series, np.ndarray],
        y_prob: Union[pd.Series, np.ndarray],
        scenarios: Union[pd.Series, np.ndarray, List[str]],
        threshold: float = 0.5,
    ) -> Dict[str, Dict[str, Union[float, int]]]:
        """Computes detection recall broken down by specific fraud scenario from hidden ground truth."""
        y_t = np.asarray(y_true)
        y_p = np.asarray(y_prob)
        scen = np.asarray(scenarios)

        preds = (y_p >= threshold).astype(int)
        unique_scenarios = sorted(list(set(scen)))
        breakdown = {}

        for s in unique_scenarios:
            mask = scen == s
            total_count = int(np.sum(mask))
            actual_fraud_count = int(np.sum(y_t[mask]))
            detected_fraud_count = int(np.sum(preds[mask] & (y_t[mask] == 1)))

            if actual_fraud_count > 0:
                rec = float(detected_fraud_count / actual_fraud_count)
            else:
                rec = 0.0

            breakdown[str(s)] = {
                "total_samples": total_count,
                "fraud_samples": actual_fraud_count,
                "detected_samples": detected_fraud_count,
                "recall": round(rec, 4),
            }

        return breakdown

    def evaluate_all(
        self,
        y_true: Union[pd.Series, np.ndarray],
        y_prob: Union[pd.Series, np.ndarray],
        scenarios: Optional[Union[pd.Series, np.ndarray, List[str]]] = None,
        threshold: float = 0.5,
    ) -> Dict[str, Any]:
        """Computes all required acceptance and operational metrics on the test dataset."""
        y_t = np.asarray(y_true)
        y_p = np.asarray(y_prob)
        preds = (y_p >= threshold).astype(int)

        auroc = float(roc_auc_score(y_t, y_p))
        auprc = float(average_precision_score(y_t, y_p))
        brier = float(brier_score_loss(y_t, y_p))

        precision = float(precision_score(y_t, preds, zero_division=0))
        recall = float(recall_score(y_t, preds, zero_division=0))
        f1 = float(f1_score(y_t, preds, zero_division=0))

        recall_5pct_fpr = self.compute_recall_at_fpr(y_t, y_p, target_fpr=0.05)
        precision_top10pct = self.compute_precision_at_top_k(y_t, y_p, top_k_pct=0.10)

        metrics = {
            "auroc": round(auroc, 4),
            "auprc": round(auprc, 4),
            "brier_score": round(brier, 4),
            "classification_threshold": threshold,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "recall_at_5pct_fpr": round(recall_5pct_fpr, 4),
            "precision_at_top_10pct": round(precision_top10pct, 4),
            "total_test_samples": len(y_t),
            "total_fraud_samples": int(np.sum(y_t)),
        }

        if scenarios is not None:
            metrics["scenario_breakdown"] = self.compute_scenario_wise_recall(
                y_t, y_p, scenarios, threshold=threshold
            )

        return metrics
