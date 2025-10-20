#!/usr/bin/env python3
"""
Тесты для fallback логики поиска лотов
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Добавляем путь к модулю бота
sys.path.append(str(Path(__file__).parent.parent / "bot"))

from search.graphql_v2_client import LotResult
from search.search_service import (
    GoszakupSearchService,
    SearchComplexity,
    SearchQuery,
    SearchStrategy,
    search_lots_for_telegram,
)


class TestFallbackLogic(unittest.IsolatedAsyncioTestCase):
    """Тесты fallback логики поискового сервиса"""

    def setUp(self):
        """Настройка тестов"""
        self.service = GoszakupSearchService(
            graphql_v2_token="test_v2_token",
            rest_v3_token="test_v3_token",
            default_strategy=SearchStrategy.AUTO,
        )

    async def test_strategy_determination_simple(self):
        """Тест определения стратегии для простого запроса"""
        query = SearchQuery(keyword="лак")

        # Мокаем проверку доступности v2
        with patch.object(self.service, "_is_v2_available", return_value=True):
            strategy = await self.service._determine_optimal_strategy(query)

            # Простые запросы должны идти через REST v3 (быстрее)
            self.assertEqual(strategy, SearchStrategy.REST_V3)

    async def test_strategy_determination_moderate(self):
        """Тест определения стратегии для умеренно сложного запроса"""
        query = SearchQuery(
            keyword="мебель", customer_bin="123456789012", min_amount=100000
        )

        # Мокаем проверку доступности v2
        with patch.object(self.service, "_is_v2_available", return_value=True):
            strategy = await self.service._determine_optimal_strategy(query)

            # Средние запросы - приоритет GraphQL v2
            self.assertEqual(strategy, SearchStrategy.GRAPHQL_V2)

    async def test_strategy_determination_complex(self):
        """Тест определения стратегии для сложного запроса"""
        query = SearchQuery(
            keyword="строительство",
            customer_bin="123456789012",
            customer_name="ТОО Стройка",
            trade_method_ids=[1, 3, 7],
            status_ids=[1, 2],
            min_amount=500000,
            max_amount=5000000,
            publish_date_from="2024-01-01",
        )

        # Мокаем проверку доступности v2
        with patch.object(self.service, "_is_v2_available", return_value=True):
            strategy = await self.service._determine_optimal_strategy(query)

            # Сложные запросы - обязательно GraphQL v2
            self.assertEqual(strategy, SearchStrategy.GRAPHQL_V2)

    async def test_strategy_fallback_when_v2_unavailable(self):
        """Тест fallback на v3 когда v2 недоступен"""
        query = SearchQuery(keyword="мебель", customer_bin="123456789012")

        # Мокаем недоступность v2
        with patch.object(self.service, "_is_v2_available", return_value=False):
            strategy = await self.service._determine_optimal_strategy(query)

            # При недоступности v2 должен выбираться REST v3
            self.assertEqual(strategy, SearchStrategy.REST_V3)

    def test_query_complexity_assessment(self):
        """Тест оценки сложности запроса"""
        # Простой запрос
        simple_query = SearchQuery(keyword="лак")
        complexity = self.service._assess_query_complexity(simple_query)
        self.assertEqual(complexity, SearchComplexity.SIMPLE)

        # Умеренный запрос
        moderate_query = SearchQuery(
            keyword="мебель", customer_bin="123456789012", min_amount=100000
        )
        complexity = self.service._assess_query_complexity(moderate_query)
        self.assertEqual(complexity, SearchComplexity.MODERATE)

        # Сложный запрос
        complex_query = SearchQuery(
            keyword="строительство",
            customer_bin="123456789012",
            customer_name="ТОО Стройка",
            trade_method_ids=[1, 3],
            status_ids=[1, 2],
            min_amount=500000,
            announcement_number="ANNO-001",
        )
        complexity = self.service._assess_query_complexity(complex_query)
        self.assertEqual(complexity, SearchComplexity.COMPLEX)

    @patch("search.search_service.GraphQLV2Client")
    @patch("search.search_service.RestV3Client")
    async def test_search_with_v2_success(self, mock_rest_client, mock_v2_client):
        """Тест успешного поиска через GraphQL v2"""
        # Настраиваем моки
        mock_result = LotResult(
            lot_number="TEST-001",
            announcement_number="ANNO-001",
            announcement_name="Тестовое объявление",
            lot_name="Тестовый лот",
            lot_description="Описание тестового лота",
            quantity=10.0,
            amount=100000.0,
            currency="KZT",
            trade_method="Открытый тендер",
            status="Прием заявок",
            customer_name="ТОО Тестовая компания",
            customer_bin="123456789012",
            source="graphql_v2",
        )

        mock_v2_instance = AsyncMock()
        mock_v2_instance.search_by_keyword.return_value = [mock_result]
        mock_v2_client.return_value = mock_v2_instance

        # Создаем сервис
        service = GoszakupSearchService(
            graphql_v2_token="test_token", default_strategy=SearchStrategy.GRAPHQL_V2
        )

        # Мокаем проверку доступности
        with patch.object(service, "_is_v2_available", return_value=True):
            results = await service.search_by_keyword("лак", limit=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "graphql_v2")
        self.assertEqual(service.stats["v2_requests"], 1)

    @patch("search.search_service.GraphQLV2Client")
    @patch("search.search_service.RestV3Client")
    async def test_search_with_v2_failure_fallback_to_v3(
        self, mock_rest_client, mock_v2_client
    ):
        """Тест fallback на REST v3 при ошибке GraphQL v2"""
        # Настраиваем мок GraphQL v2 для ошибки
        mock_v2_instance = AsyncMock()
        mock_v2_instance.search_by_keyword.side_effect = Exception("GraphQL v2 failed")
        mock_v2_client.return_value = mock_v2_instance

        # Настраиваем мок REST v3 для успеха
        mock_result_v3 = LotResult(
            lot_number="TEST-V3-001",
            announcement_number="ANNO-V3-001",
            announcement_name="Fallback объявление",
            lot_name="Fallback лот",
            lot_description="Описание fallback лота",
            quantity=5.0,
            amount=50000.0,
            currency="KZT",
            trade_method="Из одного источника",
            status="Опубликован",
            customer_name="АО Fallback компания",
            customer_bin="987654321098",
            source="rest_v3",
        )

        mock_rest_instance = AsyncMock()
        mock_rest_instance.search_by_keyword.return_value = [mock_result_v3]
        mock_rest_client.return_value = mock_rest_instance

        # Создаем сервис
        service = GoszakupSearchService(
            graphql_v2_token="test_token",
            rest_v3_token="test_token_v3",
            default_strategy=SearchStrategy.GRAPHQL_V2,
        )

        # Мокаем проверку доступности
        with patch.object(service, "_is_v2_available", return_value=True):
            results = await service.search_by_keyword("лак", limit=5)

        # Проверяем, что получили результат от REST v3 через fallback
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "rest_v3")
        self.assertEqual(service.stats["fallback_requests"], 1)

    @patch("search.search_service.GraphQLV2Client")
    @patch("search.search_service.RestV3Client")
    async def test_search_complete_failure(self, mock_rest_client, mock_v2_client):
        """Тест полного отказа всех API"""
        # Настраиваем моки для ошибок
        mock_v2_instance = AsyncMock()
        mock_v2_instance.search_by_keyword.side_effect = Exception("GraphQL v2 failed")
        mock_v2_client.return_value = mock_v2_instance

        mock_rest_instance = AsyncMock()
        mock_rest_instance.search_by_keyword.side_effect = Exception("REST v3 failed")
        mock_rest_client.return_value = mock_rest_instance

        # Создаем сервис
        service = GoszakupSearchService(
            graphql_v2_token="test_token",
            rest_v3_token="test_token_v3",
            default_strategy=SearchStrategy.GRAPHQL_V2,
        )

        # Мокаем проверку доступности
        with patch.object(service, "_is_v2_available", return_value=True):
            with self.assertRaises(Exception) as context:
                await service.search_by_keyword("лак", limit=5)

        self.assertIn("All search strategies failed", str(context.exception))
        self.assertEqual(service.stats["failed_requests"], 1)

    async def test_parse_string_query_simple(self):
        """Тест парсинга простого строкового запроса"""
        parsed = await self.service._parse_string_query("лак")

        self.assertEqual(parsed.keyword, "лак")
        self.assertIsNone(parsed.customer_bin)
        self.assertIsNone(parsed.min_amount)

    async def test_parse_string_query_with_bin(self):
        """Тест парсинга запроса с БИН"""
        parsed = await self.service._parse_string_query("мебель БИН:123456789012")

        self.assertEqual(parsed.keyword, "мебель")
        self.assertEqual(parsed.customer_bin, "123456789012")

    async def test_parse_string_query_with_amount_range(self):
        """Тест парсинга запроса с диапазоном сумм"""
        parsed = await self.service._parse_string_query(
            "строительство сумма:100000-500000"
        )

        self.assertEqual(parsed.keyword, "строительство")
        self.assertEqual(parsed.min_amount, 100000.0)
        self.assertEqual(parsed.max_amount, 500000.0)

    async def test_parse_string_query_with_announcement(self):
        """Тест парсинга запроса с номером объявления"""
        parsed = await self.service._parse_string_query("поиск объявление:ANNO-12345")

        self.assertEqual(parsed.keyword, "поиск")
        self.assertEqual(parsed.announcement_number, "ANNO-12345")

    @patch("search.search_service.RestV3Client")
    async def test_format_results_for_telegram(self, mock_rest_client):
        """Тест форматирования результатов для Telegram"""
        # Создаем тестовые результаты
        results = [
            LotResult(
                lot_number="LOT-001",
                announcement_number="ANNO-001",
                announcement_name="Тестовое объявление",
                lot_name="Тестовый лот",
                lot_description="Краткое описание",
                quantity=10.0,
                amount=100000.0,
                currency="KZT",
                trade_method="Открытый тендер",
                status="Прием заявок",
                customer_name="ТОО Тестовая компания",
                customer_bin="123456789012",
                deadline="2024-12-31T23:59:59Z",
                url="https://goszakup.gov.kz/ru/announce/index/12345",
                source="graphql_v2",
            )
        ]

        formatted = await self.service.format_results_for_telegram(
            results, show_source=True
        )

        # Проверяем, что форматирование содержит ключевые элементы
        self.assertIn("Найдено лотов: 1", formatted)
        self.assertIn("LOT-001", formatted)
        self.assertIn("ANNO-001", formatted)
        self.assertIn("Тестовое объявление", formatted)
        self.assertIn("Тестовый лот", formatted)
        self.assertIn("100,000 KZT", formatted)
        self.assertIn("ТОО Тестовая компания", formatted)
        self.assertIn("123456789012", formatted)
        self.assertIn("Открытый тендер", formatted)
        self.assertIn("Прием заявок", formatted)
        self.assertIn("goszakup.gov.kz", formatted)
        self.assertIn("graphql_v2", formatted)

    async def test_format_empty_results_for_telegram(self):
        """Тест форматирования пустых результатов для Telegram"""
        formatted = await self.service.format_results_for_telegram([])
        self.assertEqual(formatted, "🔍 Ничего не найдено по вашему запросу.")

    def test_get_search_statistics(self):
        """Тест получения статистики поиска"""
        # Устанавливаем тестовые значения статистики
        self.service.stats["v2_requests"] = 5
        self.service.stats["v3_rest_requests"] = 3
        self.service.stats["fallback_requests"] = 2
        self.service.stats["failed_requests"] = 1

        stats = self.service.get_search_statistics()

        self.assertEqual(stats["v2_requests"], 5)
        self.assertEqual(stats["v3_rest_requests"], 3)
        self.assertEqual(stats["fallback_requests"], 2)
        self.assertEqual(stats["failed_requests"], 1)
        self.assertEqual(stats["total_requests"], 11)
        self.assertAlmostEqual(stats["success_rate"], 10 / 11, places=2)


class TestTelegramIntegration(unittest.IsolatedAsyncioTestCase):
    """Тесты интеграции с Telegram"""

    @patch("search.search_service.GoszakupSearchService")
    async def test_search_lots_for_telegram_success(self, mock_service_class):
        """Тест успешного поиска для Telegram"""
        # Настраиваем мок
        mock_service = AsyncMock()
        mock_result = LotResult(
            lot_number="TG-001",
            announcement_number="TG-ANNO-001",
            announcement_name="Telegram тест",
            lot_name="Лот для Telegram",
            lot_description="Описание для тестирования",
            quantity=1.0,
            amount=50000.0,
            currency="KZT",
            trade_method="Запрос ценовых предложений",
            status="Опубликован",
            customer_name="ТОО Telegram Тест",
            customer_bin="111222333444",
            source="rest_v3",
        )

        mock_service.search_lots.return_value = [mock_result]
        mock_service.format_results_for_telegram.return_value = (
            "✅ Форматированный результат для Telegram"
        )
        mock_service_class.return_value = mock_service

        # Выполняем поиск
        result = await search_lots_for_telegram("лак", limit=5)

        self.assertEqual(result, "✅ Форматированный результат для Telegram")

    @patch("search.search_service.GoszakupSearchService")
    async def test_search_lots_for_telegram_error(self, mock_service_class):
        """Тест обработки ошибок в Telegram поиске"""
        # Настраиваем мок для ошибки
        mock_service = AsyncMock()
        mock_service.search_lots.side_effect = Exception("API Error")
        mock_service_class.return_value = mock_service

        # Выполняем поиск
        result = await search_lots_for_telegram("лак")

        self.assertIn("❌ Произошла ошибка поиска", result)
        self.assertIn("API Error", result)


def run_fallback_tests():
    """Запуск всех тестов fallback логики"""
    print("🧪 Running Fallback Logic Tests")
    print("=" * 50)

    # Создаем test suite
    suite = unittest.TestSuite()

    # Добавляем тесты
    suite.addTest(unittest.makeSuite(TestFallbackLogic))
    suite.addTest(unittest.makeSuite(TestTelegramIntegration))

    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Выводим результаты
    print("\n📊 Test Results:")
    print(f"  Tests run: {result.testsRun}")
    print(f"  Failures: {len(result.failures)}")
    print(f"  Errors: {len(result.errors)}")
    print(f"  Skipped: {len(result.skipped)}")

    if result.failures:
        print("\n❌ Failures:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")

    if result.errors:
        print("\n💥 Errors:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")

    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\n{'✅ All tests passed!' if success else '❌ Some tests failed'}")

    return success


if __name__ == "__main__":
    success = run_fallback_tests()
    sys.exit(0 if success else 1)
