"""Model loader and inference runtime.

Loads champion LightGBM model weights and isotonic calibrator from model_registry/,
validates feature alignment, and produces calibrated risk probabilities and raw margins in sub-millisecond time.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import joblib
import numpy as np
import pandas as pd


class ModelLoader:
    """Loads and runs production model inference with probability calibration."""

    def __init__(
        self,
        registry_dir: Union[str, Path] = "model_registry",
        model_name: str = "return-risk",
        version: str = "1.0.0",
    ):
        self.registry_dir = Path(registry_dir)
        self.model_name = model_name
        self.version = version
        self.model_version = f"rr-lgbm-{version}"
        self.calibration_version = "cal-1.0"

        self.model: Optional[Any] = None
        self.calibrator: Optional[Any] = None
        self.feature_names: List[str] = []
        self._is_loaded = False

    def load(self) -> None:
        """Loads model weights, calibration object, and feature schema from registry."""
        version_dir = self.registry_dir / self.model_name / self.version
        if not version_dir.exists():
            raise FileNotFoundError(f"Model version not found: {version_dir}")

        # 1. Feature schema
        schema_path = version_dir / "feature_schema.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.feature_names = data.get("features", [])

        # 2. Model
        model_path = version_dir / "model.joblib"
        self.model = joblib.load(model_path)

        # 3. Calibrator
        cal_path = version_dir / "calibration.pkl"
        if cal_path.exists():
            self.calibrator = joblib.load(cal_path)

        # 4. Calibration version from metadata if available
        meta_path = version_dir / "metadata.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                cal_method = meta.get("calibration_method", "isotonic")
                self.calibration_version = f"cal-{cal_method}-1.0"

        self._is_loaded = True

    def predict(self, feature_dict: Dict[str, Any]) -> Tuple[float, float, str, str]:
        """Runs inference for a single feature dictionary.

        Returns:
            (calibrated_probability, raw_margin, model_version, calibration_version)
        """
        if not self._is_loaded:
            self.load()

        # Build single-row DataFrame strictly ordered by schema
        row_values = [feature_dict.get(feat, 0.0) for feat in self.feature_names]
        X = pd.DataFrame([row_values], columns=self.feature_names)

        # Compute raw margin (raw log-odds from tree booster)
        if hasattr(self.model, "predict"):
            try:
                raw_margin = float(self.model.predict(X, raw_score=True)[0])
            except Exception:
                raw_probs = self.model.predict_proba(X)[0, 1]
                eps = 1e-7
                p = np.clip(raw_probs, eps, 1 - eps)
                raw_margin = float(np.log(p / (1 - p)))
        else:
            raw_margin = 0.0

        # Compute calibrated probability
        if self.calibrator is not None:
            if hasattr(self.calibrator, "predict_risk_score"):
                cal_prob = float(self.calibrator.predict_risk_score(X)[0])
            elif hasattr(self.calibrator, "predict_proba"):
                cal_prob = float(self.calibrator.predict_proba(X)[0, 1])
            else:
                cal_prob = float(self.model.predict_proba(X)[0, 1])
        else:
            cal_prob = float(self.model.predict_proba(X)[0, 1])

        # Ensure strictly bounded in [0.0, 1.0]
        cal_prob = max(0.0, min(1.0, cal_prob))

        return cal_prob, raw_margin, self.model_version, self.calibration_version
