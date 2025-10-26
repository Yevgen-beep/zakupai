#!/usr/bin/env python3
"""
Тесты для REST v3 поиска лотов
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Добавляем путь к модулю бота
sys.path.append(str(Path(__file__).parent.parent / "bot"))

from search.graphql_v2_client import LotResult
from search.rest_v3_client import RestV3Client

TEST_REST_TOKEN = os.getenv("GOSZAKUP_V3_TEST_TOKEN", "dummy-rest-token")  # nosec B105


class TestRestV3Client(unittest.IsolatedAsyncioTestCase):
    """Тесты для REST v3 клиента"""

    def setUp(self):
        """Настройка тестов"""
        self.test_token = TEST_REST_TOKEN
        self.client = RestV3Client(self.test_token, timeout=10)

    async def test_client_initialization(self):
        """Тест инициализации клиента"""
        self.assertEqual(self.client.token, self.test_token)
        self.assertEqual(self.client.rest_base_url, "https://ows.goszakup.gov.kz/v3")
        self.assertEqual(
            self.client.graphql_url, "https://ows.goszakup.gov.kz/v3/graphql"
        )
        self.assertIn(f"Bearer {self.test_token}", self.client.headers["Authorization"])

    async def test_client_initialization_without_token(self):
        """Тест инициализации без токена"""
        client = RestV3Client()
        self.assertIsNone(client.token)
        self.assertNotIn("Authorization", client.headers)
        self.assertFalse(client.is_token_available())

    @patch("aiohttp.ClientSession.get")
    async def test_search_lots_rest_success(self, mock_get):
        """Тест успешного поиска через REST v3"""
        # Мокаем успешный ответ
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "lots": [
                    {
                        "id": 789,
                        "lot_number": "LOT-REST-001",
                        "nameRu": "Мебель офисная",
                        "descriptionRu": "Столы и стулья для офиса",
                        "count": 50.0,
                        "amount": 300000.0,
                        "customer_name_ru": "АО Офис-Сервис",
                        "customer_bin": "987654321098",
                        "trd_buy_number_anno": "REST-ANNO-001",
                        "trd_buy": {
                            "id": 101112,
                            "name_ru": "Закупка офисной мебели",
                            "number_anno": "REST-ANNO-001",
                            "org_name_ru": "АО Офис-Сервис",
                            "org_bin": "987654321098",
                            "end_date": "2024-11-30T18:00:00Z",
                        },
                        "ref_lot_status": {"id": 1, "name_ru": "Опубликован"},
                        "ref_trade_methods": {
                            "id": 3,
                            "name_ru": "Из одного источника",
                        },
                    }
                ]
            }
        )

        mock_get.return_value.__aenter__.return_value = mock_response

        # Выполняем поиск
        results = await self.client.search_by_keyword(
            "мебель", limit=5, use_graphql=False
        )

        # Проверяем результаты
        self.assertEqual(len(results), 1)
        result = results[0]

        self.assertIsInstance(result, LotResult)
        self.assertEqual(result.lot_number, "LOT-REST-001")
        self.assertEqual(result.lot_name, "Мебель офисная")
        self.assertEqual(result.amount, 300000.0)
        self.assertEqual(result.customer_name, "АО Офис-Сервис")
        self.assertEqual(result.trade_method, "Из одного источника")
        self.assertEqual(result.status, "Опубликован")
        self.assertEqual(result.source, "rest_v3")

    @patch("aiohttp.ClientSession.post")
    async def test_search_lots_graphql_v3_success(self, mock_post):
        """Тест успешного поиска через GraphQL v3"""
        # Мокаем успешный ответ GraphQL v3
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": {
                    "lots": [
                        {
                            "id": 456,
                            "lot_number": "LOT-GQL3-001",
                            "nameRu": "Уголь каменный",
                            "descriptionRu": "Уголь для отопления",
                            "count": 1000.0,
                            "amount": 500000.0,
                            "customer_name_ru": "ТОО Энергоресурс",
                            "customer_bin": "555666777888",
                            "trd_buy_number_anno": "GQL3-ANNO-001",
                            "trd_buy": {
                                "id": 20304,
                                "name_ru": "Закупка угля",
                                "number_anno": "GQL3-ANNO-001",
                                "org_name_ru": "ТОО Энергоресурс",
                                "org_bin": "555666777888",
                                "end_date": "2024-12-15T12:00:00Z",
                            },
                            "ref_lot_status": {"id": 2, "name_ru": "Прием заявок"},
                            "ref_trade_methods": {
                                "id": 1,
                                "name_ru": "Открытый тендер",
                            },
                        }
                    ]
                }
            }
        )

        mock_post.return_value.__aenter__.return_value = mock_response

        # Выполняем поиск через GraphQL v3
        results = await self.client.search_by_keyword(
            "уголь", limit=5, use_graphql=True
        )

        # Проверяем результаты
        self.assertEqual(len(results), 1)
        result = results[0]

        self.assertIsInstance(result, LotResult)
        self.assertEqual(result.lot_number, "LOT-GQL3-001")
        self.assertEqual(result.lot_name, "Уголь каменный")
        self.assertEqual(result.amount, 500000.0)
        self.assertEqual(result.customer_name, "ТОО Энергоресурс")
        self.assertEqual(result.trade_method, "Открытый тендер")
        self.assertEqual(result.status, "Прием заявок")
        self.assertEqual(result.source, "graphql_v3")

    @patch("aiohttp.ClientSession.get")
    async def test_search_lots_rest_error(self, mock_get):
        """Тест обработки ошибок REST v3"""
        # Мокаем ошибку
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")
        mock_get.return_value.__aenter__.return_value = mock_response

        # Проверяем обработку ошибок
        with self.assertRaises(Exception) as context:
            await self.client.search_by_keyword("лак", use_graphql=False)

        self.assertIn("REST v3 request failed", str(context.exception))

    @patch("aiohttp.ClientSession.get")
    async def test_get_lot_by_id_success(self, mock_get):
        """Тест получения лота по ID"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "id": 12345,
                "lot_number": "SPECIFIC-LOT-001",
                "nameRu": "Конкретный лот",
                "descriptionRu": "Описание конкретного лота",
                "count": 1.0,
                "amount": 100000.0,
                "customer_name_ru": "ТОО Заказчик",
                "customer_bin": "111222333444",
            }
        )

        mock_get.return_value.__aenter__.return_value = mock_response

        result = await self.client.get_lot_by_id(12345)

        self.assertIsNotNone(result)
        self.assertEqual(result.lot_number, "SPECIFIC-LOT-001")
        self.assertEqual(result.lot_name, "Конкретный лот")

    @patch("aiohttp.ClientSession.get")
    async def test_get_lot_by_id_not_found(self, mock_get):
        """Тест получения несуществующего лота"""
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await self.client.get_lot_by_id(99999)
        self.assertIsNone(result)

    async def test_search_by_complex_filters_parameters(self):
        """Тест параметров сложного поиска"""
        filters = {
            "keyword": "строительство",
            "customer_bin": "123456789012",
            "trade_method_ids": [1, 7],
            "status_ids": [1, 2],
            "min_amount": 100000,
            "max_amount": 1000000,
            "publish_date_from": "2024-01-01",
            "publish_date_to": "2024-12-31",
        }

        # Мокаем метод поиска
        with patch.object(self.client, "search_lots_rest", return_value=[]):
            with patch.object(self.client, "search_lots_graphql_v3", return_value=[]):
                try:
                    # REST поиск
                    await self.client.search_by_complex_filters(
                        **filters, use_graphql=False
                    )
                    # GraphQL поиск
                    await self.client.search_by_complex_filters(
                        **filters, use_graphql=True
                    )
                except Exception as e:
                    self.fail(f"Complex filters failed: {e}")

    async def test_get_available_endpoints(self):
        """Тест получения доступных endpoints"""
        endpoints = await self.client.get_available_endpoints()

        self.assertIn("lots", endpoints)
        self.assertIn("lots_by_id", endpoints)
        self.assertIn("announcements", endpoints)
        self.assertIn("graphql", endpoints)

        # Проверяем корректность URL
        self.assertEqual(endpoints["lots"], "https://ows.goszakup.gov.kz/v3/lots")
        self.assertEqual(endpoints["graphql"], "https://ows.goszakup.gov.kz/v3/graphql")

    def test_build_graphql_v3_query(self):
        """Тест построения GraphQL v3 запроса"""
        query = self.client._build_graphql_v3_query()

        # Проверяем структуру запроса
        self.assertIn("query SearchLotsV3", query)
        self.assertIn("LotsFilterInput", query)
        self.assertIn("lot_number", query)
        self.assertIn("nameRu", query)
        self.assertIn("trd_buy", query)
        self.assertIn("ref_lot_status", query)
        self.assertIn("ref_trade_methods", query)

    def test_parse_rest_results_empty(self):
        """Тест парсинга пустых результатов REST"""
        results = self.client._parse_rest_results([])
        self.assertEqual(len(results), 0)

    def test_parse_graphql_v3_results_empty(self):
        """Тест парсинга пустых результатов GraphQL v3"""
        results = self.client._parse_graphql_v3_results([])
        self.assertEqual(len(results), 0)

    def test_is_token_available(self):
        """Тест проверки наличия токена"""
        client_with_token = RestV3Client("some_token")
        client_without_token = RestV3Client()

        self.assertTrue(client_with_token.is_token_available())
        self.assertFalse(client_without_token.is_token_available())


