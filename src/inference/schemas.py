"""Pydantic schemas for the Return-Risk Inference API contract."""

from datetime import datetime
from typing import Any, Dict, Literal, Optional, Union
from pydantic import BaseModel, Field


class ReturnScoreRequest(BaseModel):
    """Input payload for scoring a return request."""
    request_id: str = Field(..., description="Unique return request identifier", examples=["ret_12345"])
    merchant_id: str = Field(..., description="Merchant identifier", examples=["m_102"])
    user_id: str = Field(..., description="Customer account identifier", examples=["usr_981"])
    transaction_id: str = Field(..., description="Original order transaction identifier", examples=["txn_12891"])
    product_id: str = Field(..., description="Product identifier", examples=["prod_7781"])
    timestamp: Union[datetime, str] = Field(..., description="Timestamp of return request", examples=["2026-09-02T21:40:11Z"])
    refund_amount: float = Field(..., ge=0.0, description="Requested refund amount in currency units", examples=[8420.0])
    order_amount: float = Field(..., ge=0.0, description="Total original transaction amount", examples=[10500.0])
    product_category: str = Field(default="default", description="Category of product being returned", examples=["electronics"])
    device_id: Optional[str] = Field(default=None, description="Device fingerprint ID", examples=["dev_391"])
    address_id: Optional[str] = Field(default=None, description="Shipping/return address ID", examples=["addr_120"])
    payment_id: Optional[str] = Field(default=None, description="Payment instrument token", examples=["pay_883"])


class RiskResult(BaseModel):
    """Calibrated fraud probability and raw scoring metadata."""
    probability: float = Field(..., ge=0.0, le=1.0, description="Calibrated fraud risk probability", examples=[0.874])
    model_version: str = Field(..., description="Registered model version", examples=["rr-lgbm-1.0.0"])
    calibration_version: str = Field(..., description="Calibration method/version", examples=["cal-1.0"])
    raw_margin: float = Field(..., description="Raw model logit/margin score before calibration", examples=[1.93])


class DecisionResult(BaseModel):
    """Economic action and financial risk assessment."""
    action: Literal["APPROVE", "VERIFY", "BLOCK"] = Field(..., description="Prescribed automated risk decision", examples=["VERIFY"])
    expected_loss: float = Field(..., ge=0.0, description="Quantified expected financial loss in currency units", examples=[812.40])
    policy_version: str = Field(..., description="Policy rulebook version", examples=["policy-3.0"])


class FeaturesMetadata(BaseModel):
    """Feature store lineage and freshness tracking."""
    feature_version: str = Field(..., description="Feature schema definition version", examples=["fv-2.1"])
    graph_version: str = Field(default="g0000", description="Identity graph partition version", examples=["g0000"])
    graph_age_ms: int = Field(default=0, ge=0, description="Graph snapshot staleness in milliseconds", examples=[0])


class EconomicsMetadata(BaseModel):
    """Economic profile versioning and staleness."""
    merchant_profile_version: str = Field(..., description="Merchant economic profile version", examples=["merchant-econ-1.7"])
    product_profile_version: str = Field(..., description="Product economic profile version", examples=["product-econ-4.2"])
    profile_freshness_ms: int = Field(default=1800, ge=0, description="Profile cached freshness in milliseconds", examples=[1800])


class ExplanationMetadata(BaseModel):
    """Explainability status stub (asynchronous SHAP pipeline)."""
    status: Literal["PENDING", "COMPLETED", "SKIPPED"] = Field(default="PENDING", description="Status of SHAP explanation job", examples=["PENDING"])


class ReturnScoreResponse(BaseModel):
    """Full synchronous response payload for POST /v1/risk/returns/score."""
    request_id: str = Field(..., description="Correlated return request identifier", examples=["ret_12345"])
    risk: RiskResult
    decision: DecisionResult
    features: FeaturesMetadata
    economics: EconomicsMetadata
    explanation: ExplanationMetadata
