"""
Обновленный интеграционный модуль для работы с внешними сервисами ZakupAI v2
Использует новый универсальный клиент GraphQL v3 API
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

import aiohttp
from config import config
from error_handler import handle_api_error
from goszakup_client_extensions import GoszakupClientFull

# Импортируем новый универсальный клиент GraphQL v3
from goszakup_client_v3 import LotStatus, TradeMethod

# Для обратной совместимости
try:
    # Импортируем старую поисковую систему как fallback
    from search import GoszakupSearchService, SearchStrategy, search_lots_for_telegram

    # Импортируем гибридную поисковую систему
    from search.hybrid_search import HybridSearchService
    from search.hybrid_search import SearchStrategy as HybridSearchStrategy
    from search.morphology import get_morphology_analyzer

    LEGACY_SEARCH_AVAILABLE = True
except ImportError:
    LEGACY_SEARCH_AVAILABLE = False

logger = logging.getLogger(__name__)


class BillingServiceV2:
    """Обновленный сервис для работы с биллинговой системой"""

    def __init__(self):
        self.base_url = config.api.billing_service_url

    async def validate_key_and_log_usage(
        self, api_key: str, user_id: int, endpoint: str, cost: int = 1
    ) -> dict[str, Any]:
        """Универсальная проверка ключа и логирование использования"""

        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

        # Валидация ключа
        validate_data = {"api_key": api_key, "endpoint": endpoint, "cost": cost}

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=config.security.request_timeout),
                connector=aiohttp.TCPConnector(ssl=config.security.ssl_verify),
            ) as session:
                # Проверяем ключ и лимиты
                async with session.post(
                    f"{self.base_url}/billing/validate_key",
                    json=validate_data,
                    headers=headers,
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        if data.get("valid", False):
                            # Логируем использование
                            log_data = {
                                "api_key": api_key,
                                "user_id": user_id,
                                "endpoint": endpoint,
                                "cost": cost,
                                "timestamp": datetime.utcnow().isoformat(),
                            }

                            async with session.post(
                                f"{self.base_url}/billing/log_usage",
                                json=log_data,
                                headers=headers,
                            ) as log_response:
                                if log_response.status != 200:
                                    logger.warning(
                                        f"Failed to log usage: {log_response.status}"
                                    )

                            return {
                                "valid": True,
                                "user_plan": data.get("user_plan", "free"),
                                "usage_count": data.get("usage_count", 0),
                                "usage_limit": data.get("usage_limit", 100),
                            }

                        return {
                            "valid": False,
                            "error": data.get("error", "Invalid key"),
                        }

                    else:
                        logger.error(f"Billing API error: {response.status}")
                        return {
                            "valid": False,
                            "error": handle_api_error(None, "billing"),
                        }

        except Exception as e:
            logger.error(f"Error validating API key: {type(e).__name__}")
            return {"valid": False, "error": handle_api_error(e, "billing validation")}


class GoszakupServiceV2:
    """Обновленный сервис для работы с API goszakup.gov.kz v3 GraphQL"""

    def __init__(self):
        # Получаем токен GraphQL v3 из конфигурации или переменных окружения
        self.v3_token = self._get_v3_token()

        # Создаем новый универсальный клиент GraphQL v3
        self.new_client = None  # Будет создан при первом использовании

        # Для обратной совместимости сохраняем старые клиенты как fallback
        if LEGACY_SEARCH_AVAILABLE:
            self.v2_token = self._get_v2_token()

            # Создаем поисковый сервис с поддержкой n8n webhook (старая система)
            self.search_service = GoszakupSearchService(
                graphql_v2_token=self.v2_token,
                rest_v3_token=self.v3_token,
                default_strategy=SearchStrategy.AUTO,
                n8n_webhook_url=os.getenv("N8N_WEBHOOK_URL"),
            )

            # Создаем новый гибридный поисковый сервис
            self.hybrid_search = HybridSearchService(
                graphql_v2_token=self.v2_token,
                rest_v3_token=self.v3_token,
                n8n_webhook_url=os.getenv("N8N_WEBHOOK_URL"),
                default_strategy=HybridSearchStrategy.AUTO,
            )

            # Морфологический анализатор
            self.morphology = get_morphology_analyzer()

        logger.info(
            f"GoszakupServiceV2 initialized: v3_token={bool(self.v3_token)}, "
            f"legacy_search={LEGACY_SEARCH_AVAILABLE}"
        )

    def _get_v2_token(self) -> str | None:
        """Получение токена GraphQL v2"""
        # Приоритет: переменная окружения -> конфигурация
        token = os.getenv("GOSZAKUP_V2_TOKEN")

        if (
            not token
            and hasattr(config, "goszakup")
            and hasattr(config.goszakup, "v2_token")
        ):
            token = config.goszakup.v2_token

        if not token and config.api and hasattr(config.api, "goszakup_v2_token"):
            token = config.api.goszakup_v2_token

        return token

    def _get_v3_token(self) -> str | None:
        """Получение токена GraphQL v3"""
        # Приоритет: переменная окружения -> конфигурация
        token = os.getenv("GOSZAKUP_V3_TOKEN")

        if (
            not token
            and hasattr(config, "goszakup")
            and hasattr(config.goszakup, "v3_token")
        ):
            token = config.goszakup.v3_token

        if not token and config.api and hasattr(config.api, "goszakup_v3_token"):
            token = config.api.goszakup_v3_token

        # Также пробуем использовать токен из переменной окружения с безопасным значением по умолчанию
        if not token:
            token = os.getenv("GOSZAKUP_V3_FALLBACK_TOKEN", "dummy-token-for-tests")

        return token

    async def _get_new_client(self) -> GoszakupClientFull:
        """Получение нового GraphQL v3 клиента (создается по требованию)"""
        if self.new_client is None:
            if not self.v3_token:
                raise Exception("GraphQL v3 token not available")

            # Создаем новый клиент
            self.new_client = GoszakupClientFull(
                token=self.v3_token,
                graphql_url="https://ows.goszakup.gov.kz/v3/graphql",
                timeout=30,
                enable_cache=True,
                cache_ttl=300,  # 5 минут кеш
            )

        return self.new_client

    async def search_lots(
        self, query: str, limit: int = 10, offset: int = 0, user_id: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Поиск лотов с использованием нового GraphQL v3 клиента

        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов
            offset: Смещение для пагинации (по умолчанию 0)
            user_id: ID пользователя для метрик (опционально)

        Returns:
            Список лотов в старом формате для совместимости
        """
        try:
            # Используем новый GraphQL v3 клиент
            client = await self._get_new_client()

            async with client:
                # Простой поиск по ключевому слову
                # Запрашиваем больше лотов, чтобы после фильтрации активных осталось достаточно
                # Для пагинации нужно получить еще больше результатов
                search_limit = max(
                    (limit + offset) * 4, 50
                )  # Запрашиваем в 4 раза больше от (limit + offset)
                results = await client.search_lots(keyword=query, limit=search_limit)

                logger.info(
                    f"New GraphQL v3 search completed: query='{query}', results={len(results)}"
                )

                # Конвертируем в старый формат для совместимости
                formatted_lots = []

                for result in results:
                    # Извлекаем даты из TrdBuy объекта
                    start_date = ""
                    end_date = ""
                    publish_date = ""

                    if result.trdBuy and isinstance(result.trdBuy, dict):
                        start_date = result.trdBuy.get("startDate", "") or ""
                        end_date = result.trdBuy.get("endDate", "") or ""
                        publish_date = result.trdBuy.get("publishDate", "") or ""

                    formatted_lot = {
                        "id": result.lotNumber,
                        "lot_number": result.lotNumber,
                        "name": result.nameRu,
                        "customer": result.customerNameRu,
                        "price": result.amount,
                        "currency": "тг",
                        "status": result.status,
                        "deadline": end_date,
                        "start_date": start_date,
                        "publish_date": publish_date,
                        "url": f"https://goszakup.gov.kz/ru/search/lots?filter%5Bnumber%5D={result.lotNumber.split('-')[0]}",
                        "description": result.descriptionRu,
                        "trade_method": result.tradeMethod,
                        "customer_bin": result.customerBin,
                        "quantity": result.count,
                        "source": "graphql_v3",
                    }
                    formatted_lots.append(formatted_lot)

                # Фильтруем только активные лоты
                active_lots = [
                    lot
                    for lot in formatted_lots
                    if is_active_lot(lot.get("status", ""))
                ]

                # Применяем пагинацию (offset и limit)
                paginated_lots = active_lots[offset : offset + limit]

                return paginated_lots

        except Exception as e:
            logger.error(f"GraphQL v3 search failed: {e}")

            # Fallback на старую систему если доступна
            if LEGACY_SEARCH_AVAILABLE:
                try:
                    logger.info("Falling back to legacy search system")
                    search_result = await self.hybrid_search.search_lots(
                        query=query,
                        limit=limit,
                        user_id=user_id,
                        use_morphology=True,
                        use_relevance_filter=True,
                    )

                    # Конвертируем в старый формат
                    formatted_lots = []
                    for result in search_result.lots:
                        formatted_lot = {
                            "id": result.lot_number or result.announcement_number,
                            "name": result.lot_name,
                            "customer": result.customer_name,
                            "price": result.amount,
                            "currency": result.currency,
                            "status": result.status,
                            "deadline": result.deadline or "",
                            "url": result.url or "",
                            "description": result.lot_description,
                            "trade_method": result.trade_method,
                            "customer_bin": result.customer_bin,
                            "quantity": result.quantity,
                            "source": result.source,
                        }
                        formatted_lots.append(formatted_lot)

                    return formatted_lots
                except Exception as fallback_error:
                    logger.error(
                        f"Legacy fallback search also failed: {fallback_error}"
                    )

            # Если всё не работает, возвращаем пустой список
            return []

    async def search_lots_advanced(
        self,
        keyword: str | None = None,
        customer_bin: str | None = None,
        trade_methods: list[str] | None = None,
        statuses: list[str] | None = None,
        min_amount: float | None = None,
        max_amount: float | None = None,
        limit: int = 10,
        user_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Расширенный поиск лотов с новым GraphQL v3 клиентом

        Args:
            keyword: Ключевое слово
            customer_bin: БИН заказчика
            trade_methods: Способы закупки
            statuses: Статусы лотов
            min_amount: Минимальная сумма
            max_amount: Максимальная сумма
            limit: Максимальное количество результатов
            user_id: ID пользователя для метрик (опционально)

        Returns:
            Список найденных лотов
        """
        try:
            # Используем новый GraphQL v3 клиент
            client = await self._get_new_client()

            async with client:
                # Подготавливаем параметры поиска
                search_params = {"keyword": keyword, "limit": limit}

                # Добавляем БИН заказчика если указан
                if customer_bin:
                    search_params["customer_bin"] = [customer_bin]

                # Конвертируем способы закупки в TradeMethod enum
                if trade_methods:
                    trade_method_enums = []
                    for method in trade_methods:
                        if method.lower() in ["открытый конкурс", "open_tender", "1"]:
                            trade_method_enums.append(TradeMethod.OPEN_TENDER)
                        elif method.lower() in [
                            "запрос ценовых предложений",
                            "request_quotations",
                            "2",
                        ]:
                            trade_method_enums.append(TradeMethod.REQUEST_QUOTATIONS)
                        elif method.lower() in [
                            "из одного источника",
                            "from_one_source",
                            "3",
                        ]:
                            trade_method_enums.append(TradeMethod.FROM_ONE_SOURCE)
                        elif method.lower() in [
                            "электронный магазин",
                            "electronic_store",
                            "5",
                        ]:
                            trade_method_enums.append(TradeMethod.ELECTRONIC_STORE)

                    if trade_method_enums:
                        search_params["trade_methods"] = trade_method_enums

                # Конвертируем статусы в LotStatus enum
                if statuses:
                    status_enums = []
                    for status in statuses:
                        if status.lower() in ["опубликован", "published", "2"]:
                            status_enums.append(LotStatus.PUBLISHED)
                        elif status.lower() in [
                            "прием заявок",
                            "accepting_applications",
                            "3",
                        ]:
                            status_enums.append(LotStatus.ACCEPTING_APPLICATIONS)
                        elif status.lower() in ["завершен", "completed", "6"]:
                            status_enums.append(LotStatus.COMPLETED)

                    if status_enums:
                        search_params["status"] = status_enums

                # Добавляем диапазон сумм
                if min_amount is not None and max_amount is not None:
                    search_params["amount_range"] = (min_amount, max_amount)

                # Выполняем поиск
                results = await client.search_lots(**search_params)

                logger.info(
                    f"Advanced GraphQL v3 search completed: results={len(results)}"
                )

                # Конвертируем в старый формат
                formatted_lots = []

                for result in results:
                    formatted_lot = {
                        "id": result.lotNumber,
                        "name": result.nameRu,
                        "customer": result.customerNameRu,
                        "price": result.amount,
                        "currency": "тг",
                        "status": result.status,
                        "deadline": result.endDate or "",
                        "url": f"https://goszakup.gov.kz/ru/announce/index/{result.id}",
                        "description": result.descriptionRu,
                        "trade_method": result.tradeMethod,
                        "customer_bin": result.customerBin,
                        "quantity": result.count,
                        "source": "graphql_v3_advanced",
                    }
                    formatted_lots.append(formatted_lot)

                return formatted_lots

        except Exception as e:
            logger.error(f"Advanced GraphQL v3 search failed: {e}")

            # Fallback на старую систему если доступна
            if LEGACY_SEARCH_AVAILABLE:
                try:
                    logger.info("Falling back to legacy advanced search")
                    search_result = await self.hybrid_search.search_complex(
                        keyword=keyword,
                        customer_bin=customer_bin,
                        customer_name=None,
                        trade_methods=trade_methods,
                        statuses=statuses,
                        min_amount=min_amount,
                        max_amount=max_amount,
                        limit=limit,
                        user_id=user_id,
                    )

                    # Конвертируем в старый формат
                    formatted_lots = []
                    for result in search_result.lots:
                        formatted_lot = {
                            "id": result.lot_number or result.announcement_number,
                            "name": result.lot_name,
                            "customer": result.customer_name,
                            "price": result.amount,
                            "currency": result.currency,
                            "status": result.status,
                            "deadline": result.deadline or "",
                            "url": result.url or "",
                            "description": result.lot_description,
                            "trade_method": result.trade_method,
                            "customer_bin": result.customer_bin,
                            "quantity": result.quantity,
                            "source": result.source,
                        }
                        formatted_lots.append(formatted_lot)

                    return formatted_lots
                except Exception as fallback_error:
                    logger.error(
                        f"Legacy advanced search fallback failed: {fallback_error}"
                    )

            # Если всё не работает, возвращаем пустой список
            return []

    async def get_lot_by_number(self, lot_number: str) -> dict[str, Any] | None:
        """
        Получение конкретного лота по номеру

        Args:
            lot_number: Номер лота

        Returns:
            Найденный лот или None
        """
        try:
            # Используем гибридную систему для поиска по номеру
            result = await self.hybrid_search.get_lot_by_number(lot_number)

            if result:
                return {
                    "id": result.lot_number or result.announcement_number,
                    "name": result.lot_name,
                    "customer": result.customer_name,
                    "price": result.amount,
                    "currency": result.currency,
                    "status": result.status,
                    "deadline": result.deadline or "",
                    "url": result.url or "",
                    "description": result.lot_description,
                    "trade_method": result.trade_method,
                    "customer_bin": result.customer_bin,
                    "quantity": result.quantity,
                    "source": result.source,
                }

            return None

        except Exception as e:
            logger.error(f"Hybrid get lot by number failed: {e}")
            # Fallback на старую систему
            try:
                result = await self.search_service.get_lot_by_number(lot_number)

                if result:
                    return {
                        "id": result.lot_number or result.announcement_number,
                        "name": result.lot_name,
                        "customer": result.customer_name,
                        "price": result.amount,
                        "currency": result.currency,
                        "status": result.status,
                        "deadline": result.deadline or "",
                        "url": result.url or "",
                        "description": result.lot_description,
                        "trade_method": result.trade_method,
                        "customer_bin": result.customer_bin,
                        "quantity": result.quantity,
                        "source": result.source,
                    }

                return None
            except Exception as fallback_error:
                logger.error(f"Fallback get lot by number failed: {fallback_error}")
                return None

    def get_search_statistics(self) -> dict[str, Any]:
        """Получение статистики поиска"""
        stats = {
            "graphql_v3_available": bool(self.v3_token),
            "new_client_initialized": self.new_client is not None,
        }

        # Получаем статистику нового клиента если доступен
        if self.new_client:
            try:
                new_client_stats = asyncio.run(self.new_client.get_stats())
                stats.update(new_client_stats)
            except Exception as e:
                logger.warning(f"Failed to get new client stats: {e}")

        # Для обратной совместимости добавляем статистику старых систем
        if LEGACY_SEARCH_AVAILABLE:
            try:
                old_stats = self.search_service.get_search_statistics()
                hybrid_stats = self.hybrid_search.get_search_statistics()

                stats.update(
                    {
                        "legacy_system": old_stats,
                        "hybrid_system": hybrid_stats,
                        "morphology": self.morphology.get_statistics(),
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to get legacy stats: {e}")
        else:
            # Заглушки для обратной совместимости
            stats.update(
                {
                    "v2_requests": 0,
                    "v3_rest_requests": 0,
                    "v3_graphql_requests": 0,
                    "fallback_requests": 0,
                    "failed_requests": 0,
                }
            )

        return stats

    def is_v2_available(self) -> bool:
        """Проверка доступности GraphQL v2"""
        return self.v2_token is not None

    def is_v3_available(self) -> bool:
        """Проверка доступности REST v3"""
        return self.v3_token is not None


class ZakupAIServiceV2:
    """Обновленный сервис для работы с внешним API ZakupAI"""

    def __init__(self):
        self.base_url = config.api.zakupai_base_url

    async def call_endpoint(
        self, endpoint: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Универсальный вызов API endpoints"""

        headers = {"Content-Type": "application/json"}

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=config.security.request_timeout),
                connector=aiohttp.TCPConnector(ssl=config.security.ssl_verify),
            ) as session:
                async with session.post(
                    f"{self.base_url}/{endpoint}",
                    json=data,
                    headers=headers,
                ) as response:
                    if response.status == 200:
                        return await response.json()

                    logger.error(f"ZakupAI API error for {endpoint}: {response.status}")
                    return None

        except Exception as e:
            logger.error(f"Error calling {endpoint}: {type(e).__name__}")
            return None


