#!/usr/bin/env python3
"""
Тесты для GraphQL v2 поиска лотов
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Добавляем путь к модулю бота
sys.path.append(str(Path(__file__).parent.parent / "bot"))

from search.graphql_v2_client import GraphQLV2Client, LotResult


class TestGraphQLV2Client(unittest.IsolatedAsyncioTestCase):
    """Тесты для GraphQL v2 клиента"""

    def setUp(self):
        """Настройка тестов"""
        self.test_token = "test_token_12345"
        self.client = GraphQLV2Client(self.test_token, timeout=10)

    async def test_client_initialization(self):
        """Тест инициализации клиента"""
        self.assertEqual(self.client.token, self.test_token)
        self.assertEqual(
            self.client.graphql_url, "https://ows.goszakup.gov.kz/v2/graphql"
        )
        self.assertIn("Bearer test_token_12345", self.client.headers["Authorization"])

    @patch("aiohttp.ClientSession.post")
    async def test_search_lots_success(self, mock_post):
        """Тест успешного поиска лотов"""
        # Мокаем успешный ответ
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": {
                    "Lots": [
                        {
                            "id": 123,
                            "lotNumber": "LOT-001",
                            "nameRu": "Лакокрасочные материалы",
                            "descriptionRu": "Краска для внутренних работ",
                            "amount": 150000.0,
                            "count": 100.0,
                            "customerNameRu": "ТОО Тестовая компания",
                            "customerBin": "123456789012",
                            "trdBuyNumberAnno": "ANNO-001",
                            "TrdBuy": {
                                "id": 456,
                                "nameRu": "Закупка лакокрасочных материалов",
                                "numberAnno": "ANNO-001",
                                "orgNameRu": "ТОО Тестовая компания",
                                "orgBin": "123456789012",
                                "endDate": "2024-12-31T23:59:59Z",
                                "RefTradeMethods": {
                                    "id": 1,
                                    "nameRu": "Открытый тендер",
                                },
                            },
                            "RefLotsStatus": {"id": 2, "nameRu": "Прием заявок"},
                        }
                    ]
                }
            }
        )

        mock_post.return_value.__aenter__.return_value = mock_response

        # Выполняем поиск
        results = await self.client.search_by_keyword("лак", limit=5)

        # Проверяем результаты
        self.assertEqual(len(results), 1)
        result = results[0]

        self.assertIsInstance(result, LotResult)
        self.assertEqual(result.lot_number, "LOT-001")
        self.assertEqual(result.lot_name, "Лакокрасочные материалы")
        self.assertEqual(result.amount, 150000.0)
        self.assertEqual(result.customer_name, "ТОО Тестовая компания")
        self.assertEqual(result.trade_method, "Открытый тендер")
        self.assertEqual(result.status, "Прием заявок")
        self.assertEqual(result.source, "graphql_v2")

    @patch("aiohttp.ClientSession.post")
    async def test_search_lots_error(self, mock_post):
        """Тест обработки ошибок поиска"""
        # Мокаем ошибку авторизации
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_post.return_value.__aenter__.return_value = mock_response

        # Проверяем, что выбрасывается исключение
        with self.assertRaises(Exception) as context:
            await self.client.search_by_keyword("лак")

        self.assertIn("authorization failed", str(context.exception))

    @patch("aiohttp.ClientSession.post")
    async def test_search_lots_graphql_error(self, mock_post):
        """Тест обработки GraphQL ошибок"""
        # Мокаем ответ с GraphQL ошибками
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "errors": [
                    {"message": "Field 'invalidField' doesn't exist on type 'Lots'"}
                ]
            }
        )

        mock_post.return_value.__aenter__.return_value = mock_response

        # Проверяем обработку GraphQL ошибок
        with self.assertRaises(Exception) as context:
            await self.client.search_by_keyword("лак")

        self.assertIn("GraphQL query failed", str(context.exception))

    async def test_search_by_complex_filters(self):
        """Тест сложного поиска с фильтрами"""
        # Тестируем только построение параметров (без реального запроса)
        filters = {
            "keyword": "мебель",
            "customer_bin": "123456789012",
            "trade_method_ids": [1, 3],
            "status_ids": [2, 10],
            "min_amount": 50000,
        }

        # Проверяем, что метод принимает параметры без ошибок
        try:
            # Мокаем метод search_lots чтобы не делать реальный запрос
            with patch.object(self.client, "search_lots", return_value=[]):
                await self.client.search_by_complex_filters(**filters)
        except Exception as e:
            self.fail(f"Complex filters search failed: {e}")

    async def test_get_available_filters(self):
        """Тест получения доступных фильтров"""
        filters = await self.client.get_available_filters()

        self.assertIn("text_filters", filters)
        self.assertIn("list_filters", filters)
        self.assertIn("numeric_filters", filters)

        # Проверяем наличие ключевых фильтров
        self.assertIn("nameRu", filters["text_filters"])
        self.assertIn("nameDescriptionRu", filters["text_filters"])
        self.assertIn("customerBin", filters["text_filters"])

    def test_build_search_query(self):
        """Тест построения GraphQL запроса"""
        query = self.client._build_search_query()

        # Проверяем, что запрос содержит необходимые поля
        self.assertIn("query SearchLots", query)
        self.assertIn("LotsFiltersInput", query)
        self.assertIn("lotNumber", query)
        self.assertIn("nameRu", query)
        self.assertIn("TrdBuy", query)
        self.assertIn("RefLotsStatus", query)

    async def test_parse_results_empty(self):
        """Тест парсинга пустых результатов"""
        results = self.client._parse_results([])
        self.assertEqual(len(results), 0)

    async def test_parse_results_malformed_data(self):
        """Тест парсинга некорректных данных"""
        malformed_data = [
            {"invalid": "data"},  # Неполные данные
            {},  # Пустой объект
            {"lotNumber": None, "nameRu": ""},  # Частично заполненные данные
        ]

        # Парсинг не должен падать, но может вернуть пустой список
        results = self.client._parse_results(malformed_data)
        # Проверяем, что функция не падает
        self.assertIsInstance(results, list)


class TestGraphQLV2Integration(unittest.IsolatedAsyncioTestCase):
    """Интеграционные тесты GraphQL v2 (требуют реального токена)"""

    def setUp(self):
        """Настройка интеграционных тестов"""
        self.token = os.getenv("GOSZAKUP_V2_TOKEN")
        self.skip_if_no_token()

    def skip_if_no_token(self):
        """Пропускаем тесты если нет токена"""
        if not self.token:
            self.skipTest("GOSZAKUP_V2_TOKEN not set - skipping integration tests")

    async def test_real_token_validation(self):
        """Тест валидации реального токена"""
        client = GraphQLV2Client(self.token, timeout=15)

        try:
            is_valid = await client.validate_token()
            # Если токен реальный, он должен быть валидным или невалидным
            self.assertIsInstance(is_valid, bool)

            if is_valid:
                print("✅ GraphQL v2 token is valid")
            else:
                print("❌ GraphQL v2 token is invalid or expired")

        except Exception as e:
            # При проблемах с сетью или API тест может упасть
            self.skipTest(f"Network/API error during token validation: {e}")

    async def test_real_search_simple(self):
        """Тест реального простого поиска"""
        client = GraphQLV2Client(self.token, timeout=15)

        try:
            results = await client.search_by_keyword("лак", limit=2)

            # Проверяем, что получили список результатов
            self.assertIsInstance(results, list)
            print(f"✅ Real search returned {len(results)} results")

            if results:
                result = results[0]
                self.assertIsInstance(result, LotResult)
                self.assertEqual(result.source, "graphql_v2")
                print(f"  - First result: {result.lot_name}")
                print(f"  - Customer: {result.customer_name}")
                print(f"  - Amount: {result.amount:,.0f} {result.currency}")

        except Exception as e:
            # Если API недоступен или токен недействителен
            print(f"❌ Real search failed: {e}")
            self.skipTest(f"Real API search failed: {e}")


def run_graphql_tests():
    """Запуск всех тестов GraphQL v2"""
    print("🧪 Running GraphQL v2 Tests")
    print("=" * 50)

    # Создаем test suite
    suite = unittest.TestSuite()

    # Добавляем базовые тесты
    suite.addTest(unittest.makeSuite(TestGraphQLV2Client))

    # Добавляем интеграционные тесты только если есть токен
    if os.getenv("GOSZAKUP_V2_TOKEN"):
        print("🔑 Found V2 token - including integration tests")
        suite.addTest(unittest.makeSuite(TestGraphQLV2Integration))
    else:
        print("⚠️  No V2 token found - skipping integration tests")
        print("   Set GOSZAKUP_V2_TOKEN=your_token to run integration tests")

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
    success = run_graphql_tests()
    sys.exit(0 if success else 1)
