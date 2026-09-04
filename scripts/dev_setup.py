"""Development environment verification script."""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def check_directories() -> None:
    print("Checking directory structure...")
    required_dirs = [
        "config/simulation",
        "config/features",
        "config/economics",
        "config/policies",
        "src/common",
        "tests",
        "scripts",
        "docs",
    ]
    for d in required_dirs:
        path = PROJECT_ROOT / d
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            print(f"  [CREATED] {d}")
        else:
            print(f"  [OK] {d}")


def check_imports() -> None:
    print("\nChecking core package imports...")
    try:
        from src.common.config import Config
        from src.common.logging import setup_logging, get_logger
        from src.common.observability import increment_counter
        from src.common.idempotency import generate_idempotency_key
        from src.common.utils import utc_now
        from src.app import app
        print("  [OK] Successfully imported all src.common modules and FastAPI app.")
    except Exception as e:
        print(f"  [ERROR] Import failed: {e}")
        sys.exit(1)


def check_config() -> None:
    print("\nChecking configuration loading...")
    try:
        from src.common.config import Config
        cfg = Config("simulation/default")
        num_cust = cfg.get("population.num_customers")
        print(f"  [OK] Loaded config 'simulation/default' (population.num_customers = {num_cust})")
    except Exception as e:
        print(f"  [ERROR] Config check failed: {e}")
        sys.exit(1)


def main() -> None:
    print("=== Razorpay Return-Risk Intelligence Engine: Dev Setup Check ===\n")
    check_directories()
    check_imports()
    check_config()
    print("\n[SUCCESS] Environment verification complete. Phase 0 scaffold is ready.")


if __name__ == "__main__":
    main()
