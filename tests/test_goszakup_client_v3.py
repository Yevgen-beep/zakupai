"""
Тесты для универсального клиента API госзакупок v3
"""

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "bot"))

from goszakup_client_extensions import (
    ExportFormat,
    GoszakupClientFull,
    create_monitoring_callback,
)
from goszakup_client_v3 import (
    AsyncCache,
    ContractFiltersInput,
    ContractResult,
    ContractStatus,
    GoszakupClient,
    LotResult,
    LotsFiltersInput,
    LotStatus,
    RetryConfig,
    SubjectResult,
    SubjectType,
    TradeMethod,
    with_retry,
)

TEST_API_TOKEN = os.getenv("GOSZAKUP_V3_TEST_TOKEN", "dummy-token-for-tests")  # nosec B105


@pytest.fixture
async def client():
    """Фикстура для создания клиента"""
    async with GoszakupClient(token=TEST_API_TOKEN) as client:
        yield client


@pytest.fixture
async def client_full():
    """Фикстура для полного клиента"""
    async with GoszakupClientFull(token=TEST_API_TOKEN) as client:
        yield client


@pytest.fixture
def sample_lot_data():
    """Пример данных лота"""
    return {
        "id": "123456",
        "lotNumber": "LOT-001",
        "nameRu": "Поставка компьютерного оборудования",
        "nameKz": "Компьютерлік жабдықтарды жеткізу",
        "descriptionRu": "Поставка компьютеров и периферии",
        "count": 10.0,
        "amount": 5000000.0,
        "customerNameRu": "ТОО Тестовая компания",
        "customerBin": "123456789012",
        "publishDate": "2024-01-15T10:00:00",
        "endDate": "2024-02-15T18:00:00",
        "RefLotsStatus": {"nameRu": "Прием заявок"},
        "TrdBuy": {
            "id": "TB-001",
            "numberAnno": "ANNO-001",
            "nameRu": "Объявление о закупке оборудования",
            "orgNameRu": "ТОО Тестовая компания",
            "orgBin": "123456789012",
            "RefTradeMethods": {"nameRu": "Открытый конкурс"},
        },
    }


@pytest.fixture
def sample_contract_data():
    """Пример данных контракта"""
    return {
        "id": "CONTRACT-123",
        "contractNumber": "CONT-2024-001",
        "contractNumberSys": "SYS-001",
        "supplierBiin": "987654321098",
        "supplierNameRu": "ТОО Поставщик",
        "customerBin": "123456789012",
        "customerNameRu": "ТОО Заказчик",
        "contractSum": 3000000.0,
        "signDate": "2024-01-20T12:00:00",
        "startDate": "2024-02-01T00:00:00",
        "endDate": "2024-03-01T23:59:59",
        "RefContractStatus": {"nameRu": "Действующий"},
        "Acts": [
            {
                "id": "ACT-001",
                "actNumber": "ACT-2024-001",
                "actSum": 1500000.0,
                "signDate": "2024-02-15T15:00:00",
            }
        ],
    }


