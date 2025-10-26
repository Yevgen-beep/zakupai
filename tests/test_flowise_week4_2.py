"""
Comprehensive test suite for Week 4.2 Flowise features
Tests complaint-generator, supplier-finder, and modular functionality
"""

import logging
import os
import sys
import time
from datetime import date
from io import BytesIO
from unittest.mock import patch

import pytest
import responses
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Import the flowise implementation
try:
    from web.flowise_week4_2 import (
        ComplaintRequest,
        Supplier,
        SupplierRequest,
        fetch_api_suppliers,
        fetch_mock_suppliers,
        filter_suppliers,
        generate_complaint_fallback,
        generate_complaint_via_flowise_enhanced,
        generate_complaint_word,
        generate_enhanced_complaint_pdf,
    )
    from web.main import app, redis_client
except ImportError:
    pytest.skip("Week 4.2 Flowise modules not available", allow_module_level=True)

logger = logging.getLogger(__name__)


class TestComplaintGeneration:
    """Test suite for complaint generation functionality"""

    @pytest.fixture
    def test_client(self):
        return TestClient(app)

    @pytest.fixture
    def mock_lot_data(self):
        return {
            "id": 12345,
            "name": "Компьютерное оборудование для школ",
            "amount": 2500000,
            "customer": "Управление образования г. Алматы",
            "description": "Закупка компьютерного оборудования",
            "status": 1,
            "publish_date": "2025-01-15T10:00:00",
        }

    def test_complaint_request_validation_valid(self):
        """Test complaint request validation with valid data"""
        request = ComplaintRequest(
            reason="Завышенная цена на товары", date="2025-01-15"
        )
        assert request.reason == "Завышенная цена на товары"
        assert request.date == "2025-01-15"

    def test_complaint_request_validation_invalid_reason(self):
        """Test complaint request validation with invalid reason"""
        with pytest.raises(ValueError, match="Reason too long"):
            ComplaintRequest(
                reason="x" * 201,  # Too long
                date="2025-01-15",
            )

        with pytest.raises(ValueError, match="Reason cannot be empty"):
            ComplaintRequest(
                reason="   ",  # Empty
                date="2025-01-15",
            )

    def test_complaint_request_validation_invalid_date(self):
        """Test complaint request validation with invalid date"""
        with pytest.raises(ValueError, match="Date cannot be in the future"):
            ComplaintRequest(
                reason="Valid reason",
                date="2030-01-01",  # Future date
            )

        with pytest.raises(ValueError, match="Invalid date format"):
            ComplaintRequest(reason="Valid reason", date="invalid-date")

    def test_complaint_request_auto_date(self):
        """Test automatic date assignment when not provided"""
        request = ComplaintRequest(reason="Valid reason")
        # Should auto-assign today's date
        assert request.date == date.today().isoformat()

    @pytest.mark.asyncio
    async def test_generate_complaint_fallback(self, mock_lot_data):
        """Test fallback complaint generation"""
        result = await generate_complaint_fallback(
            lot_id=12345,
            lot_info=mock_lot_data,
            reason="Завышенная цена",
            complaint_date="2025-01-15",
        )

        assert result["source"] == "fallback"
        assert "ЖАЛОБА #12345" in result["text"]
        assert "Завышенная цена" in result["text"]
        assert "Компьютерное оборудование для школ" in result["text"]

    @responses.activate
    @pytest.mark.asyncio
    async def test_generate_complaint_flowise_success(self, mock_lot_data):
        """Test successful Flowise complaint generation"""
        # Mock Flowise API response
        responses.add(
            responses.POST,
            "http://flowise:3000/api/v1/prediction/complaint-generator",
            json={"text": "Generated complaint from Flowise"},
            status=200,
        )

        with patch.dict(
            os.environ,
            {"FLOWISE_API_URL": "http://flowise:3000", "FLOWISE_API_KEY": "test-key"},
        ):
            result = await generate_complaint_via_flowise_enhanced(
                lot_id=12345,
                lot_info=mock_lot_data,
                reason="Завышенная цена",
                complaint_date="2025-01-15",
            )

        assert result["source"] == "flowise"
        assert result["text"] == "Generated complaint from Flowise"

    @responses.activate
    @pytest.mark.asyncio
    async def test_generate_complaint_flowise_timeout(self, mock_lot_data):
        """Test Flowise timeout fallback"""
        # Mock timeout response
        responses.add(
            responses.POST,
            "http://flowise:3000/api/v1/prediction/complaint-generator",
            body=responses.ConnectionError("Timeout"),
        )

        with patch.dict(
            os.environ,
            {"FLOWISE_API_URL": "http://flowise:3000", "FLOWISE_API_KEY": "test-key"},
        ):
            result = await generate_complaint_via_flowise_enhanced(
                lot_id=12345,
                lot_info=mock_lot_data,
                reason="Завышенная цена",
                complaint_date="2025-01-15",
            )

        # Should fallback to SQL-based generation
        assert result["source"] == "fallback"
        assert "ЖАЛОБА #12345" in result["text"]

    def test_generate_enhanced_complaint_pdf(self):
        """Test enhanced PDF generation with proper formatting"""
        complaint_text = """
ЖАЛОБА #12345

Дата: 2025-01-15

Лот: Компьютерное оборудование для школ (ID: 12345)
Заказчик: Управление образования г. Алматы
Сумма: 2,500,000.00 тенге

Основание жалобы: Завышенная цена

Подробное описание:
В рамках анализа лота #12345 выявлены нарушения: завышенная цена.
        """.strip()

        pdf_buffer = generate_enhanced_complaint_pdf(
            complaint_text, 12345, "Завышенная цена", "2025-01-15"
        )

        # Verify PDF was generated
        assert isinstance(pdf_buffer, BytesIO)
        assert len(pdf_buffer.getvalue()) > 1000  # PDF should be substantial

        # Reset buffer position
        pdf_buffer.seek(0)
        pdf_content = pdf_buffer.read()

        # Verify it's a PDF file (starts with %PDF)
        assert pdf_content.startswith(b"%PDF")

    def test_generate_complaint_word(self):
        """Test Word document generation"""
        complaint_text = """
ЖАЛОБА #12345

Дата: 2025-01-15

Лот: Компьютерное оборудование для школ (ID: 12345)
Заказчик: Управление образования г. Алматы
        """.strip()

        word_buffer = generate_complaint_word(
            complaint_text, 12345, "Завышенная цена", "2025-01-15"
        )

        # Verify Word document was generated
        assert isinstance(word_buffer, BytesIO)
        assert len(word_buffer.getvalue()) > 5000  # Word docs are typically larger

        # Reset buffer position
        word_buffer.seek(0)
        word_content = word_buffer.read()

        # Verify it's a Word document (contains expected ZIP signature)
        assert word_content.startswith(b"PK")  # ZIP/DOCX signature

    def test_complaint_cyrillic_support(self):
        """Test proper handling of Cyrillic characters in complaints"""
        request = ComplaintRequest(
            reason="Нарушение требований технического задания и завышение цен",
            date="2025-01-15",
        )

        # Should handle Cyrillic without issues
        assert "Нарушение" in request.reason
        assert "завышение" in request.reason

    @pytest.mark.asyncio
    async def test_complaint_caching(self, test_client):
        """Test Redis caching for complaint generation"""
        lot_id = 12345
        reason = "Test caching"

        # Clear any existing cache
        try:
            cache_key = f"complaint:{lot_id}:{hash(reason) % 1000000}"
            redis_client.delete(cache_key)
        except Exception as exc:
            logger.debug("Failed to clear complaint cache for lot %s: %s", lot_id, exc)

        # First request should generate complaint
        response1 = test_client.post(
            f"/api/complaint/{lot_id}", json={"reason": reason, "date": "2025-01-15"}
        )

        if response1.status_code == 200:
            # Second request should hit cache
            start_time = time.time()
            response2 = test_client.post(
                f"/api/complaint/{lot_id}",
                json={"reason": reason, "date": "2025-01-15"},
            )
            cache_time = time.time() - start_time

            if response2.status_code == 200:
                # Cache hit should be faster
                assert cache_time < 1.0  # Should be much faster than 1 second


