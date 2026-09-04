"""Model probability calibration module.

Calibrates model scores on validation split using isotonic regression or sigmoid scaling,
and computes/plots reliability curves.
"""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve


class Calibrator:
    """Calibrates predicted probabilities using isotonic or sigmoid regression on validation data."""

    def __init__(self, base_estimator: Any, method: str = "isotonic"):
        self.base_estimator = base_estimator
        self.method = method
        self.calibrated_classifier: Optional[CalibratedClassifierCV] = None

    def fit(self, X_val: pd.DataFrame, y_val: pd.Series) -> "Calibrator":
        """Fits the calibrator on validation features and labels."""
        # Handle modern scikit-learn (>= 1.4/1.9) FrozenEstimator vs legacy cv='prefit'
        try:
            from sklearn.frozen import FrozenEstimator
            estimator = FrozenEstimator(self.base_estimator)
            self.calibrated_classifier = CalibratedClassifierCV(
                estimator=estimator,
                method=self.method,
            )
        except (ImportError, TypeError):
            # Fallback for scikit-learn versions with cv='prefit'
            self.calibrated_classifier = CalibratedClassifierCV(
                estimator=self.base_estimator,
                method=self.method,
                cv="prefit",
            )

        self.calibrated_classifier.fit(X_val, y_val)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Outputs calibrated class probabilities of shape (n_samples, 2)."""
        if self.calibrated_classifier is None:
            raise ValueError("Calibrator is not fitted yet. Call fit() first.")
        return np.asarray(self.calibrated_classifier.predict_proba(X))

    def predict_risk_score(self, X: pd.DataFrame) -> np.ndarray:
        """Returns 1D array of calibrated fraud risk probabilities in [0.0, 1.0]."""
        probs = self.predict_proba(X)
        return probs[:, 1]

    @staticmethod
    def compute_reliability_curve(
        y_true: Union[pd.Series, np.ndarray],
        y_prob: Union[pd.Series, np.ndarray],
        n_bins: int = 10,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Computes true vs predicted probabilities across confidence bins."""
        prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins, strategy="uniform")
        return prob_true, prob_pred

    def plot_reliability_curve(
        self,
        y_true: Union[pd.Series, np.ndarray],
        y_prob: Union[pd.Series, np.ndarray],
        save_path: Union[str, Path],
        uncalibrated_prob: Optional[Union[pd.Series, np.ndarray]] = None,
        title: str = "Reliability Calibration Curve",
    ) -> Path:
        """Plots and saves the reliability diagram."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        fig, ax = plt.subplots(figsize=(8, 6))

        # Perfectly calibrated diagonal reference
        ax.plot([0, 1], [0, 1], "k--", label="Perfectly Calibrated", alpha=0.7)

        # Plot uncalibrated if provided
        if uncalibrated_prob is not None:
            uncal_true, uncal_pred = calibration_curve(
                y_true, uncalibrated_prob, n_bins=10, strategy="uniform"
            )
            ax.plot(
                uncal_pred,
                uncal_true,
                "s-",
                color="#e74c3c",
                label="Uncalibrated Base Model",
                linewidth=1.5,
            )

        # Plot calibrated
        cal_true, cal_pred = self.compute_reliability_curve(y_true, y_prob, n_bins=10)
        ax.plot(
            cal_pred,
            cal_true,
            "o-",
            color="#2ecc71",
            label=f"Calibrated ({self.method.capitalize()})",
            linewidth=2,
        )

        ax.set_xlabel("Mean Predicted Probability (Confidence)")
        ax.set_ylabel("Fraction of Positives (Empirical Risk)")
        ax.set_title(title)
        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.0])
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(loc="lower right")

        fig.tight_layout()
        fig.savefig(path, dpi=200)
        plt.close(fig)
        return path
