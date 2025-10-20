from fastapi.testclient import TestClient
from main import app, generate_tldr


def test_generate_tldr_simple():
    """Unit test for TL;DR generation"""
    text = """
    This is the first line of content.
    This is the second line with more details.
    This is the third line with even more information.
    This is the fourth line that should be ignored.
    """

    result = generate_tldr(text)

    assert result.startswith("TL;DR:")
    assert "first line" in result
    assert "second line" in result
    assert "third line" in result
    assert "fourth line" not in result


def test_generate_tldr_empty():
    """Unit test for empty input"""
    result = generate_tldr("")
    assert result == "No content provided."


def test_health_endpoint():
    """API test for /health endpoint"""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "doc-service"}