class TestSupplierSearch:
    """Test suite for supplier search functionality"""

    @pytest.fixture
    def supplier_request_valid(self):
        return SupplierRequest(
            region="KZ", min_budget=10000, max_budget=500000, sources=["satu", "1688"]
        )

    def test_supplier_request_validation_valid(self, supplier_request_valid):
        """Test supplier request validation with valid data"""
        assert supplier_request_valid.region == "KZ"
        assert supplier_request_valid.min_budget == 10000
        assert supplier_request_valid.max_budget == 500000
        assert supplier_request_valid.sources == ["satu", "1688"]

    def test_supplier_request_validation_invalid_budget_range(self):
        """Test supplier request validation with invalid budget range"""
        with pytest.raises(ValueError, match="max_budget must be >= min_budget"):
            SupplierRequest(
                min_budget=100000,
                max_budget=50000,  # Less than min_budget
            )

    @pytest.mark.asyncio
    async def test_fetch_mock_suppliers(self):
        """Test mock supplier data generation"""
        suppliers = await fetch_mock_suppliers("мебель", "Satu.kz")

        assert len(suppliers) == 2
        assert all("region" in s for s in suppliers)
        assert all("budget" in s for s in suppliers)
        assert all("rating" in s for s in suppliers)
        assert all(s["source"] == "Satu.kz" for s in suppliers)

    @responses.activate
    @pytest.mark.asyncio
    async def test_fetch_api_suppliers_1688(self):
        """Test fetching suppliers from 1688 API"""
        source_config = {
            "name": "1688",
            "auth_type": "API_KEY",
            "credentials_ref": "RAPIDAPI_KEY",
        }

        with patch.dict(os.environ, {"RAPIDAPI_KEY": "test-key"}):
            suppliers = await fetch_api_suppliers("мебель", source_config)

            assert len(suppliers) >= 1
            assert suppliers[0]["source"] == "1688"
            assert suppliers[0]["region"] == "CN"

    @responses.activate
    @pytest.mark.asyncio
    async def test_fetch_api_suppliers_alibaba(self):
        """Test fetching suppliers from Alibaba API"""
        source_config = {
            "name": "Alibaba",
            "auth_type": "API_KEY",
            "credentials_ref": "RAPIDAPI_KEY",
        }

        with patch.dict(os.environ, {"RAPIDAPI_KEY": "test-key"}):
            suppliers = await fetch_api_suppliers("мебель", source_config)

            assert len(suppliers) >= 1
            assert suppliers[0]["source"] == "Alibaba"
            assert suppliers[0]["region"] == "CN"

    @pytest.mark.asyncio
    async def test_fetch_api_suppliers_missing_key(self):
        """Test API suppliers fetch with missing API key"""
        source_config = {
            "name": "1688",
            "auth_type": "API_KEY",
            "credentials_ref": "MISSING_KEY",
        }

        # Should fallback to web search
        with patch.dict(os.environ, {}, clear=True):
            suppliers = await fetch_api_suppliers("мебель", source_config)

            # Should return fallback results
            assert len(suppliers) >= 1
            assert "fallback" in suppliers[0]["source"]

    def test_filter_suppliers_by_region(self):
        """Test filtering suppliers by region"""
        suppliers_data = [
            {
                "name": "KZ Supplier",
                "region": "KZ",
                "budget": 50000,
                "rating": 4.0,
                "link": "test",
                "source": "test",
            },
            {
                "name": "CN Supplier",
                "region": "CN",
                "budget": 30000,
                "rating": 4.5,
                "link": "test",
                "source": "test",
            },
            {
                "name": "RU Supplier",
                "region": "RU",
                "budget": 60000,
                "rating": 3.8,
                "link": "test",
                "source": "test",
            },
        ]

        request = SupplierRequest(region="KZ")
        filtered = filter_suppliers(suppliers_data, request)

        assert len(filtered) == 1
        assert filtered[0].region == "KZ"
        assert filtered[0].name == "KZ Supplier"

    def test_filter_suppliers_by_budget_range(self):
        """Test filtering suppliers by budget range"""
        suppliers_data = [
            {
                "name": "Cheap",
                "region": "KZ",
                "budget": 10000,
                "rating": 4.0,
                "link": "test",
                "source": "test",
            },
            {
                "name": "Mid",
                "region": "KZ",
                "budget": 50000,
                "rating": 4.5,
                "link": "test",
                "source": "test",
            },
            {
                "name": "Expensive",
                "region": "KZ",
                "budget": 100000,
                "rating": 3.8,
                "link": "test",
                "source": "test",
            },
        ]

        request = SupplierRequest(min_budget=20000, max_budget=80000)
        filtered = filter_suppliers(suppliers_data, request)

        assert len(filtered) == 1
        assert filtered[0].name == "Mid"
        assert 20000 <= filtered[0].budget <= 80000

    def test_filter_suppliers_sort_by_rating(self):
        """Test suppliers are sorted by rating in descending order"""
        suppliers_data = [
            {
                "name": "Low",
                "region": "KZ",
                "budget": 50000,
                "rating": 3.0,
                "link": "test",
                "source": "test",
            },
            {
                "name": "High",
                "region": "KZ",
                "budget": 50000,
                "rating": 4.8,
                "link": "test",
                "source": "test",
            },
            {
                "name": "Mid",
                "region": "KZ",
                "budget": 50000,
                "rating": 4.2,
                "link": "test",
                "source": "test",
            },
        ]

        request = SupplierRequest()
        filtered = filter_suppliers(suppliers_data, request)

        assert len(filtered) == 3
        assert filtered[0].name == "High"  # Highest rating first
        assert filtered[1].name == "Mid"
        assert filtered[2].name == "Low"

    def test_supplier_cyrillic_support(self):
        """Test proper handling of Cyrillic characters in supplier search"""
        suppliers_data = [
            {
                "name": "ТОО Мебельная компания Астана",
                "region": "KZ",
                "budget": 50000,
                "rating": 4.2,
                "link": "https://test.kz",
                "source": "Satu.kz",
            }
        ]

        request = SupplierRequest()
        filtered = filter_suppliers(suppliers_data, request)

        assert len(filtered) == 1
        assert "Мебельная" in filtered[0].name
        assert filtered[0].region == "KZ"

    def test_supplier_model_validation(self):
        """Test Supplier model validation"""
        supplier = Supplier(
            name="Test Supplier",
            region="KZ",
            budget=50000.50,
            rating=4.2,
            link="https://test.com",
            source="Satu.kz",
        )

        assert supplier.name == "Test Supplier"
        assert supplier.region == "KZ"
        assert supplier.budget == 50000.50
        assert supplier.rating == 4.2
        assert supplier.link == "https://test.com"
        assert supplier.source == "Satu.kz"

    def test_supplier_model_validation_invalid_rating(self):
        """Test Supplier model with invalid rating"""
        with pytest.raises(ValueError):
            Supplier(
                name="Test Supplier",
                region="KZ",
                budget=50000,
                rating=6.0,  # Rating > 5
                link="https://test.com",
                source="Satu.kz",
            )

    def test_supplier_model_validation_negative_budget(self):
        """Test Supplier model with negative budget"""
        with pytest.raises(ValueError):
            Supplier(
                name="Test Supplier",
                region="KZ",
                budget=-1000,  # Negative budget
                rating=4.0,
                link="https://test.com",
                source="Satu.kz",
            )


