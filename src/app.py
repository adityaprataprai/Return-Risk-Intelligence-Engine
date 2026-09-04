from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.common.logging import get_logger, setup_logging

logger = get_logger("api.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown events."""
    setup_logging()
    logger.info("Initializing Razorpay Return-Risk Intelligence Engine API...")
    try:
        from src.inference.api import init_service
        init_service()
    except Exception as e:
        logger.warning(f"Deferred inference service warmup: {e}")
    yield
    logger.info("Shutting down Return-Risk Intelligence Engine API...")


def create_app() -> FastAPI:
    """Factory function for FastAPI application."""
    app = FastAPI(
        title="Razorpay Return-Risk Intelligence Engine",
        version="0.1.0",
        description="Real-time return abuse detection and economic decision engine.",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Correlation ID middleware
    from src.common.middleware import RequestIdMiddleware
    app.add_middleware(RequestIdMiddleware)

    @app.get("/health", tags=["Health"])
    async def health() -> Dict[str, str]:
        """Health check endpoint."""
        return {
            "status": "ok",
            "version": "0.1.0",
        }

    # Include routers
    from src.inference.api import router as inference_router
    app.include_router(inference_router)

    # Initialize Prometheus metrics & /metrics endpoint
    from src.common.metrics import setup_metrics
    setup_metrics(app, app_name="risk-engine-api")

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run("src.app:app", host="0.0.0.0", port=8000, reload=True)