# Инициализация обновленных сервисов
billing_service_v2 = BillingServiceV2()
goszakup_service_v2 = GoszakupServiceV2()
zakupai_service_v2 = ZakupAIServiceV2()


def is_active_lot(status: str) -> bool:
    """Проверяет, является ли лот активным по статусу"""
    active_statuses = {
        "Опубликован",
        "Опубликован (прием ценовых предложений)",
        "Опубликован (прием заявок)",
        "Проект",
    }
    return status in active_statuses


def calculate_remaining_time(end_date: str) -> str:
    """Вычисляет оставшееся время до окончания без секунд"""
    if not end_date:
        return ""

    try:
        import re
        from datetime import datetime

        # Парсим дату в различных форматах
        date_formats = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d",
            "%d.%m.%Y %H:%M",
            "%d.%m.%Y",
        ]

        # Очищаем дату от лишних символов
        clean_date = re.sub(r"[Z+]\d{2}:\d{2}$", "", end_date.strip())

        end_datetime = None
        for fmt in date_formats:
            try:
                end_datetime = datetime.strptime(clean_date, fmt)
                break
            except ValueError:
                continue

        if not end_datetime:
            return f"до {clean_date[:16]}"

        now = datetime.now()
        if end_datetime <= now:
            return "Истек"

        diff = end_datetime - now
        days = diff.days
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60

        if days > 0:
            return f"{days} дн. {hours} ч."
        elif hours > 0:
            return f"{hours} ч. {minutes} мин."
        elif minutes > 0:
            return f"{minutes} мин."
        else:
            return "Менее минуты"

    except Exception:
        # Если не удалось распарсить дату, просто возвращаем первые 16 символов
        return f"до {end_date[:16]}"