class TestGoszakupClient:
    """Тесты основного клиента"""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Тест инициализации клиента"""
        client = GoszakupClient(token=TEST_API_TOKEN)

        assert client.token == TEST_API_TOKEN
        assert client.graphql_url == "https://ows.goszakup.gov.kz/v3/graphql"
        assert client.cache_enabled is True
        assert client.retry_config.max_retries == 3

        await client.close()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Тест контекстного менеджера"""
        async with GoszakupClient(token=TEST_API_TOKEN) as client:
            assert client._session is not None

        assert client._session.closed

    def test_generate_query(self, client):
        """Тест генерации GraphQL запроса"""
        filters = {"nameRu": "тест", "amount": 1000000}
        fields = ["id", "lotNumber", "nameRu"]

        query = client._generate_query("Lots", filters, fields, 10)

        assert "query SearchLots" in query["query"]
        assert "$filter: LotsFiltersInput" in query["query"]
        assert "id lotNumber nameRu" in query["query"]
        assert query["variables"]["filter"] == filters
        assert query["variables"]["limit"] == 10

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.post")
    async def test_make_request_success(self, mock_post, client):
        """Тест успешного выполнения запроса"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "data": {"Lots": [{"id": "123", "lotNumber": "LOT-001"}]}
        }
        mock_post.return_value.__aenter__.return_value = mock_response

        query = {"query": "test query", "variables": {}}
        result = await client._make_request(query)

        assert "data" in result
        assert "Lots" in result["data"]

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.post")
    async def test_make_request_graphql_error(self, mock_post, client):
        """Тест обработки ошибок GraphQL"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"errors": [{"message": "Field not found"}]}
        mock_post.return_value.__aenter__.return_value = mock_response

        query = {"query": "test query", "variables": {}}

        with pytest.raises(Exception, match="GraphQL errors"):
            await client._make_request(query)

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.post")
    async def test_make_request_auth_error(self, mock_post, client):
        """Тест обработки ошибок авторизации"""
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text.return_value = "Unauthorized"
        mock_post.return_value.__aenter__.return_value = mock_response

        query = {"query": "test query", "variables": {}}

        with pytest.raises(Exception, match="authorization failed"):
            await client._make_request(query)

    def test_clean_filters(self, client):
        """Тест очистки фильтров"""
        filters = LotsFiltersInput(
            nameRu="тест", amount=None, customerBin=["123456789012"], publishDate=None
        )

        clean = client._clean_filters(filters)

        assert "nameRu" in clean
        assert "customerBin" in clean
        assert "amount" not in clean
        assert "publishDate" not in clean

    def test_parse_lot_result(self, client, sample_lot_data):
        """Тест парсинга результата лота"""
        result = client._parse_lot_result(sample_lot_data)

        assert isinstance(result, LotResult)
        assert result.id == "123456"
        assert result.lotNumber == "LOT-001"
        assert result.nameRu == "Поставка компьютерного оборудования"
        assert result.amount == 5000000.0
        assert result.customerNameRu == "ТОО Тестовая компания"
        assert result.status == "Прием заявок"
        assert result.tradeMethod == "Открытый конкурс"

    def test_parse_contract_result(self, client, sample_contract_data):
        """Тест парсинга результата контракта"""
        result = client._parse_contract_result(sample_contract_data)

        assert isinstance(result, ContractResult)
        assert result.id == "CONTRACT-123"
        assert result.contractNumber == "CONT-2024-001"
        assert result.supplierNameRu == "ТОО Поставщик"
        assert result.contractSum == 3000000.0
        assert result.status == "Действующий"
        assert result.acts is not None
        assert len(result.acts) == 1


class TestFilters:
    """Тесты фильтров"""

    def test_lots_filters_creation(self):
        """Тест создания фильтров для лотов"""
        filters = LotsFiltersInput(
            nameRu="компьютер",
            customerBin=["123456789012"],
            amountFrom=1000000,
            amountTo=5000000,
            refLotStatusId=[LotStatus.PUBLISHED.value],
            refTradeMethodsId=[TradeMethod.OPEN_TENDER.value],
        )

        assert filters.nameRu == "компьютер"
        assert filters.customerBin == ["123456789012"]
        assert filters.amountFrom == 1000000
        assert filters.amountTo == 5000000
        assert filters.refLotStatusId == [2]
        assert filters.refTradeMethodsId == [1]

    def test_contracts_filters_creation(self):
        """Тест создания фильтров для контрактов"""
        filters = ContractFiltersInput(
            supplierBiin=["987654321098"],
            contractSumFrom=500000,
            signDateFrom="2024-01-01",
            refContractStatusId=[ContractStatus.ACTIVE.value],
        )

        assert filters.supplierBiin == ["987654321098"]
        assert filters.contractSumFrom == 500000
        assert filters.signDateFrom == "2024-01-01"
        assert filters.refContractStatusId == [2]


