"""FastAPI inference router and endpoint handler for synchronous return risk scoring."""

import time
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, status
from src.common.idempotency import generate_idempotency_key, hash_dict_or_str
from src.common.logging import get_logger
from src.common.metrics import (
    record_risk_score,
    update_graph_feature_age,
    update_shap_queue_depth,
)
from src.explainability import (
    ExplanationJob,
    ExplanationQueue,
    ExplanationRecord,
    ExplanationStore,
)
from .context_resolver import ContextResolver
from .economic_engine import EconomicDecisionEngine
from .feature_store import InMemoryFeatureStore
from .model_loader import ModelLoader
from .schemas import (
    DecisionResult,
    EconomicsMetadata,
    ExplanationMetadata,
    FeaturesMetadata,
    ReturnScoreRequest,
    ReturnScoreResponse,
    RiskResult,
)

logger = get_logger("inference.api")
router = APIRouter(prefix="/v1/risk/returns", tags=["Inference"])

# Global singletons initialized once on module load / startup
_feature_store = InMemoryFeatureStore()
_context_resolver = ContextResolver(feature_store=_feature_store)
_model_loader = ModelLoader()
_economic_engine = EconomicDecisionEngine()
_explanation_queue = ExplanationQueue()
_explanation_store = ExplanationStore()

# In-memory idempotency cache: idempotency_key -> ReturnScoreResponse
_idempotency_cache: Dict[str, ReturnScoreResponse] = {}


def get_components():
    """Accessor for components (allows test fixture overrides)."""
    return (
        _feature_store,
        _context_resolver,
        _model_loader,
        _economic_engine,
        _explanation_queue,
        _explanation_store,
    )


def init_service():
    """Warms up feature store and model loader."""
    logger.info("Initializing online feature store and model loader...")
    _feature_store.load()
    _model_loader.load()
    logger.info("Inference service components warmed up successfully.")


@router.post(
    "/score",
    response_model=ReturnScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Score a return request for fraud risk and economic action",
)
async def score_return(request: ReturnScoreRequest) -> ReturnScoreResponse:
    """Synchronous scoring endpoint.

    Evaluates return request against 52 precomputed features, calibrated LightGBM model,
    and merchant/product economic profiles to return an actionable decision (APPROVE/VERIFY/BLOCK).
    Asynchronously queues a TreeSHAP explanation job without blocking response.
    """
    start_time = time.perf_counter()

    # 1. Idempotency check
    payload_dict = request.model_dump(mode="json")
    payload_hash = hash_dict_or_str(payload_dict)
    idem_key = generate_idempotency_key(request.request_id, payload_hash)

    if idem_key in _idempotency_cache:
        logger.info(f"Idempotent hit for request_id={request.request_id}")
        return _idempotency_cache[idem_key]

    try:
        # 2. Context resolution (features, economic context, metadata)
        ml_features, economic_context, meta = _context_resolver.resolve(request)

        # 3. Model inference & probability calibration (No SHAP or graph traversal in critical path)
        cal_prob, raw_margin, model_ver, cal_ver = _model_loader.predict(ml_features)

        # 4. Economic decision engine
        decision: DecisionResult = _economic_engine.decide(
            probability=cal_prob,
            economic_context=economic_context,
            policy=economic_context.get("policy"),
        )

        # 5. Assemble structured response
        response = ReturnScoreResponse(
            request_id=request.request_id,
            risk=RiskResult(
                probability=round(cal_prob, 4),
                model_version=model_ver,
                calibration_version=cal_ver,
                raw_margin=round(raw_margin, 4),
            ),
            decision=decision,
            features=FeaturesMetadata(
                feature_version=meta.get("feature_version", "fv-2.1"),
                graph_version=meta.get("graph_version", "g0000"),
                graph_age_ms=meta.get("graph_age_ms", 0),
            ),
            economics=EconomicsMetadata(
                merchant_profile_version=meta.get("merchant_profile_version", "merchant-econ-1.7"),
                product_profile_version=meta.get("product_profile_version", "product-econ-4.2"),
                profile_freshness_ms=meta.get("profile_freshness_ms", 1800),
            ),
            explanation=ExplanationMetadata(
                status="PENDING",
            ),
        )

        # 6. Store in idempotency cache
        _idempotency_cache[idem_key] = response

        # 7. Asynchronously enqueue explanation job & mark pending state (< 0.5ms overhead)
        try:
            job = ExplanationJob(
                request_id=request.request_id,
                user_id=request.user_id,
                merchant_id=request.merchant_id,
                feature_vector=ml_features,
                raw_margin=raw_margin,
                calibrated_probability=cal_prob,
                decision_action=decision.action,
                model_version=model_ver,
                calibration_version=cal_ver,
                feature_version=meta.get("feature_version", "fv-2.1"),
                graph_version=meta.get("graph_version", "g0000"),
            )
            _explanation_queue.enqueue(job)
            _explanation_store.record_pending(request.request_id)
        except Exception as q_err:
            logger.warning(f"Failed to enqueue explanation job for {request.request_id}: {q_err}")

        elapsed_sec = time.perf_counter() - start_time
        elapsed_ms = elapsed_sec * 1000.0

        # Record custom Prometheus metrics
        record_risk_score(
            action=decision.action,
            duration_seconds=elapsed_sec,
            model_version=model_ver,
            status_str="success",
        )
        try:
            update_shap_queue_depth(_explanation_queue.size())
        except Exception:
            pass
        if meta.get("graph_age_ms"):
            update_graph_feature_age(meta["graph_age_ms"] / 1000.0, meta.get("graph_version", "g0000"))

        logger.info(
            f"Scored return_id={request.request_id} in {elapsed_ms:.2f}ms | Action={decision.action} | Prob={cal_prob:.4f}"
        )
        return response

    except Exception as e:
        elapsed_sec = time.perf_counter() - start_time
        record_risk_score(
            action="ERROR",
            duration_seconds=elapsed_sec,
            model_version="error",
            status_str="error",
        )
        logger.error(f"Error scoring return request {request.request_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference scoring error: {str(e)}",
        )


@router.get(
    "/{request_id}/explanation",
    response_model=ExplanationRecord,
    status_code=status.HTTP_200_OK,
    summary="Retrieve asynchronous TreeSHAP explanation for a scored return",
)
async def get_return_explanation(request_id: str) -> ExplanationRecord:
    """Retrieves the explanation record for a previously scored return request.

    Returns status 'PENDING' while the background worker is computing TreeSHAP,
    and 'READY' with all attributions and reason codes once completed.
    """
    record = _explanation_store.get_explanation(request_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Explanation for request_id '{request_id}' not found.",
        )
    return record

