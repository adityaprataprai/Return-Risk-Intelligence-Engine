"""CLI runner for starting the Dashboard BFF FastAPI service."""

import argparse
import sys
from pathlib import Path
import uvicorn

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.common.logging import get_logger
from src.dashboard.config import BFF_HOST, BFF_PORT

logger = get_logger("scripts.run_dashboard_bff")


def main():
    parser = argparse.ArgumentParser(description="Run Dashboard BFF Service")
    parser.add_argument("--host", default=BFF_HOST, help=f"Bind host (default: {BFF_HOST})")
    parser.add_argument("--port", type=int, default=BFF_PORT, help=f"Bind port (default: {BFF_PORT})")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    args = parser.parse_args()

    logger.info(f"Starting Dashboard BFF service on http://{args.host}:{args.port}...")
    uvicorn.run("src.dashboard.api:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