class TestAsyncCache:
    """Тесты кеша"""

    @pytest.mark.asyncio
    async def test_cache_set_get(self):
        """Тест записи и чтения кеша"""
        cache = AsyncCache()

        await cache.set("test_key", {"data": "test"}, ttl=300)
        result = await cache.get("test_key")

        assert result == {"data": "test"}

    @pytest.mark.asyncio
    async def test_cache_expiration(self):
        """Тест истечения кеша"""
        cache = AsyncCache()

        await cache.set("test_key", {"data": "test"}, ttl=0)
        await asyncio.sleep(0.1)  # Ждем чтобы кеш истек
        result = await cache.get("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """Тест очистки кеша"""
        cache = AsyncCache()

        await cache.set("key1", "data1")
        await cache.set("key2", "data2")
        await cache.clear()

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None


class TestRetryLogic:
    """Тесты retry логики"""

    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self):
        """Тест успешного выполнения с первой попытки"""

        async def success_func():
            return "success"

        result = await with_retry(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """Тест успешного выполнения после неудач"""
        attempts = 0

        async def failing_func():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise Exception("Temporary error")
            return "success"

        config = RetryConfig(max_retries=3, base_delay=0.01)
        result = await with_retry(failing_func, config)

        assert result == "success"
        assert attempts == 3

    @pytest.mark.asyncio
    async def test_retry_max_attempts_exceeded(self):
        """Тест превышения максимального количества попыток"""

        async def always_failing_func():
            raise Exception("Persistent error")

        config = RetryConfig(max_retries=2, base_delay=0.01)

        with pytest.raises(Exception, match="Persistent error"):
            await with_retry(always_failing_func, config)


class TestSearchMethods:
    """Тесты методов поиска"""

    @pytest.mark.asyncio
    @patch.object(GoszakupClient, "_cached_request")
    async def test_search_lots(self, mock_request, client, sample_lot_data):
        """Тест поиска лотов"""
        mock_request.return_value = {"data": {"Lots": [sample_lot_data]}}

        results = await client.search_lots(
            keyword="компьютер",
            customer_bin=["123456789012"],
            trade_methods=[TradeMethod.OPEN_TENDER],
            status=[LotStatus.PUBLISHED],
            amount_range=(1000000, 5000000),
            limit=10,
        )

        assert len(results) == 1
        assert isinstance(results[0], LotResult)
        assert results[0].nameRu == "Поставка компьютерного оборудования"

        # Проверяем что был сделан правильный запрос
        mock_request.assert_called_once()
        call_args = mock_request.call_args[0][0]

        assert "SearchLots" in call_args["query"]
        assert call_args["variables"]["limit"] == 10

        filters = call_args["variables"]["filter"]
        assert filters["nameDescriptionRu"] == "компьютер"
        assert filters["customerBin"] == ["123456789012"]
        assert filters["refTradeMethodsId"] == [1]
        assert filters["refLotStatusId"] == [2]
        assert filters["amountFrom"] == 1000000
        assert filters["amountTo"] == 5000000

    @pytest.mark.asyncio
    @patch.object(GoszakupClient, "_cached_request")
    async def test_search_contracts(self, mock_request, client, sample_contract_data):
        """Тест поиска контрактов"""
        mock_request.return_value = {"data": {"Contract": [sample_contract_data]}}

        results = await client.search_contracts(
            supplier_bin=["987654321098"],
            status=[ContractStatus.ACTIVE],
            sign_date_from="2024-01-01",
            include_acts=True,
        )

        assert len(results) == 1
        assert isinstance(results[0], ContractResult)
        assert results[0].contractNumber == "CONT-2024-001"
        assert results[0].acts is not None

    @pytest.mark.asyncio
    @patch.object(GoszakupClient, "_cached_request")
    async def test_search_subjects(self, mock_request, client):
        """Тест поиска участников"""
        sample_subject = {
            "id": "SUBJ-123",
            "bin": "123456789012",
            "nameRu": "ТОО Тестовая компания",
            "nameKz": "Тест компаниясы ЖШС",
            "addressRu": "г. Алматы, ул. Тестовая, 1",
            "isActive": True,
            "regDate": "2020-01-01T00:00:00",
            "RefSubjectType": {"nameRu": "Юридическое лицо"},
        }

        mock_request.return_value = {"data": {"Subjects": [sample_subject]}}

        results = await client.search_subjects(
            bin_list=["123456789012"],
            subject_type=[SubjectType.LEGAL_ENTITY],
            is_active=True,
        )

        assert len(results) == 1
        assert isinstance(results[0], SubjectResult)
        assert results[0].bin == "123456789012"
        assert results[0].subjectType == "Юридическое лицо"


class TestFullClientExtensions:
    """Тесты расширений полного клиента"""

    @pytest.mark.asyncio
    async def test_export_to_json(self, client_full, sample_lot_data):
        """Тест экспорта в JSON"""
        lot = LotResult(
            id=sample_lot_data["id"],
            lotNumber=sample_lot_data["lotNumber"],
            nameRu=sample_lot_data["nameRu"],
            amount=sample_lot_data["amount"],
        )

        json_data = await client_full.export_search_results(
            [lot], format_type=ExportFormat.JSON
        )

        data = json.loads(json_data)
        assert data["count"] == 1
        assert "metadata" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["id"] == sample_lot_data["id"]

    @pytest.mark.asyncio
    async def test_export_to_csv(self, client_full, sample_lot_data):
        """Тест экспорта в CSV"""
        lot = LotResult(
            id=sample_lot_data["id"],
            lotNumber=sample_lot_data["lotNumber"],
            nameRu=sample_lot_data["nameRu"],
            amount=sample_lot_data["amount"],
        )

        csv_data = await client_full.export_search_results(
            [lot], format_type=ExportFormat.CSV
        )

        lines = csv_data.strip().split("\n")
        assert len(lines) >= 2  # Заголовок + данные
        assert "lotNumber" in lines[0]  # Заголовок
        assert sample_lot_data["lotNumber"] in lines[1]  # Данные

    def test_format_lot_for_telegram(self, client_full, sample_lot_data):
        """Тест форматирования лота для Telegram"""
        lot = LotResult(
            id=sample_lot_data["id"],
            lotNumber=sample_lot_data["lotNumber"],
            nameRu=sample_lot_data["nameRu"],
            amount=sample_lot_data["amount"],
            customerNameRu=sample_lot_data["customerNameRu"],
            customerBin=sample_lot_data["customerBin"],
            tradeMethod="Открытый конкурс",
            status="Прием заявок",
            endDate=sample_lot_data["endDate"],
        )

        formatted = client_full.format_lot_for_telegram(lot)

        assert f"Лот {lot.lotNumber}" in formatted
        assert lot.nameRu in formatted
        assert f"{lot.amount:,.0f} тг" in formatted
        assert lot.customerNameRu in formatted
        assert lot.customerBin in formatted
        assert "Открытый конкурс" in formatted
        assert "Прием заявок" in formatted

    @pytest.mark.asyncio
    async def test_search_with_preset(self, client_full):
        """Тест поиска с предустановками"""
        # Мокаем search_lots
        with patch.object(client_full, "search_lots") as mock_search:
            mock_search.return_value = []

            await client_full.search_with_preset("construction_almaty")

            mock_search.assert_called_once()
            call_kwargs = mock_search.call_args[1]

            assert call_kwargs["keyword"] == "строительство"
            assert call_kwargs["regions"] == ["Алматы"]
            assert call_kwargs["trade_methods"] == [TradeMethod.OPEN_TENDER]

    @pytest.mark.asyncio
    async def test_get_lots_stats(self, client_full):
        """Тест получения статистики"""
        lots = [
            LotResult(id="1", amount=1000000, tradeMethod="Открытый конкурс"),
            LotResult(id="2", amount=2000000, tradeMethod="Открытый конкурс"),
            LotResult(id="3", amount=500000, tradeMethod="Запрос ценовых предложений"),
        ]

        stats = await client_full.get_lots_stats(lots, group_by="tradeMethod")

        assert stats["total"] == 3
        assert stats["total_amount"] == 3500000
        assert stats["avg_amount"] == 3500000 / 3
        assert stats["max_amount"] == 2000000
        assert stats["min_amount"] == 500000

        assert "groups" in stats
        assert stats["groups"]["Открытый конкурс"]["count"] == 2
        assert stats["groups"]["Открытый конкурс"]["amount"] == 3000000
        assert stats["groups"]["Запрос ценовых предложений"]["count"] == 1

    @pytest.mark.asyncio
    async def test_monitoring_subscription(self, client_full):
        """Тест создания подписки на мониторинг"""
        callback = AsyncMock()

        subscription_id = await client_full.monitor_lots(
            filters={"keyword": "тест"}, callback=callback, interval=60
        )

        assert subscription_id.startswith("lots_")
        assert len(client_full._subscriptions) == 1

        subscription = client_full._subscriptions[0]
        assert subscription["id"] == subscription_id
        assert subscription["type"] == "lots"
        assert subscription["active"] is True
        assert subscription["interval"] == 60

    @pytest.mark.asyncio
    async def test_batch_search_by_bins(self, client_full):
        """Тест батчевого поиска по БИН"""
        with patch.object(client_full, "search_lots") as mock_search:
            mock_search.return_value = [
                LotResult(id="1", customerBin="123456789012"),
                LotResult(id="2", customerBin="123456789013"),
            ]

            bins = ["123456789012", "123456789013", "123456789014"]
            results = await client_full.batch_search_by_bins(
                bins, entity_type="lots", batch_size=2
            )

            # Должно быть сделано 2 запроса (2+2 и 1 БИН)
            assert mock_search.call_count == 2

            # Проверяем группировку результатов
            assert "123456789012" in results
            assert "123456789013" in results


class TestMonitoringCallback:
    """Тесты callback для мониторинга"""

    @pytest.mark.asyncio
    async def test_create_monitoring_callback(self):
        """Тест создания callback функции"""
        processed_results = []

        def process_func(result):
            processed_results.append(result.id)

        callback = create_monitoring_callback(process_func)

        # Тестовые результаты
        test_results = [
            LotResult(id="1", nameRu="Лот 1"),
            LotResult(id="2", nameRu="Лот 2"),
        ]

        await callback(test_results)

        assert len(processed_results) == 2
        assert "1" in processed_results
        assert "2" in processed_results

    @pytest.mark.asyncio
    async def test_create_monitoring_callback_async(self):
        """Тест создания async callback функции"""
        processed_results = []

        async def async_process_func(result):
            processed_results.append(f"async_{result.id}")

        callback = create_monitoring_callback(async_process_func)

        test_results = [LotResult(id="1", nameRu="Лот 1")]
        await callback(test_results)

        assert processed_results == ["async_1"]


# Интеграционные тесты (требуют настоящий токен)
class TestIntegration:
    """Интеграционные тесты с реальным API"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_api_search(self):
        """Тест с реальным API (требует токен в переменной окружения)"""
        import os

        token = os.getenv("GOSZAKUP_TOKEN")
        if not token:
            pytest.skip("GOSZAKUP_TOKEN not set")

        async with GoszakupClient(token=token) as client:
            # Простой поиск
            results = await client.search_lots(keyword="компьютер", limit=1)

            # Проверяем что получили результат правильного типа
            if results:
                assert isinstance(results[0], LotResult)
                assert results[0].id

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_api_export(self):
        """Тест экспорта с реальными данными"""
        import os

        token = os.getenv("GOSZAKUP_TOKEN")
        if not token:
            pytest.skip("GOSZAKUP_TOKEN not set")

        async with GoszakupClientFull(token=token) as client:
            results = await client.search_lots(keyword="тест", limit=2)

            if results:
                # Тест экспорта в JSON
                json_export = await client.export_search_results(
                    results, ExportFormat.JSON
                )
                assert json.loads(json_export)

                # Тест экспорта в CSV
                csv_export = await client.export_search_results(
                    results, ExportFormat.CSV
                )
                assert len(csv_export.split("\n")) >= 2


if __name__ == "__main__":
    # Для запуска тестов: python -m pytest test_goszakup_client_v3.py -v
    # Для интеграционных тестов: python -m pytest test_goszakup_client_v3.py -v -m integration
    pass
