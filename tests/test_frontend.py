"""Integration and structural verification test for Phase 8 Dashboard Frontend."""

from pathlib import Path
import json
import pytest

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def test_frontend_configuration_and_packages():
    """Validates package.json, next.config.js, tailwind.config.ts, and tsconfig.json."""
    pkg_file = FRONTEND_DIR / "package.json"
    assert pkg_file.exists()

    with open(pkg_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    deps = data.get("dependencies", {})
    assert "next" in deps
    assert "react" in deps
    assert "clsx" in deps
    assert "tailwind-merge" in deps

    assert (FRONTEND_DIR / "next.config.js").exists()
    assert (FRONTEND_DIR / "tailwind.config.ts").exists()
    assert (FRONTEND_DIR / "tsconfig.json").exists()


def test_frontend_routes_exist():
    """Verifies all required App Router pages exist."""
    required_routes = [
        "src/app/layout.tsx",
        "src/app/page.tsx",
        "src/app/overview/page.tsx",
        "src/app/review-queue/page.tsx",
        "src/app/cases/[request_id]/page.tsx",
        "src/app/networks/page.tsx",
        "src/app/analytics/page.tsx",
        "src/app/policies/page.tsx",
        "src/app/health/page.tsx",
    ]
    for r in required_routes:
        path = FRONTEND_DIR / r
        assert path.exists(), f"Missing route {r}"
        assert path.stat().st_size > 50


def test_frontend_components_and_hooks():
    """Verifies all dashboard UI components and hooks exist."""
    required_components = [
        "src/components/dashboard/KpiCard.tsx",
        "src/components/dashboard/RiskOverview.tsx",
        "src/components/dashboard/ReviewQueueTable.tsx",
        "src/components/dashboard/CaseDetail.tsx",
        "src/components/dashboard/ExplanationPanel.tsx",
        "src/components/dashboard/NetworkGraph.tsx",
        "src/components/dashboard/Timeline.tsx",
        "src/lib/types.ts",
        "src/lib/api.ts",
        "src/lib/utils.ts",
        "src/hooks/useOverview.ts",
        "src/hooks/useCases.ts",
        "src/hooks/useNetwork.ts",
    ]
    for c in required_components:
        path = FRONTEND_DIR / c
        assert path.exists(), f"Missing component {c}"
        assert path.stat().st_size > 50


def test_frontend_build_artifacts():
    """Verifies that next build artifacts were generated."""
    next_dir = FRONTEND_DIR / ".next"
    assert next_dir.exists()
    assert (next_dir / "build-manifest.json").exists()
