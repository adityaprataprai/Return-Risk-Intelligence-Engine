/**
 * TypeScript interface definitions matching Phase 7 Dashboard BFF API contracts.
 */

export interface OverviewKPIs {
  total_cases_evaluated: number;
  total_fraud_blocked: number;
  total_manual_reviews: number;
  total_approved: number;
  loss_prevented_amount: number;
  total_refund_requested: number;
  approval_rate: number;
  review_rate: number;
  block_rate: number;
  avg_decision_latency_ms: number;
  active_review_queue_count: number;
}

export interface RiskDistributionBucket {
  range: string;
  count: number;
  percentage: number;
}

export interface RiskDistribution {
  buckets: RiskDistributionBucket[];
  decision_breakdown: Record<string, number>;
  average_risk_score: number;
}

export interface ReviewQueueItem {
  request_id: string;
  user_id: string;
  merchant_id: string;
  transaction_id: string;
  risk_score: number;
  action: "APPROVE" | "VERIFY" | "BLOCK" | string;
  priority: "HIGH" | "MEDIUM" | "LOW";
  status: string;
  assignee: string | null;
  refund_amount: number;
  order_amount: number;
  created_at: string;
  primary_reason: string | null;
}

export interface ReviewQueueResponse {
  total: number;
  limit: number;
  offset: number;
  items: ReviewQueueItem[];
}

export interface FeatureAttribution {
  feature: string;
  value: number;
  shap_value: number;
  abs_shap: number;
  direction: "RISK_INCREASING" | "RISK_DECREASING";
}

export interface GroupAttribution {
  group_name: string;
  display_name: string;
  description: string;
  total_shap: number;
  abs_total_shap: number;
  rank: number;
  top_features: FeatureAttribution[];
}

export interface ReasonCodeEvidence {
  code: string;
  title: string;
  severity: "HIGH" | "MEDIUM" | "LOW" | "INFO";
  group: string;
  evidence_text: string;
  supporting_features: Record<string, any>;
  timestamp?: string;
  source?: string;
}

export interface DataConfidenceInfo {
  confidence_level: "HIGH" | "MEDIUM" | "LOW_COLD_START";
  history_summary: string;
  cold_start_indicators?: Record<string, any>;
}

export interface ExplanationRecord {
  request_id: string;
  status: "PENDING" | "READY" | "FAILED";
  base_value: number;
  raw_margin: number;
  calibrated_probability: number;
  reconstructed_margin?: number;
  margin_reconstruction_error?: number;
  group_attributions?: GroupAttribution[];
  top_features?: FeatureAttribution[];
  reason_codes?: ReasonCodeEvidence[];
  data_confidence?: DataConfidenceInfo;
  metadata?: Record<string, any>;
}

export interface AnalystAction {
  action_id: string;
  analyst_id: string;
  action: string;
  override_reason?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface CaseDetail {
  request_id: string;
  user_id: string;
  merchant_id: string;
  transaction_id: string;
  created_at: string;
  status: string;
  assignee: string | null;
  risk: {
    risk_score: number;
    action: string;
    expected_loss: number;
    model_version: string;
    calibration_version?: string;
  };
  order: {
    refund_amount: number;
    order_amount: number;
    transaction_id: string;
  };
  explanation: ExplanationRecord | null;
  analyst_actions: AnalystAction[];
}

export interface TimelineEvent {
  event_id: string;
  timestamp: string;
  event_type: string;
  title: string;
  description: string;
  amount?: number | null;
  badge_type: "info" | "warning" | "danger" | "success" | string;
}

export interface TimelineResponse {
  request_id: string;
  user_id: string;
  events: TimelineEvent[];
}

export interface NetworkNode {
  id: string;
  label: string;
  type: "user" | "device" | "address" | "payment";
  risk_level: "HIGH" | "MEDIUM" | "LOW" | "CLEAN";
  properties: Record<string, any>;
}

export interface NetworkEdge {
  source: string;
  target: string;
  relation: string;
  weight: number;
}

export interface NetworkGraphResponse {
  request_id: string;
  root_user_id: string;
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  summary: {
    connected_component_size: number;
    linked_accounts_count: number;
    shared_devices_count: number;
    graph_anomaly_flag?: boolean;
  };
}

export interface FraudVectorItem {
  vector: string;
  title: string;
  count: number;
  amount: number;
  percentage: number;
}

export interface FraudAnalyticsResponse {
  vectors: FraudVectorItem[];
  trend_daily: Array<{
    date: string;
    legitimate_returns: number;
    flagged_fraud: number;
  }>;
  total_flagged_count: number;
}

export interface FinancialImpactResponse {
  gross_merchandise_value: number;
  total_refund_requested: number;
  fraud_loss_prevented: number;
  return_shipping_saved: number;
  handling_costs_preserved: number;
  net_financial_savings: number;
  roi_multiple: number;
}

export interface PolicyRule {
  rule_id: string;
  condition: string;
  action: string;
  description: string;
}

export interface PolicyConfig {
  policy_id: string;
  version: string;
  verify_threshold: number;
  block_threshold: number;
  vip_exemption_enabled: boolean;
  high_value_refund_trigger: number;
  max_allowed_24h_returns: number;
  rules: PolicyRule[];
  created_at: string;
}

export interface PolicySimulateResponse {
  cases_evaluated: number;
  current_distribution: Record<string, number>;
  simulated_distribution: Record<string, number>;
  simulated_expected_loss: number;
  loss_saved_difference: number;
  review_queue_workload_change_percent: number;
}

export interface ModelHealthResponse {
  model_name: string;
  version: string;
  status: string;
  test_auroc: number;
  test_auprc: number;
  brier_score: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
}

export interface FeatureHealthResponse {
  feature_version: string;
  feature_count: number;
  redis_status: string;
  graph_freshness_age_seconds: number;
  missing_feature_rate: number;
}

export interface SystemHealthResponse {
  status: string;
  timestamp: string;
  services: Record<string, string>;
}
