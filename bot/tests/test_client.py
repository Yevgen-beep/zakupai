from unittest.mock import AsyncMock, patch

import pytest

from bot.client import ZakupaiAPIClient, ZakupaiPipelineClient


class TestZakupaiAPIClient:
    """Тесты для ZakupaiAPIClient"""

    @pytest.fixture
    def client(self):
        """Фикстура для создания тестового клиента"""
        return ZakupaiAPIClient(
            base_url="http://test.zakupai.local", api_key="test-api-key"
        )

    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """Тест успешного health check"""
        mock_response = {"status": "ok", "service": "test"}

        with patch.object(
            client, "_make_request", return_value=mock_response
        ) as mock_request:
            result = await client.health_check()

            mock_request.assert_called_once_with("GET", "/health")
            assert result == mock_response

    @pytest.mark.asyncio
    async def test_health_check_failure(self, client):
        """Тест неудачного health check"""
        with patch.object(
            client, "_make_request", side_effect=Exception("Network error")
        ):
            result = await client.health_check()
            assert result is None

    @pytest.mark.asyncio
    async def test_get_info_success(self, client):
        """Тест успешного получения info"""
        mock_response = {"service": "zakupai", "version": "1.0.0"}

        with patch.object(
            client, "_make_request", return_value=mock_response
        ) as mock_request:
            result = await client.get_info()

            mock_request.assert_called_once_with("GET", "/info")
            assert result == mock_response

    @pytest.mark.asyncio
    async def test_get_tldr(self, client):
        """Тест получения TL;DR"""
        lot_id = "12345"
        mock_response = {"lot_id": lot_id, "title": "Тестовый лот", "price": 1000000}

        with patch.object(
            client, "_make_request", return_value=mock_response
        ) as mock_request:
            result = await client.get_tldr(lot_id)

            mock_request.assert_called_once_with(
                "POST", "/doc/tldr", json_data={"lot_id": lot_id}
            )
            assert result == mock_response

    @pytest.mark.asyncio
    async def test_calculate_vat(self, client):
        """Тест расчёта НДС"""
        amount = 1000.0
        vat_rate = 0.12
        mock_response = {
            "amount": amount,
            "vat_rate": vat_rate,
            "vat_amount": 120.0,
            "total_with_vat": 1120.0,
        }

        with patch.object(
            client, "_make_request", return_value=mock_response
        ) as mock_request:
            result = await client.calculate_vat(amount, vat_rate)

            expected_data = {"amount": amount, "vat_rate": vat_rate}
            mock_request.assert_called_once_with(
                "POST", "/calc/vat", json_data=expected_data
            )
            assert result == mock_response

    @pytest.mark.asyncio
    async def test_get_risk_score(self, client):
        """Тест получения риск-скора"""
        lot_id = "12345"
        mock_response = {
            "lot_id": lot_id,
            "score": 0.3,
            "level": "low",
            "explanation": "Низкий риск",
        }

        with patch.object(
            client, "_make_request", return_value=mock_response
        ) as mock_request:
            result = await client.get_risk_score(lot_id)

            mock_request.assert_called_once_with(
                "POST", "/risk/score", json_data={"lot_id": lot_id}
            )
            assert result == mock_response

    @pytest.mark.asyncio
    async def test_embed_text(self, client):
        """Тест получения эмбеддингов"""
        text = "Тестовый текст"
        model = "test-model"
        mock_response = {"embedding": [0.1, 0.2, 0.3], "model": model, "dimension": 3}

        with patch.object(
            client, "_make_request", return_value=mock_response
        ) as mock_request:
            result = await client.embed_text(text, model)

            expected_data = {"text": text, "model": model}
            mock_request.assert_called_once_with(
                "POST", "/embed", json_data=expected_data
            )
            assert result == mock_response