def format_search_results_v2(
    lots: list[dict[str, Any]],
    show_source: bool = False,
    show_pagination: bool = False,
    offset: int = 0,
) -> str:
    """
    Обновленное форматирование результатов поиска для отображения в боте

    Args:
        lots: Список найденных лотов
        show_source: Показывать источник данных
        show_pagination: Показывать кнопку "Дальше?"

    Returns:
        Форматированный текст для бота
    """
    if not lots:
        return "🔍 Лоты не найдены по вашему запросу."

    # Лоты уже отфильтрованы и пагинированы в search_lots
    display_lots = lots

    # Для первой страницы показываем общую статистику, для последующих - текущую страницу
    if offset == 0:
        text = "🔍 Найдено активных лотов\n"
        text += f"📄 Показано: {len(display_lots)}\n\n"
    else:
        text = f"🔍 Продолжение поиска (страница {(offset // 10) + 1})\n"
        text += f"📄 Показано: {len(display_lots)} лотов\n\n"

    for i, lot in enumerate(display_lots, offset + 1):
        price_str = (
            f"{lot['price']:,.0f} {lot.get('currency', 'тг')}"
            if lot.get("price", 0) > 0
            else "Цена не указана"
        )

        text += f"<b>{i}. {lot['name'][:100]}</b>\n"
        if lot.get("lot_number"):
            text += f"🔢 Лот: <code>{lot['lot_number']}</code>\n"
        text += f"💰 {price_str}\n"
        text += f"🏢 {lot.get('customer', 'Заказчик не указан')}\n"

        if lot.get("customer_bin"):
            text += f"🏛️ БИН: <code>{lot['customer_bin']}</code>\n"

        if lot.get("trade_method"):
            text += f"🛒 {lot['trade_method']}\n"

        text += f"📊 {lot.get('status', 'Статус не указан')}\n"

        if lot.get("quantity", 0) > 0:
            text += f"🔢 Количество: {lot['quantity']}\n"

        if lot.get("description") and len(lot["description"]) > 10:
            description = (
                lot["description"][:150] + "..."
                if len(lot["description"]) > 150
                else lot["description"]
            )
            text += f"📋 {description}\n"

        # Даты начала и окончания приема заявок
        if lot.get("start_date"):
            text += f"📅 Начало приема: {lot['start_date'][:16]}\n"

        if lot.get("deadline"):
            remaining = calculate_remaining_time(lot["deadline"])
            if remaining:
                text += f"⏰ Окончание: {lot['deadline'][:16]}\n"
                if remaining != "Истек":
                    text += f"⏳ Осталось: {remaining}\n"
            else:
                text += f"⏰ До: {lot['deadline'][:16]}\n"

        if lot.get("url"):
            text += f"🔗 <a href='{lot['url']}'>Открыть на сайте</a>\n"

        if show_source and lot.get("source"):
            source_emoji = (
                "🚀"
                if lot["source"] == "graphql_v2"
                else "🔄" if lot["source"] == "graphql_v3" else "📡"
            )
            text += f"{source_emoji} Источник: {lot['source']}\n"

        text += "\n"

    # Добавляем пагинацию если запрошено
    if show_pagination and len(display_lots) > 0:
        text += "➡️ <b>Дальше?</b> Используйте /search_continue для продолжения\n\n"

    return text


