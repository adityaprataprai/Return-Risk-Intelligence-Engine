"""Asynchronous SHAP worker computing TreeSHAP in raw margin space."""

from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Union
import joblib
import numpy as np
import pandas as pd
import shap
from src.common.logging import get_logger
from .grouping import SemanticGrouper
from .queue import ExplanationQueue
from .reason_codes import ReasonCodeEngine
from .schemas import (
    ExplanationJob,
    ExplanationRecord,
    FeatureAttribution,
)
from .store import ExplanationStore

logger = get_logger("explainability.worker")


class ShapWorker:
    """Consumes explanation jobs from queue, computes TreeSHAP in raw margin space,

    generates semantic reason codes, and persists immutable explanation records.
    """

    def __init__(
        self,
        queue: Optional[ExplanationQueue] = None,
        store: Optional[ExplanationStore] = None,
        grouper: Optional[SemanticGrouper] = None,
        reason_engine: Optional[ReasonCodeEngine] = None,
        model_dir: Union[str, Path] = "model_registry/return-risk/1.0.0",
        config_path: Union[str, Path] = "config/explanation/reason_codes.yaml",
        max_retries: int = 3,
    ):
        self.queue = queue or ExplanationQueue()
        self.store = store or ExplanationStore()
        self.grouper = grouper or SemanticGrouper(config_path)
        self.reason_engine = reason_engine or ReasonCodeEngine(config_path, grouper=self.grouper)
        self.model_dir = Path(model_dir)
        self.max_retries = max_retries

        self.model: Optional[Any] = None
        self.feature_names: List[str] = []
        self.explainer: Optional[shap.TreeExplainer] = None
        self.base_value: float = 0.0
        self._is_initialized = False

    def initialize(self) -> None:
        """Loads champion model and initializes TreeExplainer."""
        if self._is_initialized:
            return

        logger.info(f"Initializing SHAP worker with model from {self.model_dir}...")
        # 1. Load feature schema
        schema_path = self.model_dir / "feature_schema.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            self.feature_names = json.load(f)["features"]

        # 2. Load model weights
        model_path = self.model_dir / "model.joblib"
        self.model = joblib.load(model_path)

        # 3. Initialize TreeExplainer (raw margin space by default for trees)
        self.explainer = shap.TreeExplainer(self.model)

        # Extract base expected value for positive class
        ev = self.explainer.expected_value
        if isinstance(ev, (list, np.ndarray)):
            self.base_value = float(ev[1]) if len(ev) > 1 else float(ev[0])
        else:
            self.base_value = float(ev)

        self._is_initialized = True
        logger.info(
            f"TreeExplainer initialized successfully. Features: {len(self.feature_names)}, Base value: {self.base_value:.4f}"
        )

    def compute_shap(self, feature_vector: Dict[str, float]) -> tuple[np.ndarray, float]:
        """Computes TreeSHAP attributions in raw margin space.

        Returns (shap_values_array, base_value).
        """
        if not self._is_initialized:
            self.initialize()

        row_vals = [float(feature_vector.get(f, 0.0)) for f in self.feature_names]
        X = pd.DataFrame([row_vals], columns=self.feature_names)

        # Compute raw margin SHAP values
        raw_sv = self.explainer.shap_values(X)

        if isinstance(raw_sv, list):
            sv = raw_sv[1] if len(raw_sv) > 1 else raw_sv[0]
        else:
            sv = raw_sv

        if hasattr(sv, "ndim") and sv.ndim == 2:
            sv = sv[0]

        return np.array(sv, dtype=np.float64), self.base_value

    def process_job(self, job: ExplanationJob) -> ExplanationRecord:
        """Executes full explainability pipeline for a single ExplanationJob.

        Guarantees idempotency and bounded retries.
        """
        start_time = time.perf_counter()
        logger.info(f"Processing explanation job for request_id={job.request_id}")

        # Idempotency check: if explanation already exists and is READY, skip recomputing
        existing = self.store.get_explanation(job.request_id)
        if existing is not None and existing.status == "READY":
            logger.info(f"Explanation for request_id={job.request_id} already exists (READY). Returning cached.")
            return existing

        try:
            # 1. Compute TreeSHAP
            shap_vals, base_val = self.compute_shap(job.feature_vector)

            # 2. Additivity verification: base_val + sum(shap_vals) == raw_margin
            reconstructed_margin = float(base_val + np.sum(shap_vals))
            error = abs(reconstructed_margin - job.raw_margin)
            if error > 0.05:
                logger.warning(
                    f"SHAP additivity reconstruction delta: {error:.6f} "
                    f"(reconstructed: {reconstructed_margin:.4f}, raw: {job.raw_margin:.4f})"
                )

            # 3. Build individual feature attributions
            attributions: List[FeatureAttribution] = []
            for i, feat_name in enumerate(self.feature_names):
                val = float(job.feature_vector.get(feat_name, 0.0))
                s_val = float(shap_vals[i])
                attributions.append(
                    FeatureAttribution(
                        feature=feat_name,
                        value=round(val, 4),
                        shap_value=round(s_val, 4),
                        abs_shap=round(abs(s_val), 4),
                        direction="RISK_INCREASING" if s_val >= 0 else "RISK_DECREASING",
                    )
                )

            # Top individual features overall by absolute SHAP magnitude
            top_features = sorted(attributions, key=lambda f: f.abs_shap, reverse=True)[:10]

            # 4. Semantic grouping
            group_attributions = self.grouper.group_attributions(attributions)

            # 5. Reason codes & concrete evidence
            reason_codes = self.reason_engine.generate_reason_codes(
                attributions=attributions,
                feature_vector=job.feature_vector,
                max_reasons=3,
            )

            # 6. Data confidence assessment (ensures cold-start is non-punitive)
            data_confidence = self.reason_engine.evaluate_data_confidence(job.feature_vector)

            # 7. Assemble final ExplanationRecord
            now_iso = datetime.now(timezone.utc).isoformat()
            record = ExplanationRecord(
                request_id=job.request_id,
                status="READY",
                created_at=job.created_at,
                completed_at=now_iso,
                base_value=round(base_val, 4),
                raw_margin=round(job.raw_margin, 4),
                calibrated_probability=round(job.calibrated_probability, 4),
                reconstructed_margin=round(reconstructed_margin, 4),
                margin_reconstruction_error=round(error, 6),
                group_attributions=group_attributions,
                top_features=top_features,
                reason_codes=reason_codes,
                data_confidence=data_confidence,
                metadata={
                    "model_version": job.model_version,
                    "calibration_version": job.calibration_version,
                    "feature_version": job.feature_version,
                    "graph_version": job.graph_version,
                    "decision_action": job.decision_action,
                    "worker_compute_ms": round((time.perf_counter() - start_time) * 1000.0, 2),
                },
            )

            # 8. Persist explanation
            self.store.save_explanation(record)
            elapsed = (time.perf_counter() - start_time) * 1000.0
            logger.info(
                f"Completed explanation for request_id={job.request_id} in {elapsed:.2f}ms "
                f"({len(reason_codes)} reason codes generated)."
            )
            return record

        except Exception as e:
            logger.error(f"Error computing explanation for request_id={job.request_id}: {e}", exc_info=True)
            if job.retries < self.max_retries:
                job.retries += 1
                logger.info(f"Re-queueing job {job.request_id} (retry {job.retries}/{self.max_retries})...")
                self.queue.enqueue(job)
            else:
                # Save FAILED record
                failed_record = ExplanationRecord(
                    request_id=job.request_id,
                    status="FAILED",
                    created_at=job.created_at,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    error_message=str(e),
                )
                self.store.save_explanation(failed_record)
            raise

    def process_next(self, timeout_seconds: float = 0.5) -> Optional[ExplanationRecord]:
        """Dequeues and processes a single job."""
        job = self.queue.dequeue(timeout_seconds=timeout_seconds)
        if job is None:
            return None
        return self.process_job(job)

    def run(self, poll_interval: float = 0.1, max_jobs: Optional[int] = None) -> int:
        """Runs the worker loop until stopped or max_jobs processed."""
        self.initialize()
        processed = 0
        logger.info("SHAP worker polling loop started.")
        while True:
            try:
                record = self.process_next(timeout_seconds=poll_interval)
                if record is not None:
                    processed += 1
                    if max_jobs is not None and processed >= max_jobs:
                        break
            except Exception as e:
                logger.error(f"Worker iteration exception: {e}")
                time.sleep(poll_interval)
        return processed