class TestZakupaiPipelineClient:
    """Тесты для ZakupaiPipelineClient"""

    @pytest.fixture
    def api_client(self):
        """Фикстура для mock API клиента"""
        return AsyncMock(spec=ZakupaiAPIClient)

    @pytest.fixture
    def pipeline_client(self, api_client):
        """Фикстура для pipeline клиента"""
        return ZakupaiPipelineClient(api_client)

    @pytest.mark.asyncio
    async def test_analyze_lot_full_success(self, pipeline_client, api_client):
        """Тест успешного полного анализа лота"""
        lot_id = "12345"

        # Mock responses
        tldr_response = {"lot_id": lot_id, "title": "Тест", "price": 1000000}
        risk_response = {"lot_id": lot_id, "score": 0.3, "level": "low"}
        vat_response = {"vat_amount": 120000, "total_with_vat": 1120000}

        # Настройка mock'ов
        api_client.get_tldr.return_value = tldr_response
        api_client.get_risk_score.return_value = risk_response
        api_client.calculate_vat.return_value = vat_response

        # Выполнение теста
        result = await pipeline_client.analyze_lot_full(lot_id)

        # Проверки
        assert result["lot_id"] == lot_id
        assert result["tldr"] == tldr_response
        assert result["risk"] == risk_response
        assert result["finance"] == vat_response
        assert len(result["errors"]) == 0

        # Проверяем вызовы API
        api_client.get_tldr.assert_called_once_with(lot_id)
        api_client.get_risk_score.assert_called_once_with(lot_id)
        api_client.calculate_vat.assert_called_once_with(1000000)

    @pytest.mark.asyncio
    async def test_analyze_lot_full_with_errors(self, pipeline_client, api_client):
        """Тест анализа лота с ошибками"""
        lot_id = "12345"

        # Mock responses с ошибками
        api_client.get_tldr.side_effect = Exception("TL;DR error")
        api_client.get_risk_score.return_value = {"lot_id": lot_id, "score": 0.5}

        # Выполнение теста
        result = await pipeline_client.analyze_lot_full(lot_id)

        # Проверки
        assert result["lot_id"] == lot_id
        assert result["tldr"] is None
        assert result["risk"]["score"] == 0.5
        assert result["finance"] is None
        assert len(result["errors"]) > 0
        assert "TL;DR error" in str(result["errors"])

    @pytest.mark.asyncio
    async def test_format_analysis_html(self, pipeline_client):
        """Тест форматирования анализа в HTML"""
        analysis = {
            "lot_id": "12345",
            "tldr": {"title": "Тестовый лот", "price": 1000000, "customer": "Тест ТОО"},
            "risk": {"score": 0.3, "explanation": "Низкий риск"},
            "finance": {
                "amount_without_vat": 892857,
                "vat_amount": 107143,
                "total_with_vat": 1000000,
            },
            "errors": ["Тестовая ошибка"],
        }

        html = pipeline_client._format_analysis_html(analysis)

        # Проверяем содержимое HTML
        assert "12345" in html
        assert "Тестовый лот" in html
        assert "1000000" in html
        assert "Низкий риск" in html
        assert "Тестовая ошибка" in html
        assert "<html>" in html
        assert "</html>" in html


@pytest.mark.asyncio
async def test_make_request_timeout():
    """Тест обработки таймаута запроса"""
    client = ZakupaiAPIClient("http://test.local", "test-key")

    with patch("aiohttp.ClientSession.request") as mock_request:
        mock_request.side_effect = TimeoutError()

        with pytest.raises(Exception, match="Превышено время ожидания"):
            await client._make_request("GET", "/test")


@pytest.mark.asyncio
async def test_make_request_rate_limit():
    """Тест обработки rate limit (429)"""
    client = ZakupaiAPIClient("http://test.local", "test-key")

    mock_response = AsyncMock()
    mock_response.status = 429

    with patch("aiohttp.ClientSession.request") as mock_request:
        mock_request.return_value.__aenter__.return_value = mock_response

        with pytest.raises(Exception, match="Превышен лимит запросов"):
            await client._make_request("GET", "/test")


@pytest.mark.asyncio
async def test_make_request_unauthorized():
    """Тест обработки 401 Unauthorized"""
    client = ZakupaiAPIClient("http://test.local", "test-key")

    mock_response = AsyncMock()
    mock_response.status = 401

    with patch("aiohttp.ClientSession.request") as mock_request:
        mock_request.return_value.__aenter__.return_value = mock_response

        with pytest.raises(Exception, match="Неверный API ключ"):
            await client._make_request("GET", "/test")