async def search_lots_for_telegram_v2(
    query: str,
    limit: int = 10,
    offset: int = 0,
    show_source: bool = False,
    user_id: int | None = None,
) -> str:
    """
    Быстрая функция поиска для Telegram бота (обновленная версия с GraphQL v3)

    Args:
        query: Поисковый запрос
        limit: Максимальное количество результатов
        offset: Смещение для пагинации (по умолчанию 0)
        show_source: Показывать источник данных
        user_id: ID пользователя для метрик (опционально)

    Returns:
        Форматированный текст для отправки пользователю
    """
    try:
        lots = await goszakup_service_v2.search_lots(
            query, limit=limit, offset=offset, user_id=user_id
        )

        if not lots:
            return "❌ Лоты не найдены по вашему запросу"

        return format_search_results_v2(
            lots, show_source=show_source, show_pagination=True, offset=offset
        )
    except Exception as e:
        logger.error(f"Telegram search v2 failed: {e}")
        return f"❌ Произошла ошибка поиска: {str(e)}"


# Экспортируем функции для совместимости со старым кодом
search_lots_for_telegram = search_lots_for_telegram_v2
format_search_results = format_search_results_v2

# Основные сервисы для использования в боте
billing_service = billing_service_v2
goszakup_service = goszakup_service_v2
zakupai_service = zakupai_service_v2