class TestRestV3Integration(unittest.IsolatedAsyncioTestCase):
    """Интеграционные тесты REST v3 (работают без токена)"""

    def setUp(self):
        """Настройка интеграционных тестов"""
        self.client = RestV3Client(timeout=15)

    async def test_real_rest_search_public(self):
        """Тест реального поиска через публичный REST API"""
        try:
            results = await self.client.search_by_keyword(
                "лак", limit=2, use_graphql=False
            )

            self.assertIsInstance(results, list)
            print(f"✅ Real REST search returned {len(results)} results")

            if results:
                result = results[0]
                self.assertIsInstance(result, LotResult)
                self.assertEqual(result.source, "rest_v3")
                print(f"  - First result: {result.lot_name}")
                print(f"  - Customer: {result.customer_name}")
                print(f"  - Amount: {result.amount:,.0f} {result.currency}")

        except Exception as e:
            print(f"❌ Real REST search failed: {e}")
            self.skipTest(f"Real REST API search failed: {e}")

    async def test_real_endpoints_availability(self):
        """Тест доступности endpoints"""
        endpoints = await self.client.get_available_endpoints()

        self.assertIsInstance(endpoints, dict)
        print("✅ Available endpoints:")
        for name, url in endpoints.items():
            print(f"  - {name}: {url}")


def run_rest_tests():
    """Запуск всех тестов REST v3"""
    print("🧪 Running REST v3 Tests")
    print("=" * 50)

    # Создаем test suite
    suite = unittest.TestSuite()

    # Добавляем базовые тесты
    suite.addTest(unittest.makeSuite(TestRestV3Client))

    # Добавляем интеграционные тесты (не требуют токена)
    print("🌐 Including integration tests (no token required)")
    suite.addTest(unittest.makeSuite(TestRestV3Integration))

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
    success = run_rest_tests()
    sys.exit(0 if success else 1)
