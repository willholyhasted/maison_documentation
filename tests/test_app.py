import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_query_documents_empty(client):
    """Test that querying documents returns empty list when no documents exist"""
    response = client.get("/documents/query")
    assert response.status_code == 200
    data = response.get_json()
    assert "count" in data
    assert "documents" in data
    assert data["count"] == 0
    assert data["documents"] == []


# To add more tests here when database is populated
