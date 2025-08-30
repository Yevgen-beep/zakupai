#!/usr/bin/env python3
"""
Smoke тесты для ZakupAI Telegram Bot
"""

import asyncio
import logging
import os
import sys
from typing import Any

from client import ZakupaiAPIClient

from db import health_check, init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class SmokeTestRunner:
    """Раннер для smoke тестов"""

    def __init__(self):
        self.results = []
        self.api_client = None

    async def setup(self):
        """Настройка тестового окружения"""
        try:
            # Проверяем переменные окружения
            required_vars = ["ZAKUPAI_API_URL", "ZAKUPAI_API_KEY"]
            missing_vars = [var for var in required_vars if not os.getenv(var)]

            if missing_vars:
                raise Exception(
                    f"Missing environment variables: {', '.join(missing_vars)}"
                )

            # Инициализируем API клиент
            self.api_client = ZakupaiAPIClient(
                base_url=os.getenv("ZAKUPAI_API_URL"),
                api_key=os.getenv("ZAKUPAI_API_KEY"),
            )

            logger.info("✅ Test setup completed")
        except Exception as e:
            logger.error(f"❌ Test setup failed: {e}")
            raise

    async def test_database_health(self) -> dict[str, Any]:
        """Тест подключения к БД"""
        test_name = "Database Health"

        try:
            await init_db()
            is_healthy = await health_check()

            if is_healthy:
                return {
                    "name": test_name,
                    "status": "PASS",
                    "message": "Database is healthy",
                }
            else:
                return {
                    "name": test_name,
                    "status": "FAIL",
                    "message": "Database health check failed",
                }
        except Exception as e:
            return {
                "name": test_name,
                "status": "FAIL",
                "message": f"Database error: {e}",
            }

    async def test_api_health_check(self) -> dict[str, Any]:
        """Тест health check API"""
        test_name = "API Health Check"

        try:
            result = await self.api_client.health_check()

            if result and result.get("status") == "ok":
                return {
                    "name": test_name,
                    "status": "PASS",
                    "message": "API health check passed",
                }
            else:
                return {
                    "name": test_name,
                    "status": "FAIL",
                    "message": f"API health check failed: {result}",
                }
        except Exception as e:
            return {
                "name": test_name,
                "status": "FAIL",
                "message": f"API health check error: {e}",
            }

    async def test_api_info_endpoint(self) -> dict[str, Any]:
        """Тест info endpoint с авторизацией"""
        test_name = "API Info Endpoint"

        try:
            result = await self.api_client.get_info()

            if result and "service" in result:
                return {
                    "name": test_name,
                    "status": "PASS",
                    "message": f"Info endpoint returned: {result.get('service')}",
                }
            else:
                return {
                    "name": test_name,
                    "status": "FAIL",
                    "message": f"Invalid info response: {result}",
                }
        except Exception as e:
            return {
                "name": test_name,
                "status": "FAIL",
                "message": f"Info endpoint error: {e}",
            }

    async def test_calc_service_vat(self) -> dict[str, Any]:
        """Тест calc-service VAT расчёта"""
        test_name = "Calc Service VAT"

        try:
            result = await self.api_client.calculate_vat(1000.0, 0.12)

            expected_vat = 120.0  # 12% от 1000
            actual_vat = result.get("vat_amount", 0)

            if abs(actual_vat - expected_vat) < 0.01:
                return {
                    "name": test_name,
                    "status": "PASS",
                    "message": f"VAT calculation correct: {actual_vat}",
                }
            else:
                return {
                    "name": test_name,
                    "status": "FAIL",
                    "message": f"VAT calculation incorrect: expected {expected_vat}, got {actual_vat}",
                }
        except Exception as e:
            return {
                "name": test_name,
                "status": "FAIL",
                "message": f"VAT calculation error: {e}",
            }

    async def test_calc_service_margin(self) -> dict[str, Any]:
        """Тест calc-service margin расчёта"""
        test_name = "Calc Service Margin"

        try:
            result = await self.api_client.calculate_margin(800.0, 1000.0, 1)

            expected_margin = 200.0  # 1000 - 800
            actual_margin = result.get("margin_amount", 0)

            if abs(actual_margin - expected_margin) < 0.01:
                return {
                    "name": test_name,
                    "status": "PASS",
                    "message": f"Margin calculation correct: {actual_margin}",
                }
            else:
                return {
                    "name": test_name,
                    "status": "FAIL",
                    "message": f"Margin calculation incorrect: expected {expected_margin}, got {actual_margin}",
                }
        except Exception as e:
            return {
                "name": test_name,
                "status": "FAIL",
                "message": f"Margin calculation error: {e}",
            }

    async def test_doc_service_tldr(self) -> dict[str, Any]:
        """Тест doc-service TL;DR"""
        test_name = "Doc Service TL;DR"

        try:
            # Используем тестовый ID лота
            result = await self.api_client.get_tldr("test-lot-123")

            if result and "lot_id" in result:
                return {
                    "name": test_name,
                    "status": "PASS",
                    "message": f"TL;DR returned for lot: {result.get('lot_id')}",
                }
            else:
                return {
                    "name": test_name,
                    "status": "FAIL",
                    "message": f"Invalid TL;DR response: {result}",
                }
        except Exception as e:
            return {"name": test_name, "status": "FAIL", "message": f"TL;DR error: {e}"}

    async def test_risk_engine_score(self) -> dict[str, Any]:
        """Тест risk-engine score"""
        test_name = "Risk Engine Score"

        try:
            # Используем тестовый ID лота
            result = await self.api_client.get_risk_score("test-lot-123")

            if result and "score" in result:
                score = result.get("score")
                if 0.0 <= score <= 1.0:
                    return {
                        "name": test_name,
                        "status": "PASS",
                        "message": f"Risk score valid: {score}",
                    }
                else:
                    return {
                        "name": test_name,
                        "status": "FAIL",
                        "message": f"Invalid risk score range: {score}",
                    }
            else:
                return {
                    "name": test_name,
                    "status": "FAIL",
                    "message": f"Invalid risk score response: {result}",
                }
        except Exception as e:
            return {
                "name": test_name,
                "status": "FAIL",
                "message": f"Risk score error: {e}",
            }

    async def test_embedding_service(self) -> dict[str, Any]:
        """Тест embedding-api"""
        test_name = "Embedding Service"

        try:
            result = await self.api_client.embed_text("Тестовый текст для эмбеддинга")

            if result and "embedding" in result and len(result["embedding"]) > 0:
                return {
                    "name": test_name,
                    "status": "PASS",
                    "message": f"Embedding generated, dimension: {len(result['embedding'])}",
                }
            else:
                return {
                    "name": test_name,
                    "status": "FAIL",
                    "message": f"Invalid embedding response: {result}",
                }
        except Exception as e:
            return {
                "name": test_name,
                "status": "FAIL",
                "message": f"Embedding error: {e}",
            }

    async def test_rate_limiting(self) -> dict[str, Any]:
        """Тест rate limiting (опционально)"""
        test_name = "Rate Limiting"

        try:
            # Отправляем несколько быстрых запросов
            tasks = [self.api_client.health_check() for _ in range(5)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Проверяем, что не все запросы заблокированы
            successful_requests = sum(
                1 for r in results if not isinstance(r, Exception)
            )

            if successful_requests > 0:
                return {
                    "name": test_name,
                    "status": "PASS",
                    "message": f"Rate limiting working: {successful_requests}/5 requests succeeded",
                }
            else:
                return {
                    "name": test_name,
                    "status": "FAIL",
                    "message": "All requests blocked by rate limiting",
                }
        except Exception as e:
            return {
                "name": test_name,
                "status": "FAIL",
                "message": f"Rate limiting test error: {e}",
            }

    async def run_all_tests(self) -> bool:
        """Запуск всех тестов"""
        tests = [
            self.test_database_health(),
            self.test_api_health_check(),
            self.test_api_info_endpoint(),
            self.test_calc_service_vat(),
            self.test_calc_service_margin(),
            self.test_doc_service_tldr(),
            self.test_risk_engine_score(),
            self.test_embedding_service(),
            self.test_rate_limiting(),
        ]

        logger.info("🚀 Running smoke tests...")

        try:
            self.results = await asyncio.gather(*tests)
        except Exception as e:
            logger.error(f"❌ Test execution failed: {e}")
            return False

        # Выводим результаты
        passed = 0
        failed = 0

        print("\n" + "=" * 60)
        print("SMOKE TEST RESULTS")
        print("=" * 60)

        for result in self.results:
            status_icon = "✅" if result["status"] == "PASS" else "❌"
            print(f"{status_icon} {result['name']}: {result['message']}")

            if result["status"] == "PASS":
                passed += 1
            else:
                failed += 1

        print("=" * 60)
        print(f"TOTAL: {passed + failed} tests, {passed} passed, {failed} failed")

        if failed > 0:
            print("❌ Some tests failed!")
            return False
        else:
            print("✅ All tests passed!")
            return True


async def main():
    """Основная функция"""
    runner = SmokeTestRunner()

    try:
        await runner.setup()
        success = await runner.run_all_tests()

        # Возвращаем код выхода
        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"❌ Smoke tests failed to run: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Проверяем переменные окружения
    if not os.getenv("ZAKUPAI_API_URL"):
        print("❌ ZAKUPAI_API_URL not set")
        print("Example: export ZAKUPAI_API_URL=http://localhost:8080")
        sys.exit(1)

    if not os.getenv("ZAKUPAI_API_KEY"):
        print("❌ ZAKUPAI_API_KEY not set")
        print("Example: export ZAKUPAI_API_KEY=your-api-key")
        sys.exit(1)

    asyncio.run(main())
