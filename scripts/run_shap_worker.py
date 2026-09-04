"""CLI entrypoint for running the asynchronous SHAP explanation worker."""

import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.common.logging import get_logger
from src.explainability.shap_worker import ShapWorker

logger = get_logger("scripts.run_shap_worker")


def main():
    parser = argparse.ArgumentParser(description="Run asynchronous TreeSHAP explanation worker")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.2,
        help="Polling interval in seconds when queue is empty (default: 0.2)",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=None,
        help="Maximum number of jobs to process before exiting (default: infinite)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process all currently queued jobs and exit",
    )

    args = parser.parse_args()

    logger.info("Starting SHAP Explanation Worker daemon...")
    worker = ShapWorker()
    worker.initialize()

    if args.once:
        queue_size = worker.queue.size()
        logger.info(f"Processing queued jobs in one-shot mode (queue size: {queue_size})...")
        processed = 0
        while worker.queue.size() > 0:
            rec = worker.process_next(timeout_seconds=0.1)
            if rec:
                processed += 1
                logger.info(f"Processed explanation for request_id={rec.request_id}")
            else:
                break
        logger.info(f"One-shot worker finished. Processed {processed} jobs.")
        return

    try:
        worker.run(poll_interval=args.poll_interval, max_jobs=args.max_jobs)
    except KeyboardInterrupt:
        logger.info("SHAP worker stopped by user.")


if __name__ == "__main__":
    main()
