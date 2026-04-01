"""Integration tests for the FastAPI endpoints using mocked HTTP clients."""

import pytest
import respx
import httpx
from fastapi.testclient import TestClient

# Patch settings before importing app
import os
os.environ.setdefault("GOOGLE_PLACES_API_KEY", "test-key")
os.environ.setdefault("RAPIDAPI_KEY", "")

from local_scorer.api.main import app  # noqa: E402


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


MOCK_TEXT_SEARCH = {
    "places": [
        {
            "id": "ChIJabc123",
            "displayName": {"text": "La Trattoria"},
            "rating": 4.6,
            "userRatingCount": 280,
            "primaryTypeDisplayName": {"text": "Italian Restaurant"},
            "types": ["italian_restaurant", "restaurant"],
            "websiteUri": "https://latrattoria-test.es",
            "formattedAddress": "Calle Mayor 1, Madrid",
            "nationalPhoneNumber": "+34 91 000 00 00",
            "businessStatus": "OPERATIONAL",
        }
    ]
}

MOCK_PLACE_DETAILS = {
    **MOCK_TEXT_SEARCH["places"][0],
    "regularOpeningHours": {"periods": [{"open": {}}]},
    "photos": [{"name": "photo1"}, {"name": "photo2"}],
    "location": {"latitude": 40.4168, "longitude": -3.7038},
}


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "services" in data


class TestSearchEndpoint:
    @respx.mock
    def test_search_returns_results(self, client):
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=httpx.Response(200, json=MOCK_TEXT_SEARCH)
        )
        # Block any unexpected requests
        respx.route(url__regex=r".*latrattoria.*").mock(return_value=httpx.Response(404))

        response = client.post("/api/v1/search", json={
            "query": "italian restaurant",
            "location": "Madrid",
            "max_results": 3,
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "La Trattoria"
        assert data[0]["score"]["local_score"] is not None

    def test_search_validates_empty_query(self, client):
        response = client.post("/api/v1/search", json={"query": "", "location": "Madrid"})
        assert response.status_code == 422

    def test_search_requires_location(self, client):
        response = client.post("/api/v1/search", json={"query": "restaurant"})
        assert response.status_code == 422


class TestScoreEndpoint:
    @respx.mock
    def test_score_returns_full_result(self, client):
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=httpx.Response(200, json=MOCK_TEXT_SEARCH)
        )
        respx.get("https://places.googleapis.com/v1/places/ChIJabc123").mock(
            return_value=httpx.Response(200, json=MOCK_PLACE_DETAILS)
        )

        # Mock website scrape (social resolver tier 2)
        respx.get("https://latrattoria-test.es/").mock(return_value=httpx.Response(200, text="<html></html>"))

        response = client.post("/api/v1/score", json={
            "name": "La Trattoria",
            "location": "Madrid",
            "include_social": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["name"] == "La Trattoria"
        assert data["score"]["total"] > 0
        assert "recommendations" in data

    @respx.mock
    def test_score_returns_404_when_not_found(self, client):
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=httpx.Response(200, json={"places": []})
        )

        response = client.post("/api/v1/score", json={
            "name": "Nonexistent Business XYZ",
            "location": "Mars",
            "include_social": False,
        })
        assert response.status_code == 404


class TestCompareEndpoint:
    @respx.mock
    def test_compare_returns_ranked_list(self, client):
        # Both businesses return similar data
        respx.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=httpx.Response(200, json=MOCK_TEXT_SEARCH)
        )
        respx.get(url__regex=r"https://places\.googleapis\.com/v1/places/.*").mock(
            return_value=httpx.Response(200, json=MOCK_PLACE_DETAILS)
        )

        # Mock website scrapes
        respx.get(url__regex=r"https://latrattoria.*").mock(return_value=httpx.Response(200, text="<html></html>"))

        response = client.post("/api/v1/compare", json={
            "businesses": [
                {"name": "La Trattoria", "location": "Madrid"},
                {"name": "Ristorante Roma", "location": "Madrid"},
            ],
            "include_social": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        # Ranks should be sequential
        ranks = [item["rank"] for item in data]
        assert ranks == list(range(1, len(data) + 1))

    def test_compare_requires_at_least_2(self, client):
        response = client.post("/api/v1/compare", json={
            "businesses": [{"name": "Solo", "location": "Madrid"}],
        })
        assert response.status_code == 422