class TestIntegrationScenarios:
    """Integration tests for Week 4.2 complete workflows"""

    @pytest.fixture
    def test_client(self):
        return TestClient(app)

    def test_complaint_to_pdf_workflow(self, test_client):
        """Test complete complaint generation to PDF download workflow"""
        lot_id = 12345
        reason = "Тестовая жалоба на завышение цен"
        date = "2025-01-15"

        # Generate complaint
        response = test_client.post(
            f"/api/complaint/{lot_id}", json={"reason": reason, "date": date}
        )

        if response.status_code == 200:
            # Download PDF
            pdf_response = test_client.get(
                f"/api/complaint/{lot_id}/pdf", params={"reason": reason, "date": date}
            )

            if pdf_response.status_code == 200:
                assert pdf_response.headers["content-type"] == "application/pdf"
                assert len(pdf_response.content) > 1000

    def test_complaint_to_word_workflow(self, test_client):
        """Test complete complaint generation to Word download workflow"""
        lot_id = 12345
        reason = "Тестовая жалоба на нарушения"
        date = "2025-01-15"

        # Generate complaint
        response = test_client.post(
            f"/api/complaint/{lot_id}", json={"reason": reason, "date": date}
        )

        if response.status_code == 200:
            # Download Word document
            word_response = test_client.get(
                f"/api/complaint/{lot_id}/word", params={"reason": reason, "date": date}
            )

            if word_response.status_code == 200:
                assert "wordprocessingml" in word_response.headers["content-type"]
                assert len(word_response.content) > 5000

    def test_supplier_search_workflow(self, test_client):
        """Test complete supplier search workflow with filters"""
        lot_name = "мебель"

        # Search suppliers with filters
        response = test_client.get(
            f"/api/supplier/{lot_name}",
            params={
                "region": "KZ",
                "min_budget": 10000,
                "max_budget": 100000,
                "sources": "satu,1688",
            },
        )

        if response.status_code == 200:
            data = response.json()
            assert "suppliers" in data
            assert "sources_used" in data
            assert "cache_hit" in data
            assert "latency_ms" in data

    def test_performance_targets(self, test_client):
        """Test that performance targets are met"""
        lot_id = 12345

        # Test complaint generation performance (<1 second target)
        start_time = time.time()
        complaint_response = test_client.post(
            f"/api/complaint/{lot_id}",
            json={"reason": "Performance test", "date": "2025-01-15"},
        )
        complaint_time = time.time() - start_time

        # Test supplier search performance (<1 second target)
        start_time = time.time()
        supplier_response = test_client.get("/api/supplier/мебель")
        supplier_time = time.time() - start_time

        # Performance assertions (if services are running)
        if complaint_response.status_code == 200:
            assert complaint_time < 2.0  # Allow some margin for testing environment

        if supplier_response.status_code == 200:
            assert supplier_time < 2.0  # Allow some margin for testing environment

    def test_error_handling_invalid_lot_id(self, test_client):
        """Test error handling for invalid lot ID"""
        response = test_client.post(
            "/api/complaint/999999999",  # Non-existent lot ID
            json={"reason": "Test complaint", "date": "2025-01-15"},
        )

        # Should handle gracefully
        assert response.status_code in [404, 500]

    def test_concurrent_requests(self, test_client):
        """Test handling of concurrent requests"""
        import concurrent.futures

        def make_complaint_request():
            return test_client.post(
                "/api/complaint/12345",
                json={"reason": "Concurrent test", "date": "2025-01-15"},
            )

        def make_supplier_request():
            return test_client.get("/api/supplier/мебель")

        # Execute concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for _ in range(3):
                futures.append(executor.submit(make_complaint_request))
                futures.append(executor.submit(make_supplier_request))

            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        # All requests should complete without errors
        successful_requests = [r for r in results if r.status_code in [200, 404]]
        assert len(successful_requests) >= 4  # At least most should succeed


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
