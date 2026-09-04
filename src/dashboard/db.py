"""Database models and persistence layer for Dashboard BFF."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, Generator, List, Optional
import uuid
from src.common.logging import get_logger
from .config import DATABASE_PATH, DEFAULT_BLOCK_THRESHOLD, DEFAULT_VERIFY_THRESHOLD, RAW_DATA_DIR

logger = get_logger("dashboard.db")


class DatabaseManager:
    """Manages SQLite database connections, migrations, and transactions."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DATABASE_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for thread-safe database connections."""
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=10.0,
        )
        conn.row_factory = sqlite3.Row
        # Enable Write-Ahead Logging (WAL) for concurrent read-write performance
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database transaction error: {e}")
            raise
        finally:
            conn.close()

    def init_db(self) -> None:
        """Creates tables and indexes if they do not exist."""
        with self.get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS cases (
                    request_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    merchant_id TEXT NOT NULL,
                    transaction_id TEXT NOT NULL,
                    risk_score REAL NOT NULL,
                    action TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    assignee TEXT,
                    refund_amount REAL DEFAULT 0.0,
                    order_amount REAL DEFAULT 0.0,
                    decision_metadata TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
                CREATE INDEX IF NOT EXISTS idx_cases_risk ON cases(risk_score DESC);
                CREATE INDEX IF NOT EXISTS idx_cases_user ON cases(user_id);
                CREATE INDEX IF NOT EXISTS idx_cases_created ON cases(created_at DESC);

                CREATE TABLE IF NOT EXISTS analyst_actions (
                    action_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    analyst_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    override_reason TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(case_id) REFERENCES cases(request_id)
                );

                CREATE INDEX IF NOT EXISTS idx_actions_case ON analyst_actions(case_id);

                CREATE TABLE IF NOT EXISTS policies (
                    policy_id TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    config TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    event_id TEXT PRIMARY KEY,
                    request_id TEXT,
                    timestamp TEXT NOT NULL,
                    user TEXT NOT NULL,
                    action TEXT NOT NULL,
                    metadata TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);
            """)

        self._seed_default_policy()
        self._seed_initial_cases()

    def _seed_default_policy(self) -> None:
        """Seeds standard operational risk policy if not present."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM policies").fetchone()
            if row and row["cnt"] > 0:
                return

            default_policy = {
                "name": "Standard Return-Risk Decision Policy",
                "verify_threshold": DEFAULT_VERIFY_THRESHOLD,
                "block_threshold": DEFAULT_BLOCK_THRESHOLD,
                "vip_exemption_enabled": True,
                "high_value_refund_trigger": 10000.0,
                "max_allowed_24h_returns": 3,
                "rules": [
                    {
                        "rule_id": "R_HIGH_RISK_BLOCK",
                        "condition": f"risk_score >= {DEFAULT_BLOCK_THRESHOLD}",
                        "action": "BLOCK",
                        "description": "Direct automated block for severe risk probability",
                    },
                    {
                        "rule_id": "R_SUSPECT_VERIFY",
                        "condition": f"risk_score >= {DEFAULT_VERIFY_THRESHOLD} AND risk_score < {DEFAULT_BLOCK_THRESHOLD}",
                        "action": "VERIFY",
                        "description": "Route to manual review queue for fraud analyst verification",
                    },
                    {
                        "rule_id": "R_LOW_RISK_APPROVE",
                        "condition": f"risk_score < {DEFAULT_VERIFY_THRESHOLD}",
                        "action": "APPROVE",
                        "description": "Immediate automated refund authorization",
                    },
                ],
            }
            conn.execute(
                "INSERT INTO policies (policy_id, version, config, created_at) VALUES (?, ?, ?, ?)",
                (
                    "policy_standard_v1",
                    "policy-3.0",
                    json.dumps(default_policy),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            logger.info("Default operational policy seeded.")

    def _seed_initial_cases(self) -> None:
        """Seeds initial cases from returns.parquet or synthetic samples if empty."""
        with self.get_connection() as conn:
            cnt_row = conn.execute("SELECT COUNT(*) as cnt FROM cases").fetchone()
            if cnt_row and cnt_row["cnt"] > 0:
                return

        logger.info("Seeding initial dashboard cases...")
        cases_to_insert = []
        orders_file = RAW_DATA_DIR / "orders.parquet"
        returns_file = RAW_DATA_DIR / "returns.parquet"

        if orders_file.exists() and returns_file.exists():
            try:
                import polars as pl
                orders_df = pl.read_parquet(orders_file).select(
                    ["transaction_id", "user_id", "price", "seller_id"]
                )
                returns_df = pl.read_parquet(returns_file).head(60)

                joined = returns_df.join(orders_df, on="transaction_id", how="left")
                now_iso = datetime.now(timezone.utc).isoformat()

                for i, row in enumerate(joined.iter_rows(named=True)):
                    req_id = row.get("return_id", f"ret_seed_{i}")
                    user_id = row.get("user_id") or f"usr_{100 + i}"
                    merchant_id = row.get("seller_id") or "m_102"
                    txn_id = row.get("transaction_id", f"txn_seed_{i}")
                    refund_amt = float(row.get("refund_amount") or 4500.0)
                    order_amt = float(row.get("price") or (refund_amt * 1.1))

                    # Synthetic risk spread across spectrum
                    if i % 3 == 0:
                        risk_score = round(0.72 + (i % 25) * 0.01, 4)
                        action = "VERIFY"
                        status = "PENDING_REVIEW"
                        assignee = "analyst_priya" if i % 6 == 0 else None
                    elif i % 3 == 1:
                        risk_score = round(0.85 + (i % 14) * 0.01, 4)
                        action = "BLOCK"
                        status = "BLOCKED"
                        assignee = None
                    else:
                        risk_score = round(0.08 + (i % 20) * 0.01, 4)
                        action = "APPROVE"
                        status = "APPROVED"
                        assignee = None

                    meta = {
                        "model_version": "rr-lgbm-1.0.0",
                        "calibration_version": "cal-isotonic-1.0",
                        "feature_version": "fv-2.1",
                        "expected_loss": round(refund_amt * risk_score, 2),
                        "reason": row.get("reason", "defective_item"),
                    }

                    cases_to_insert.append((
                        req_id,
                        user_id,
                        merchant_id,
                        txn_id,
                        risk_score,
                        action,
                        row.get("request_time", now_iso),
                        status,
                        assignee,
                        refund_amt,
                        order_amt,
                        json.dumps(meta),
                    ))
            except Exception as e:
                logger.warning(f"Failed to seed from parquet: {e}. Generating fallback seed cases.")

        if not cases_to_insert:
            # Fallback deterministic cases
            now_iso = datetime.now(timezone.utc).isoformat()
            cases_to_insert = [
                (
                    "ret_demo_high_001",
                    "usr_981",
                    "m_102",
                    "txn_88219",
                    0.874,
                    "VERIFY",
                    now_iso,
                    "PENDING_REVIEW",
                    None,
                    9500.0,
                    10500.0,
                    json.dumps({
                        "model_version": "rr-lgbm-1.0.0",
                        "expected_loss": 8303.0,
                        "primary_reason": "Rapid wardrobing and high refund ratio",
                    }),
                ),
                (
                    "ret_demo_block_002",
                    "usr_332",
                    "m_102",
                    "txn_44120",
                    0.942,
                    "BLOCK",
                    now_iso,
                    "BLOCKED",
                    None,
                    15200.0,
                    15200.0,
                    json.dumps({
                        "model_version": "rr-lgbm-1.0.0",
                        "expected_loss": 14318.0,
                        "primary_reason": "Multi-account syndicate linkage",
                    }),
                ),
                (
                    "ret_demo_approve_003",
                    "usr_105",
                    "m_105",
                    "txn_11094",
                    0.062,
                    "APPROVE",
                    now_iso,
                    "APPROVED",
                    None,
                    1200.0,
                    2400.0,
                    json.dumps({
                        "model_version": "rr-lgbm-1.0.0",
                        "expected_loss": 74.4,
                        "primary_reason": "Low risk repeat buyer",
                    }),
                ),
            ]

        with self.get_connection() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO cases (
                    request_id, user_id, merchant_id, transaction_id,
                    risk_score, action, created_at, status, assignee,
                    refund_amount, order_amount, decision_metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                cases_to_insert,
            )

            # Seed an initial sample action and audit record
            action_id = f"act_{uuid.uuid4().hex[:8]}"
            conn.execute(
                """
                INSERT OR IGNORE INTO analyst_actions (
                    action_id, case_id, analyst_id, action, override_reason, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action_id,
                    cases_to_insert[0][0],
                    "analyst_priya",
                    "ESCALATE",
                    "Requires proof of delivery inspection",
                    "Suspicious cluster of returns on same device footprint",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

            conn.execute(
                """
                INSERT OR IGNORE INTO audit_log (
                    event_id, request_id, timestamp, user, action, metadata
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"aud_{uuid.uuid4().hex[:8]}",
                    cases_to_insert[0][0],
                    datetime.now(timezone.utc).isoformat(),
                    "analyst_priya",
                    "CASE_ESCALATED",
                    json.dumps({"reason": "Escalated for senior fraud investigation"}),
                ),
            )

        logger.info(f"Seeded {len(cases_to_insert)} initial dashboard cases successfully.")


# Global singleton instance
db_manager = DatabaseManager()
