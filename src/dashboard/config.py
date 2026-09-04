"""Configuration settings for the Dashboard Backend (BFF) service."""

import os
from pathlib import Path

# Project base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
EXPLANATIONS_DIR = DATA_DIR / "explanations"
MODEL_REGISTRY_DIR = BASE_DIR / "model_registry"

# Database Configuration
DATABASE_PATH = Path(os.getenv("DASHBOARD_DB_PATH", str(DATA_DIR / "dashboard.db")))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")

# Service & Network Settings
BFF_HOST = os.getenv("BFF_HOST", "0.0.0.0")
BFF_PORT = int(os.getenv("BFF_PORT", "8001"))
DEFAULT_PAGE_SIZE = int(os.getenv("DEFAULT_PAGE_SIZE", "20"))
MAX_PAGE_SIZE = int(os.getenv("MAX_PAGE_SIZE", "100"))

# Default Policy Thresholds
DEFAULT_VERIFY_THRESHOLD = float(os.getenv("DEFAULT_VERIFY_THRESHOLD", "0.40"))
DEFAULT_BLOCK_THRESHOLD = float(os.getenv("DEFAULT_BLOCK_THRESHOLD", "0.80"))

# Ensure directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)
