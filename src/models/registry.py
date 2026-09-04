"""Model registry management module.

Handles saving, versioning, loading, and inspecting complete model bundles:
model weights, calibration objects, feature schemas, training configs, metrics, and metadata.
"""

import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import joblib


DEFAULT_REGISTRY_DIR = Path("model_registry")


class ModelRegistry:
    """Manages versioned model artifacts under model_registry/<model_name>/<version>/."""

    def __init__(self, registry_dir: Union[str, Path] = DEFAULT_REGISTRY_DIR):
        self.registry_dir = Path(registry_dir)

    def _get_git_commit(self) -> str:
        """Retrieves current git commit hash if in a git repository."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            return res.stdout.strip()
        except Exception:
            return "git-unavailable-or-uncommitted"

    def save_version(
        self,
        model_name: str,
        version: str,
        model: Any,
        calibrator: Any,
        feature_schema: List[str],
        metrics: Dict[str, Any],
        training_config: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        feature_version: str = "fv-2.1",
    ) -> Path:
        """Saves all required Phase 3 artifacts for a registered model version."""
        version_dir = self.registry_dir / model_name / version
        version_dir.mkdir(parents=True, exist_ok=True)

        # 1. Save model.txt (Native LightGBM booster) and model.joblib
        model_txt_path = version_dir / "model.txt"
        model_joblib_path = version_dir / "model.joblib"

        if hasattr(model, "booster_"):
            model.booster_.save_model(str(model_txt_path))
        elif hasattr(model, "save_model"):
            model.save_model(str(model_txt_path))
        joblib.dump(model, model_joblib_path)

        # 2. Save calibration.pkl
        cal_path = version_dir / "calibration.pkl"
        joblib.dump(calibrator, cal_path)

        # 3. Save feature_schema.json
        schema_path = version_dir / "feature_schema.json"
        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "features": feature_schema,
                    "num_features": len(feature_schema),
                },
                f,
                indent=2,
            )

        # 4. Save feature_version.json
        feat_ver_path = version_dir / "feature_version.json"
        with open(feat_ver_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "version": feature_version,
                    "registry_path": "config/features/registry.yaml",
                },
                f,
                indent=2,
            )

        # 5. Save training_config.json
        cfg_path = version_dir / "training_config.json"
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(training_config, f, indent=2, default=str)

        # 6. Save metrics.json
        metrics_path = version_dir / "metrics.json"
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, default=str)

        # 7. Save metadata.json
        meta = {
            "model_name": model_name,
            "version": version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": self._get_git_commit(),
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "training_worlds": ["World A"],
        }
        if metadata:
            meta.update(metadata)

        meta_path = version_dir / "metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        print(f"Model version {model_name}@{version} saved cleanly to {version_dir}")
        return version_dir

    def load_version(
        self,
        model_name: str,
        version: str,
    ) -> Dict[str, Any]:
        """Loads a model bundle from the registry."""
        version_dir = self.registry_dir / model_name / version
        if not version_dir.exists():
            raise FileNotFoundError(f"Registered model bundle not found: {version_dir}")

        # Load feature schema
        schema_path = version_dir / "feature_schema.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_data = json.load(f)
            feature_names = schema_data.get("features", [])

        # Load metrics
        metrics_path = version_dir / "metrics.json"
        metrics = {}
        if metrics_path.exists():
            with open(metrics_path, "r", encoding="utf-8") as f:
                metrics = json.load(f)

        # Load training config
        cfg_path = version_dir / "training_config.json"
        training_config = {}
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                training_config = json.load(f)

        # Load metadata
        meta_path = version_dir / "metadata.json"
        metadata = {}
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)

        # Load feature version
        feat_ver_path = version_dir / "feature_version.json"
        feature_version = {}
        if feat_ver_path.exists():
            with open(feat_ver_path, "r", encoding="utf-8") as f:
                feature_version = json.load(f)

        # Load model
        model_joblib_path = version_dir / "model.joblib"
        if model_joblib_path.exists():
            model = joblib.load(model_joblib_path)
        else:
            model = None

        # Load calibration
        cal_path = version_dir / "calibration.pkl"
        calibrator = joblib.load(cal_path) if cal_path.exists() else None

        return {
            "model_name": model_name,
            "version": version,
            "version_dir": version_dir,
            "model": model,
            "calibrator": calibrator,
            "feature_names": feature_names,
            "metrics": metrics,
            "training_config": training_config,
            "metadata": metadata,
            "feature_version": feature_version,
        }

    def list_versions(self, model_name: str) -> List[str]:
        """Lists all registered versions for a model."""
        target_dir = self.registry_dir / model_name
        if not target_dir.exists():
            return []
        return sorted([d.name for d in target_dir.iterdir() if d.is_dir()])
