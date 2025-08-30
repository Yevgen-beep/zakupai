import os

# Add the parent directory to the path to import main
import sys
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import SUPPORTED_LANGUAGES, app, get_translation, load_locales

client = TestClient(app)


def test_load_locales():
    """Test locale loading"""
    locales = load_locales()

    # Check that all supported languages are loaded
    for lang in SUPPORTED_LANGUAGES:
        assert lang in locales
        assert isinstance(locales[lang], dict)


def test_get_translation():
    """Test translation function"""
    # Test existing key
    assert get_translation("lot_summary", "ru") == "Краткое описание лота"
    assert get_translation("lot_summary", "kz") == "Лот туралы қысқаша мәлімет"
    assert get_translation("lot_summary", "en") == "Lot Summary"

    # Test fallback for non-existent language
    assert (
        get_translation("lot_summary", "fr") == "Краткое описание лота"
    )  # Falls back to ru

    # Test non-existent key returns key itself
    assert get_translation("non_existent_key", "ru") == "non_existent_key"


@patch("main.get_conn")
def test_languages_endpoint(mock_conn):
    """Test languages endpoint"""
    response = client.get("/languages", headers={"X-API-Key": "changeme"})

    assert response.status_code == 200
    data = response.json()

    assert "default_language" in data
    assert "supported_languages" in data
    assert "locales" in data
    assert data["default_language"] == "ru"
    assert set(data["supported_languages"]) == SUPPORTED_LANGUAGES


@patch("main.get_lot")
def test_tldr_localization(mock_get_lot):
    """Test TL;DR endpoint with different languages"""
    mock_get_lot.return_value = {"id": 1, "title": "Test Lot", "price": 100000}

    # Test Russian (default)
    response = client.post(
        "/tldr", json={"lot_id": 1}, headers={"X-API-Key": "changeme"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "ru"
    assert "Краткое описание лота" in data["lines"][0]

    # Test Kazakh
    response = client.post(
        "/tldr?lang=kz", json={"lot_id": 1}, headers={"X-API-Key": "changeme"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "kz"
    assert "Лот туралы қысқаша мәлімет" in data["lines"][0]

    # Test English
    response = client.post(
        "/tldr?lang=en", json={"lot_id": 1}, headers={"X-API-Key": "changeme"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "en"
    assert "Lot Summary" in data["lines"][0]


def test_letter_generation_localization():
    """Test letter generation with localization"""
    request_data = {
        "template": "letters/guarantee",
        "context": {
            "supplier_name": "Test Company",
            "lot_title": "Test Lot",
            "contact": "Test Contact",
        },
    }

    # Test Russian
    response = client.post(
        "/letters/generate", json=request_data, headers={"X-API-Key": "changeme"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "Гарантийное письмо" in data["html"]

    # Test Kazakh
    response = client.post(
        "/letters/generate?lang=kz",
        json=request_data,
        headers={"X-API-Key": "changeme"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "Кепілдік хат" in data["html"]


def test_invalid_language_fallback():
    """Test that invalid language codes fall back to default"""
    request_data = {"lot_id": 1}

    with patch("main.get_lot") as mock_get_lot:
        mock_get_lot.return_value = {"id": 1, "title": "Test", "price": 100}

        response = client.post(
            "/tldr?lang=invalid", json=request_data, headers={"X-API-Key": "changeme"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["language"] == "ru"  # Should fall back to default
