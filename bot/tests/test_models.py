from datetime import datetime

import pytest
from pydantic import ValidationError

from bot.models import (  # Embedding API Models; API Response Models; Analysis Models; Risk Engine Models; Doc Service Models; Calc Service Models; Utility functions
    EmbedRequest,
    HealthResponse,
    InfoResponse,
    LetterGenerateRequest,
    LotAnalysisResult,
    MarginRequest,
    PenaltyRequest,
    PipelineStatus,
    RiskLevel,
    RiskScoreRequest,
    RiskScoreResponse,
    SearchRequest,
    SearchResult,
    TLDRRequest,
    TLDRResponse,
    VATRequest,
    VATResponse,
    calculate_risk_level,
    extract_lot_id_from_url,
    format_currency,
    get_risk_level_emoji,
    validate_lot_id,
)


class TestAPIResponseModels:
    """Тесты моделей ответов API"""

    def test_health_response_valid(self):
        """Тест валидной модели HealthResponse"""
        data = {"status": "ok"}
        response = HealthResponse(**data)

        assert response.status == "ok"
        assert response.timestamp is None
        assert response.service is None

    def test_info_response_valid(self):
        """Тест валидной модели InfoResponse"""
        data = {"service": "zakupai-bot", "version": "1.0.0", "environment": "test"}
        response = InfoResponse(**data)

        assert response.service == "zakupai-bot"
        assert response.version == "1.0.0"
        assert response.environment == "test"


class TestDocServiceModels:
    """Тесты моделей doc-service"""

    def test_tldr_request_valid(self):
        """Тест валидного TLDRRequest"""
        data = {"lot_id": "12345"}
        request = TLDRRequest(**data)

        assert request.lot_id == "12345"

    def test_tldr_request_empty_lot_id(self):
        """Тест TLDRRequest с пустым lot_id"""
        with pytest.raises(ValidationError):
            TLDRRequest(lot_id="")

    def test_tldr_response_valid(self):
        """Тест валидного TLDRResponse"""
        data = {
            "lot_id": "12345",
            "title": "Тестовый лот",
            "price": 1000000.0,
            "customer": "ТОО 'Тест'",
        }
        response = TLDRResponse(**data)

        assert response.lot_id == "12345"
        assert response.title == "Тестовый лот"
        assert response.price == 1000000.0
        assert response.currency == "KZT"  # default value

    def test_letter_generate_request_valid(self):
        """Тест валидного LetterGenerateRequest"""
        data = {
            "template": "offer_letter",
            "context": {"company": "ТОО 'Тест'", "amount": 1000000},
        }
        request = LetterGenerateRequest(**data)

        assert request.template == "offer_letter"
        assert request.context["company"] == "ТОО 'Тест'"


class TestRiskEngineModels:
    """Тесты моделей risk-engine"""

    def test_risk_score_request_valid(self):
        """Тест валидного RiskScoreRequest"""
        data = {"lot_id": "12345"}
        request = RiskScoreRequest(**data)

        assert request.lot_id == "12345"

    def test_risk_score_response_valid(self):
        """Тест валидного RiskScoreResponse"""
        data = {
            "lot_id": "12345",
            "score": 0.3,
            "level": RiskLevel.LOW,
            "explanation": "Низкий риск",
            "evaluated_at": datetime.now(),
        }
        response = RiskScoreResponse(**data)

        assert response.lot_id == "12345"
        assert response.score == 0.3
        assert response.level == RiskLevel.LOW

    def test_risk_score_invalid_range(self):
        """Тест невалидного диапазона риск-скора"""
        data = {
            "lot_id": "12345",
            "score": 1.5,  # Больше 1.0
            "level": RiskLevel.HIGH,
            "evaluated_at": datetime.now(),
        }

        with pytest.raises(ValidationError, match="between 0.0 and 1.0"):
            RiskScoreResponse(**data)


class TestCalcServiceModels:
    """Тесты моделей calc-service"""

    def test_vat_request_valid(self):
        """Тест валидного VATRequest"""
        data = {"amount": 1000.0, "vat_rate": 0.12}
        request = VATRequest(**data)

        assert request.amount == 1000.0
        assert request.vat_rate == 0.12

    def test_vat_request_negative_amount(self):
        """Тест VATRequest с отрицательной суммой"""
        with pytest.raises(ValidationError, match="greater than 0"):
            VATRequest(amount=-100.0)

    def test_vat_response_valid(self):
        """Тест валидного VATResponse"""
        data = {
            "amount": 1000.0,
            "vat_rate": 0.12,
            "vat_amount": 120.0,
            "amount_without_vat": 892.86,
            "total_with_vat": 1000.0,
        }
        response = VATResponse(**data)

        assert response.amount == 1000.0
        assert response.vat_amount == 120.0

    def test_margin_request_valid(self):
        """Тест валидного MarginRequest"""
        data = {"cost_price": 800.0, "selling_price": 1000.0, "quantity": 10}
        request = MarginRequest(**data)

        assert request.cost_price == 800.0
        assert request.selling_price == 1000.0
        assert request.quantity == 10

    def test_penalty_request_valid(self):
        """Тест валидного PenaltyRequest"""
        data = {"contract_amount": 1000000.0, "days_overdue": 30, "penalty_rate": 0.1}
        request = PenaltyRequest(**data)

        assert request.contract_amount == 1000000.0
        assert request.days_overdue == 30
        assert request.penalty_rate == 0.1


