from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.deps.auth import get_current_user
from app.main import app


@pytest.fixture()
def client():
    def override_db():
        yield SimpleNamespace()

    def override_current_user():
        return SimpleNamespace(id="test-user")

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_dashboard_trend_api_contract_and_params(client, monkeypatch):
    from app.routers import dashboard as dashboard_router

    captured = {}

    def _mock_get_trend_data(db, *, granularity, limit, before):
        captured["granularity"] = granularity
        captured["limit"] = limit
        captured["before"] = before
        return {
            "granularity": granularity,
            "data": [
                {
                    "label": "2024-06",
                    "revenue": "1200.00",
                    "cost": "800.00",
                    "margin_rate": "33.33",
                    "mom_revenue": "5.20",
                    "yoy_revenue": "12.40",
                    "mom_cost": "-2.10",
                    "yoy_cost": "8.30",
                    "mom_margin": "1.10",
                    "yoy_margin": "3.20",
                }
            ],
            "has_more": True,
            "earliest_confirmed_at": datetime(2024, 6, 1, tzinfo=timezone.utc),
        }

    monkeypatch.setattr(dashboard_router, "get_trend_data", _mock_get_trend_data)

    response = client.get(
        "/api/v1/dashboard/trend?granularity=month_day&limit=12&before=2025-01-01T00:00:00Z"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["granularity"] == "month_day"
    assert body["data"][0]["label"] == "2024-06"
    assert body["has_more"] is True
    assert captured["granularity"] == "month_day"
    assert captured["limit"] == 12
    assert captured["before"] == datetime(2025, 1, 1, tzinfo=timezone.utc)


def test_dashboard_trend_api_validation(client):
    missing_granularity = client.get("/api/v1/dashboard/trend?limit=12")
    assert missing_granularity.status_code == 422

    invalid_granularity = client.get("/api/v1/dashboard/trend?granularity=all&limit=12")
    assert invalid_granularity.status_code == 422

    invalid_before = client.get("/api/v1/dashboard/trend?granularity=month_day&limit=12&before=not-a-date")
    assert invalid_before.status_code == 422