class TestEmbeddingModels:
    """Тесты моделей embedding-api"""

    def test_embed_request_valid(self):
        """Тест валидного EmbedRequest"""
        data = {"text": "Тестовый текст", "model": "test-model"}
        request = EmbedRequest(**data)

        assert request.text == "Тестовый текст"
        assert request.model == "test-model"

    def test_embed_request_empty_text(self):
        """Тест EmbedRequest с пустым текстом"""
        with pytest.raises(ValidationError, match="at least 1 character"):
            EmbedRequest(text="")

    def test_search_request_valid(self):
        """Тест валидного SearchRequest"""
        data = {"query": "Поисковый запрос", "limit": 5, "threshold": 0.8}
        request = SearchRequest(**data)

        assert request.query == "Поисковый запрос"
        assert request.limit == 5
        assert request.threshold == 0.8

    def test_search_result_valid(self):
        """Тест валидного SearchResult"""
        data = {
            "doc_id": "doc123",
            "content": "Содержимое документа",
            "score": 0.95,
            "metadata": {"category": "tender"},
        }
        result = SearchResult(**data)

        assert result.doc_id == "doc123"
        assert result.score == 0.95
        assert result.metadata["category"] == "tender"


class TestAnalysisModels:
    """Тесты моделей анализа"""

    def test_lot_analysis_result_valid(self):
        """Тест валидного LotAnalysisResult"""
        data = {"lot_id": "12345", "errors": [], "analyzed_at": datetime.now()}
        result = LotAnalysisResult(**data)

        assert result.lot_id == "12345"
        assert result.errors == []
        assert result.tldr is None
        assert result.risk is None

    def test_pipeline_status_valid(self):
        """Тест валидного PipelineStatus"""
        data = {
            "lot_id": "12345",
            "stage": "tldr",
            "status": "ok",
            "progress": 0.5,
            "started_at": datetime.now(),
        }
        status = PipelineStatus(**data)

        assert status.lot_id == "12345"
        assert status.stage == "tldr"
        assert status.progress == 0.5


class TestUtilityFunctions:
    """Тесты вспомогательных функций"""

    def test_validate_lot_id_valid(self):
        """Тест валидации правильного ID лота"""
        assert validate_lot_id("12345") is True
        assert validate_lot_id("999999999") is True

    def test_validate_lot_id_invalid(self):
        """Тест валидации неправильного ID лота"""
        assert validate_lot_id("") is False
        assert validate_lot_id("abc123") is False
        assert validate_lot_id("12a34") is False

    def test_extract_lot_id_from_url(self):
        """Тест извлечения ID лота из URL"""
        urls = [
            ("https://goszakup.gov.kz/ru/announce/index/12345", "12345"),
            ("http://example.com/lot/67890", "67890"),
            ("https://site.com/page?lot_id=11111", "11111"),
            ("https://site.com/page?id=22222", "22222"),
            ("invalid-url", None),
            ("https://site.com/no-id", None),
        ]

        for url, expected_id in urls:
            result = extract_lot_id_from_url(url)
            assert result == expected_id, f"Failed for URL: {url}"

    def test_calculate_risk_level(self):
        """Тест расчёта уровня риска"""
        assert calculate_risk_level(0.1) == RiskLevel.LOW
        assert calculate_risk_level(0.3) == RiskLevel.MEDIUM
        assert calculate_risk_level(0.5) == RiskLevel.MEDIUM
        assert calculate_risk_level(0.7) == RiskLevel.HIGH
        assert calculate_risk_level(0.9) == RiskLevel.HIGH

    def test_format_currency(self):
        """Тест форматирования валюты"""
        assert format_currency(1000000) == "1,000,000 тг"
        assert format_currency(1234.56, "USD") == "1,234.56 USD"
        assert format_currency(500000.0) == "500,000 тг"

    def test_get_risk_level_emoji(self):
        """Тест получения эмодзи для уровня риска"""
        assert get_risk_level_emoji(RiskLevel.LOW) == "🟢"
        assert get_risk_level_emoji(RiskLevel.MEDIUM) == "🟡"
        assert get_risk_level_emoji(RiskLevel.HIGH) == "🔴"


class TestRiskLevelEnum:
    """Тесты enum RiskLevel"""

    def test_risk_level_values(self):
        """Тест значений enum RiskLevel"""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"

    def test_risk_level_string_representation(self):
        """Тест строкового представления RiskLevel"""
        assert str(RiskLevel.LOW) == "low"
        assert str(RiskLevel.MEDIUM) == "medium"
        assert str(RiskLevel.HIGH) == "high"


class TestValidators:
    """Тесты валидаторов Pydantic"""

    def test_score_range_validator(self):
        """Тест валидатора диапазона скоров"""
        # Валидные значения
        data = {
            "lot_id": "12345",
            "score": 0.5,
            "level": RiskLevel.MEDIUM,
            "evaluated_at": datetime.now(),
        }
        response = RiskScoreResponse(**data)
        assert response.score == 0.5

        # Граничные значения
        data["score"] = 0.0
        response = RiskScoreResponse(**data)
        assert response.score == 0.0

        data["score"] = 1.0
        response = RiskScoreResponse(**data)
        assert response.score == 1.0

    def test_positive_amount_validator(self):
        """Тест валидатора положительных сумм"""
        # Валидные значения
        request = VATRequest(amount=1000.0)
        assert request.amount == 1000.0

        # Невалидные значения
        with pytest.raises(ValidationError):
            VATRequest(amount=0.0)

        with pytest.raises(ValidationError):
            VATRequest(amount=-100.0)
