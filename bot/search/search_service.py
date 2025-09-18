"""
Основной поисковый сервис для работы с API Госзакупок
Теперь использует новый GraphQL v3 клиент с fallback на старые системы
"""

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import aiohttp

# Старые клиенты как fallback
from .graphql_v2_client import GraphQLV2Client, LotResult
from .mappings import get_lot_status_name, get_trade_method_name, mappings
from .rest_v3_client import RestV3Client

logger = logging.getLogger(__name__)

# Новый GraphQL v3 клиент
try:
    import sys

    sys.path.append("..")
    from goszakup_client_extensions import GoszakupClientFull

    NEW_CLIENT_AVAILABLE = True
except ImportError:
    NEW_CLIENT_AVAILABLE = False
    logger.warning("New GraphQL v3 client not available")


class SearchStrategy(Enum):
    """Стратегии поиска"""

    AUTO = "auto"  # Автоматический выбор
    GRAPHQL_V2 = "v2"  # Принудительно GraphQL v2
    REST_V3 = "v3_rest"  # Принудительно REST v3
    GRAPHQL_V3 = "v3_gql"  # Принудительно GraphQL v3


class SearchComplexity(Enum):
    """Сложность поискового запроса"""

    SIMPLE = "simple"  # Простое ключевое слово
    MODERATE = "moderate"  # Несколько фильтров
    COMPLEX = "complex"  # Множество фильтров и условий


@dataclass
class SearchQuery:
    """Структурированный поисковый запрос"""

    keyword: str | None = None
    customer_bin: str | None = None
    customer_name: str | None = None
    trade_method_ids: list[int] | None = None
    status_ids: list[int] | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    announcement_number: str | None = None
    publish_date_from: str | None = None
    publish_date_to: str | None = None
    end_date_from: str | None = None
    end_date_to: str | None = None
    region_codes: list[str] | None = None
    limit: int = 10
    offset: int = 0


class GoszakupSearchService:
    """Главный поисковый сервис для работы с API Госзакупок"""

    def __init__(
        self,
        graphql_v2_token: str | None = None,
        rest_v3_token: str | None = None,
        default_strategy: SearchStrategy = SearchStrategy.AUTO,
        enable_metrics: bool = True,
        n8n_webhook_url: str | None = None,
    ):
        """
        Инициализация поискового сервиса

        Args:
            graphql_v2_token: Токен для GraphQL v2 API
            rest_v3_token: Токен для GraphQL v3 API (теперь основной)
            default_strategy: Стратегия поиска по умолчанию
            enable_metrics: Включить сбор метрик пользователей
        """
        self.graphql_v2_client = (
            GraphQLV2Client(graphql_v2_token) if graphql_v2_token else None
        )
        self.rest_v3_client = RestV3Client(rest_v3_token)
        self.default_strategy = default_strategy
        self.enable_metrics = enable_metrics
        self.n8n_webhook_url = n8n_webhook_url or os.getenv("N8N_WEBHOOK_URL")

        # Новый GraphQL v3 клиент
        self.graphql_v3_token = rest_v3_token or "cc9ae7eb4025aca71e2e445823d88b86"
        self.new_client = None  # Создается по требованию

        # Импорт метрик (отложенный для избежания циклических зависимостей)
        if self.enable_metrics:
            try:
                from ..user_metrics import metrics_service

                self.metrics_service = metrics_service
            except ImportError:
                logger.warning("User metrics service not available, disabling metrics")
                self.enable_metrics = False
                self.metrics_service = None
        else:
            self.metrics_service = None

        # Кэш для проверки доступности API
        self._v2_available: bool | None = None
        self._v3_available: bool | None = None

        # Статистика использования
        self.stats = {
            "v2_requests": 0,
            "v3_rest_requests": 0,
            "v3_graphql_requests": 0,
            "new_graphql_v3_requests": 0,
            "fallback_requests": 0,
            "failed_requests": 0,
            "n8n_requests": 0,
            "n8n_fallbacks": 0,
        }

    async def _get_new_client(self) -> "GoszakupClientFull":
        """Получение нового GraphQL v3 клиента"""
        if not NEW_CLIENT_AVAILABLE:
            raise Exception("New GraphQL v3 client not available")

        if self.new_client is None:
            self.new_client = GoszakupClientFull(
                token=self.graphql_v3_token,
                graphql_url="https://ows.goszakup.gov.kz/v3/graphql",
                timeout=30,
                enable_cache=True,
                cache_ttl=300,
            )

        return self.new_client

    async def search_lots(
        self,
        query: str | SearchQuery,
        strategy: SearchStrategy | None = None,
        limit: int = 10,
        user_id: int | None = None,
    ) -> list[LotResult]:
        """
        Главная функция поиска лотов с поддержкой n8n webhook и fallback логики

        Args:
            query: Поисковый запрос (строка или структурированный объект)
            strategy: Стратегия поиска (или использовать по умолчанию)
            limit: Максимальное количество результатов
            user_id: ID пользователя для метрик (опционально)

        Returns:
            Список найденных лотов
        """
        start_time = time.time()
        original_query = query if isinstance(query, str) else (query.keyword or "")
        used_strategy = None
        error_message = None

        try:
            # Если это строковый запрос, сначала пробуем новый GraphQL v3 клиент
            if isinstance(query, str) and query.strip() and NEW_CLIENT_AVAILABLE:
                try:
                    return await self._search_with_new_client(query, limit, user_id)
                except Exception as e:
                    logger.warning(
                        f"New GraphQL v3 client failed: {e}, falling back to legacy"
                    )

            # Fallback на старую логику поиска с регистронезависимостью
            if isinstance(query, str) and query.strip():
                return await self._search_with_case_normalization(query, limit, user_id)

            # Парсинг запроса для объектов SearchQuery
            if isinstance(query, str):
                parsed_query = await self._parse_string_query(query)
            else:
                parsed_query = query

            parsed_query.limit = limit

            # Определение стратегии поиска
            search_strategy = strategy or self.default_strategy

            if search_strategy == SearchStrategy.AUTO:
                search_strategy = await self._determine_optimal_strategy(parsed_query)

            used_strategy = search_strategy.value

            # Выполнение поиска
            try:
                results = await self._execute_search(parsed_query, search_strategy)

                # Пост-обработка результатов
                processed_results = await self._post_process_results(results)

                logger.info(
                    f"Search completed: {len(processed_results)} lots found using {search_strategy.value}"
                )

                # Логируем успешный поиск
                if self.enable_metrics and user_id and self.metrics_service:
                    execution_time = int((time.time() - start_time) * 1000)
                    self.metrics_service.log_search(
                        user_id=user_id,
                        query=original_query,
                        results_count=len(processed_results),
                        api_used=used_strategy,
                        execution_time_ms=execution_time,
                        success=True,
                    )

                return processed_results

            except Exception as e:
                logger.error(
                    f"Search failed with strategy {search_strategy.value}: {e}"
                )

                # Попытка fallback
                if search_strategy != SearchStrategy.REST_V3:
                    logger.info("Attempting fallback to REST v3")
                    try:
                        results = await self._execute_search(
                            parsed_query, SearchStrategy.REST_V3
                        )
                        processed_results = await self._post_process_results(results)

                        used_strategy = "rest_v3_fallback"
                        self.stats["fallback_requests"] += 1

                        logger.info(
                            f"Fallback successful: {len(processed_results)} lots found"
                        )

                        # Логируем успешный fallback
                        if self.enable_metrics and user_id and self.metrics_service:
                            execution_time = int((time.time() - start_time) * 1000)
                            self.metrics_service.log_search(
                                user_id=user_id,
                                query=original_query,
                                results_count=len(processed_results),
                                api_used=used_strategy,
                                execution_time_ms=execution_time,
                                success=True,
                            )

                        return processed_results

                    except Exception as fallback_error:
                        error_message = f"Fallback also failed: {str(fallback_error)}"
                        logger.error(error_message)
                        raise e from fallback_error
                else:
                    error_message = str(e)
                    raise e

        except Exception as e:
            error_message = error_message or str(e)
            self.stats["failed_requests"] += 1

            # Логируем неудачный поиск
            if self.enable_metrics and user_id and self.metrics_service:
                execution_time = int((time.time() - start_time) * 1000)
                self.metrics_service.log_search(
                    user_id=user_id,
                    query=original_query,
                    results_count=0,
                    api_used=used_strategy or "unknown",
                    execution_time_ms=execution_time,
                    success=False,
                    error_message=error_message,
                )

            raise e

    async def search_by_keyword(
        self, keyword: str, limit: int = 10, user_id: int | None = None
    ) -> list[LotResult]:
        """
        Простой поиск по ключевому слову

        Args:
            keyword: Ключевое слово
            limit: Максимальное количество результатов
            user_id: ID пользователя для метрик (опционально)

        Returns:
            Список найденных лотов
        """
        return await self.search_lots(keyword, limit=limit, user_id=user_id)

    async def search_complex(
        self,
        keyword: str | None = None,
        customer_bin: str | None = None,
        trade_methods: list[str] | None = None,
        statuses: list[str] | None = None,
        min_amount: float | None = None,
        max_amount: float | None = None,
        limit: int = 10,
        user_id: int | None = None,
    ) -> list[LotResult]:
        """
        Сложный поиск с множественными параметрами

        Args:
            keyword: Ключевое слово
            customer_bin: БИН заказчика
            trade_methods: Названия или коды способов закупки
            statuses: Названия или коды статусов
            min_amount: Минимальная сумма
            max_amount: Максимальная сумма
            limit: Максимальное количество результатов
            user_id: ID пользователя для метрик (опционально)

        Returns:
            Список найденных лотов
        """
        # Преобразование названий в ID
        trade_method_ids = []
        if trade_methods:
            for method in trade_methods:
                found_methods = mappings.search_trade_methods(method)
                trade_method_ids.extend([m.id for m in found_methods])

        status_ids = []
        if statuses:
            for status in statuses:
                found_statuses = mappings.search_lot_statuses(status)
                status_ids.extend([s.id for s in found_statuses])

        query = SearchQuery(
            keyword=keyword,
            customer_bin=customer_bin,
            trade_method_ids=trade_method_ids or None,
            status_ids=status_ids or None,
            min_amount=min_amount,
            max_amount=max_amount,
            limit=limit,
        )

        return await self.search_lots(query, user_id=user_id)

    async def get_lot_by_number(self, lot_number: str) -> LotResult | None:
        """
        Получение конкретного лота по номеру

        Args:
            lot_number: Номер лота

        Returns:
            Найденный лот или None
        """
        # Сначала пробуем GraphQL v2
        if self.graphql_v2_client and await self._is_v2_available():
            try:
                result = await self.graphql_v2_client.get_lot_by_number(lot_number)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"GraphQL v2 get lot failed: {e}")

        # Fallback на REST v3
        try:
            query = SearchQuery(keyword=lot_number, limit=1)
            results = await self._execute_search(query, SearchStrategy.REST_V3)

            # Ищем точное совпадение номера лота
            for result in results:
                if result.lot_number == lot_number:
                    return result

        except Exception as e:
            logger.error(f"Failed to get lot by number {lot_number}: {e}")

        return None

    async def format_results_for_telegram(
        self, results: list[LotResult], show_source: bool = False
    ) -> str:
        """
        Форматирование результатов для Telegram бота

        Args:
            results: Результаты поиска
            show_source: Показывать источник данных

        Returns:
            Форматированная строка для отправки пользователю
        """
        if not results:
            return "🔍 Ничего не найдено по вашему запросу."

        formatted = f"📋 Найдено лотов: {len(results)}\n\n"

        for i, result in enumerate(results, 1):
            formatted += f"🔹 **Лот {i}**\n"

            if result.lot_number:
                formatted += f"📝 № лота: `{result.lot_number}`\n"

            if result.announcement_number:
                formatted += f"📋 Объявление: `{result.announcement_number}`\n"

            if result.announcement_name:
                formatted += f"📄 Название: {result.announcement_name}\n"

            formatted += f"📦 Наименование: {result.lot_name}\n"

            if result.lot_description and len(result.lot_description) > 10:
                description = (
                    result.lot_description[:200] + "..."
                    if len(result.lot_description) > 200
                    else result.lot_description
                )
                formatted += f"📋 Описание: {description}\n"

            if result.quantity > 0:
                formatted += f"🔢 Количество: {result.quantity}\n"

            if result.amount > 0:
                formatted += f"💰 Сумма: {result.amount:,.0f} {result.currency}\n"

            formatted += f"🏢 Заказчик: {result.customer_name}\n"

            if result.customer_bin:
                formatted += f"🏛️ БИН: `{result.customer_bin}`\n"

            formatted += f"🛒 Способ закупки: {result.trade_method}\n"
            formatted += f"📌 Статус: {result.status}\n"

            if result.deadline:
                try:
                    deadline_date = datetime.fromisoformat(
                        result.deadline.replace("Z", "+00:00")
                    )
                    formatted += (
                        f"⏰ Срок: {deadline_date.strftime('%d.%m.%Y %H:%M')}\n"
                    )
                except Exception as e:
                    logger.warning(f"Failed to parse deadline '{result.deadline}': {e}")
                    formatted += f"⏰ Срок: {result.deadline}\n"

            if result.url:
                formatted += f"🔗 [Открыть на сайте]({result.url})\n"

            if show_source:
                formatted += f"🔧 Источник: {result.source}\n"

            formatted += "\n" + "─" * 50 + "\n\n"

        return formatted

    async def _parse_string_query(self, query_string: str) -> SearchQuery:
        """
        Парсинг строкового запроса в структурированный объект

        Args:
            query_string: Строка запроса

        Returns:
            Структурированный запрос
        """
        query = SearchQuery()

        # Работаем с копией строки для поиска ключевого слова
        remaining_text = query_string.strip()

        # Поиск специальных параметров в строке
        # Например: "лак БИН:123456789" или "мебель сумма:100000-500000"

        # БИН заказчика
        bin_match = re.search(r"БИН[:\s]+(\d{12})", query_string, re.IGNORECASE)
        if bin_match:
            query.customer_bin = bin_match.group(1)
            remaining_text = remaining_text.replace(bin_match.group(0), "").strip()

        # Диапазон сумм
        amount_match = re.search(
            r"сумма[:\s]+(\d+)[-–](\d+)", query_string, re.IGNORECASE
        )
        if amount_match:
            query.min_amount = float(amount_match.group(1))
            query.max_amount = float(amount_match.group(2))
            remaining_text = remaining_text.replace(amount_match.group(0), "").strip()

        # Номер объявления
        anno_match = re.search(
            r"объявление[:\s]+([A-Z0-9\-]+)", query_string, re.IGNORECASE
        )
        if anno_match:
            query.announcement_number = anno_match.group(1)
            remaining_text = remaining_text.replace(anno_match.group(0), "").strip()

        # Устанавливаем ключевое слово после обработки всех специальных параметров
        query.keyword = remaining_text if remaining_text else None

        return query

    async def _determine_optimal_strategy(self, query: SearchQuery) -> SearchStrategy:
        """
        Определение оптимальной стратегии поиска

        Args:
            query: Поисковый запрос

        Returns:
            Оптимальная стратегия поиска
        """
        complexity = self._assess_query_complexity(query)

        # Проверяем доступность GraphQL v2
        v2_available = await self._is_v2_available()

        if complexity == SearchComplexity.SIMPLE:
            # Простые запросы лучше через REST v3 (быстрее)
            return SearchStrategy.REST_V3

        elif complexity == SearchComplexity.MODERATE:
            # Средние запросы - приоритет GraphQL v2, fallback REST v3
            return SearchStrategy.GRAPHQL_V2 if v2_available else SearchStrategy.REST_V3

        else:  # COMPLEX
            # Сложные запросы - обязательно GraphQL v2 (больше возможностей)
            return (
                SearchStrategy.GRAPHQL_V2 if v2_available else SearchStrategy.GRAPHQL_V3
            )

    def _assess_query_complexity(self, query: SearchQuery) -> SearchComplexity:
        """
        Оценка сложности поискового запроса

        Args:
            query: Поисковый запрос

        Returns:
            Уровень сложности запроса
        """
        filters_count = 0

        # Подсчитываем количество активных фильтров
        if query.keyword:
            filters_count += 1
        if query.customer_bin:
            filters_count += 1
        if query.customer_name:
            filters_count += 1
        if query.trade_method_ids:
            filters_count += 1
        if query.status_ids:
            filters_count += 1
        if query.min_amount is not None or query.max_amount is not None:
            filters_count += 1
        if query.announcement_number:
            filters_count += 1
        if query.publish_date_from or query.publish_date_to:
            filters_count += 1
        if query.end_date_from or query.end_date_to:
            filters_count += 1
        if query.region_codes:
            filters_count += 1

        if filters_count <= 1:
            return SearchComplexity.SIMPLE
        elif filters_count <= 3:
            return SearchComplexity.MODERATE
        else:
            return SearchComplexity.COMPLEX

    async def _execute_search(
        self, query: SearchQuery, strategy: SearchStrategy
    ) -> list[LotResult]:
        """
        Выполнение поиска с заданной стратегией

        Args:
            query: Поисковый запрос
            strategy: Стратегия поиска

        Returns:
            Результаты поиска
        """
        if strategy == SearchStrategy.GRAPHQL_V2:
            if not self.graphql_v2_client:
                raise Exception("GraphQL v2 client not configured")

            if query.keyword and not any(
                [query.customer_bin, query.trade_method_ids, query.status_ids]
            ):
                results = await self.graphql_v2_client.search_by_keyword(
                    query.keyword, query.limit
                )
            else:
                results = await self.graphql_v2_client.search_by_complex_filters(
                    keyword=query.keyword,
                    customer_bin=query.customer_bin,
                    customer_name=query.customer_name,
                    trade_method_ids=query.trade_method_ids,
                    status_ids=query.status_ids,
                    min_amount=query.min_amount,
                    max_amount=query.max_amount,
                    announcement_number=query.announcement_number,
                    limit=query.limit,
                )

            self.stats["v2_requests"] += 1

        elif strategy == SearchStrategy.REST_V3:
            if query.keyword and not any(
                [query.customer_bin, query.trade_method_ids, query.status_ids]
            ):
                results = await self.rest_v3_client.search_by_keyword(
                    query.keyword, query.limit, use_graphql=False
                )
            else:
                results = await self.rest_v3_client.search_by_complex_filters(
                    keyword=query.keyword,
                    customer_bin=query.customer_bin,
                    customer_name=query.customer_name,
                    trade_method_ids=query.trade_method_ids,
                    status_ids=query.status_ids,
                    min_amount=query.min_amount,
                    max_amount=query.max_amount,
                    announcement_number=query.announcement_number,
                    publish_date_from=query.publish_date_from,
                    publish_date_to=query.publish_date_to,
                    end_date_from=query.end_date_from,
                    end_date_to=query.end_date_to,
                    limit=query.limit,
                    use_graphql=False,
                )

            self.stats["v3_rest_requests"] += 1

        elif strategy == SearchStrategy.GRAPHQL_V3:
            if query.keyword and not any(
                [query.customer_bin, query.trade_method_ids, query.status_ids]
            ):
                results = await self.rest_v3_client.search_by_keyword(
                    query.keyword, query.limit, use_graphql=True
                )
            else:
                results = await self.rest_v3_client.search_by_complex_filters(
                    keyword=query.keyword,
                    customer_bin=query.customer_bin,
                    customer_name=query.customer_name,
                    trade_method_ids=query.trade_method_ids,
                    status_ids=query.status_ids,
                    min_amount=query.min_amount,
                    max_amount=query.max_amount,
                    announcement_number=query.announcement_number,
                    publish_date_from=query.publish_date_from,
                    publish_date_to=query.publish_date_to,
                    end_date_from=query.end_date_from,
                    end_date_to=query.end_date_to,
                    limit=query.limit,
                    use_graphql=True,
                )

            self.stats["v3_graphql_requests"] += 1

        else:
            raise Exception(f"Unknown search strategy: {strategy}")

        return results

    async def _post_process_results(self, results: list[LotResult]) -> list[LotResult]:
        """
        Пост-обработка результатов поиска

        Args:
            results: Сырые результаты поиска

        Returns:
            Обработанные результаты
        """
        processed = []

        for result in results:
            # Дополняем названия способов закупки и статусов если они не заполнены
            if result.trade_method == "Не указан" and hasattr(
                result, "trade_method_id"
            ):
                result.trade_method = get_trade_method_name(result.trade_method_id)

            if result.status == "Не указан" and hasattr(result, "status_id"):
                result.status = get_lot_status_name(result.status_id)

            # Убираем дубликаты по номеру лота
            if not any(
                p.lot_number == result.lot_number
                for p in processed
                if result.lot_number
            ):
                processed.append(result)

        # Сортируем по релевантности (по убыванию суммы)
        processed.sort(key=lambda x: x.amount, reverse=True)

        return processed

    async def _is_v2_available(self) -> bool:
        """Проверка доступности GraphQL v2 API"""
        if self._v2_available is not None and self.graphql_v2_client:
            return self._v2_available

        if not self.graphql_v2_client:
            self._v2_available = False
            return False

        try:
            self._v2_available = await self.graphql_v2_client.validate_token()
            return self._v2_available
        except Exception:
            self._v2_available = False
            return False

    async def _search_with_case_normalization(
        self, query: str, limit: int = 10, user_id: int | None = None
    ) -> list[LotResult]:
        """
        Поиск с нормализацией регистра и использованием n8n webhook + fallback логики

        Args:
            query: Поисковый запрос
            limit: Лимит результатов
            user_id: ID пользователя для метрик

        Returns:
            Объединенные результаты поиска без дубликатов
        """
        start_time = time.time()
        raw_query = query.strip()
        normalized_query = raw_query.casefold()

        logger.info(
            f"Starting search: raw='{raw_query}', normalized='{normalized_query}'"
        )

        # Попытка поиска через n8n webhook
        if self.n8n_webhook_url:
            try:
                n8n_results = await self._search_via_n8n_webhook(
                    raw_query, normalized_query, limit
                )
                if n8n_results:
                    logger.info("n8n search used")
                    self.stats["n8n_requests"] += 1

                    # Логируем успешный n8n поиск
                    if self.enable_metrics and user_id and self.metrics_service:
                        execution_time = int((time.time() - start_time) * 1000)
                        self.metrics_service.log_search(
                            user_id=user_id,
                            query=raw_query,
                            results_count=len(n8n_results),
                            api_used="n8n_webhook",
                            execution_time_ms=execution_time,
                            success=True,
                        )

                    return n8n_results

            except Exception as e:
                logger.warning(f"n8n unavailable, fallback → direct search: {e}")
                self.stats["n8n_fallbacks"] += 1

        # Fallback на прямой поиск через GoszakupSearchService
        return await self._search_with_direct_apis(
            raw_query, normalized_query, limit, user_id, start_time
        )

    async def _search_via_n8n_webhook(
        self, raw_query: str, normalized_query: str, limit: int
    ) -> list[LotResult] | None:
        """
        Поиск через n8n webhook

        Args:
            raw_query: Исходный запрос
            normalized_query: Нормализованный запрос
            limit: Лимит результатов

        Returns:
            Результаты поиска или None при ошибке
        """
        if not self.n8n_webhook_url:
            return None

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = {
                "query": raw_query,
                "normalized_query": normalized_query,
                "limit": limit,
            }

            async with session.post(self.n8n_webhook_url, json=payload) as response:
                if response.status != 200:
                    raise Exception(f"n8n webhook returned status {response.status}")

                data = await response.json()

                # Преобразуем данные n8n в LotResult объекты
                results = []
                if "results" in data and isinstance(data["results"], list):
                    for item in data["results"]:
                        try:
                            lot_result = self._convert_n8n_to_lot_result(item)
                            if lot_result:
                                results.append(lot_result)
                        except Exception as e:
                            logger.warning(f"Failed to convert n8n result: {e}")
                            continue

                return results

    def _convert_n8n_to_lot_result(self, n8n_item: dict[str, Any]) -> LotResult | None:
        """
        Конвертация результата n8n в LotResult объект

        Args:
            n8n_item: Элемент данных от n8n

        Returns:
            LotResult объект или None
        """
        try:
            return LotResult(
                lot_number=n8n_item.get("lot_number", ""),
                announcement_number=n8n_item.get("announcement_number", ""),
                announcement_name=n8n_item.get("announcement_name", ""),
                lot_name=n8n_item.get("lot_name", ""),
                lot_description=n8n_item.get("lot_description", ""),
                customer_name=n8n_item.get("customer_name", ""),
                customer_bin=n8n_item.get("customer_bin", ""),
                amount=float(n8n_item.get("amount", 0)),
                currency=n8n_item.get("currency", "тг"),
                quantity=n8n_item.get("quantity", 0),
                trade_method=n8n_item.get("trade_method", "Не указан"),
                status=n8n_item.get("status", "Не указан"),
                deadline=n8n_item.get("deadline", ""),
                url=n8n_item.get("url", ""),
                source="n8n_webhook",
            )
        except Exception as e:
            logger.error(f"Error converting n8n item to LotResult: {e}")
            return None

    async def _search_with_direct_apis(
        self,
        raw_query: str,
        normalized_query: str,
        limit: int,
        user_id: int | None,
        start_time: float,
    ) -> list[LotResult]:
        """
        Прямой поиск через API с нормализацией регистра

        Args:
            raw_query: Исходный запрос
            normalized_query: Нормализованный запрос
            limit: Лимит результатов
            user_id: ID пользователя
            start_time: Время начала поиска

        Returns:
            Объединенные результаты без дубликатов
        """
        all_results = []

        # Параллельный поиск по нормализованному и исходному запросам
        tasks = []

        # Поиск по нормализованному запросу
        if normalized_query != raw_query:
            tasks.append(self._search_single_query(normalized_query, limit))

        # Поиск по исходному запросу
        tasks.append(self._search_single_query(raw_query, limit))

        # Выполняем поиски параллельно
        try:
            results_list = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results_list):
                if isinstance(result, Exception):
                    logger.warning(f"Search task {i} failed: {result}")
                    continue

                if result:
                    all_results.extend(result)

        except Exception as e:
            logger.error(f"Parallel search failed: {e}")
            # Fallback на последовательный поиск
            try:
                if normalized_query != raw_query:
                    norm_results = await self._search_single_query(
                        normalized_query, limit
                    )
                    if norm_results:
                        all_results.extend(norm_results)

                raw_results = await self._search_single_query(raw_query, limit)
                if raw_results:
                    all_results.extend(raw_results)

            except Exception as fallback_e:
                logger.error(f"Sequential search fallback failed: {fallback_e}")
                raise e from fallback_e

        # Удаляем дубликаты по номеру лота
        unique_results = self._remove_duplicates(all_results)

        logger.info(f"Direct search completed: {len(unique_results)} unique lots found")

        # Логируем результат
        if self.enable_metrics and user_id and self.metrics_service:
            execution_time = int((time.time() - start_time) * 1000)
            self.metrics_service.log_search(
                user_id=user_id,
                query=raw_query,
                results_count=len(unique_results),
                api_used="direct_search_combined",
                execution_time_ms=execution_time,
                success=len(unique_results) > 0,
            )

        return unique_results

    async def _search_single_query(self, query: str, limit: int) -> list[LotResult]:
        """
        Поиск по одному запросу через лучшую доступную стратегию

        Args:
            query: Поисковый запрос
            limit: Лимит результатов

        Returns:
            Результаты поиска
        """
        parsed_query = await self._parse_string_query(query)
        parsed_query.limit = limit

        strategy = await self._determine_optimal_strategy(parsed_query)
        results = await self._execute_search(parsed_query, strategy)

        return await self._post_process_results(results)

    def _remove_duplicates(self, results: list[LotResult]) -> list[LotResult]:
        """
        Удаление дубликатов по номеру лота

        Args:
            results: Список результатов с возможными дубликатами

        Returns:
            Список уникальных результатов
        """
        seen_lot_numbers = set()
        unique_results = []

        for result in results:
            # Используем lot_number как ключ уникальности
            lot_key = (
                result.lot_number
                or f"{result.customer_bin}_{result.lot_name}_{result.amount}"
            )

            if lot_key not in seen_lot_numbers:
                seen_lot_numbers.add(lot_key)
                unique_results.append(result)

        return unique_results

    async def _search_with_new_client(
        self, query: str, limit: int, user_id: int | None
    ) -> list[LotResult]:
        """
        Поиск с использованием нового GraphQL v3 клиента

        Args:
            query: Поисковый запрос
            limit: Лимит результатов
            user_id: ID пользователя для метрик

        Returns:
            Результаты поиска в формате LotResult
        """
        start_time = time.time()

        try:
            client = await self._get_new_client()

            async with client:
                # Выполняем поиск через новый клиент
                lots = await client.search_lots(keyword=query, limit=limit)

                # Конвертируем результаты в LotResult формат
                lot_results = []
                for lot in lots:
                    lot_result = LotResult(
                        lot_number=lot.lotNumber,
                        announcement_number="",  # В новом API может не быть
                        announcement_name="",
                        lot_name=lot.nameRu,
                        lot_description=lot.descriptionRu,
                        customer_name=lot.customerNameRu,
                        customer_bin=lot.customerBin,
                        amount=lot.amount,
                        currency="тг",
                        quantity=lot.count,
                        trade_method=lot.tradeMethod,
                        status=lot.status,
                        deadline=lot.endDate or "",
                        url=f"https://goszakup.gov.kz/ru/announce/index/{lot.id}",
                        source="new_graphql_v3",
                    )
                    lot_results.append(lot_result)

                self.stats["new_graphql_v3_requests"] += 1

                logger.info(
                    f"New GraphQL v3 search completed: query='{query}', "
                    f"results={len(lot_results)}, time={time.time() - start_time:.2f}s"
                )

                # Логируем метрики если включены
                if self.enable_metrics and user_id and self.metrics_service:
                    execution_time = int((time.time() - start_time) * 1000)
                    self.metrics_service.log_search(
                        user_id=user_id,
                        query=query,
                        results_count=len(lot_results),
                        api_used="new_graphql_v3",
                        execution_time_ms=execution_time,
                        success=True,
                    )

                return lot_results

        except Exception as e:
            self.stats["failed_requests"] += 1
            logger.error(f"New GraphQL v3 client search failed: {e}")
            raise e

    def get_search_statistics(self) -> dict[str, Any]:
        """
        Получение статистики поиска

        Returns:
            Словарь со статистикой
        """
        total_requests = sum(self.stats.values())

        return {
            **self.stats,
            "total_requests": total_requests,
            "success_rate": (total_requests - self.stats["failed_requests"])
            / max(total_requests, 1),
            "v2_available": self._v2_available,
            "v3_available": self.rest_v3_client is not None,
            "new_graphql_v3_available": NEW_CLIENT_AVAILABLE
            and bool(self.graphql_v3_token),
            "n8n_available": bool(self.n8n_webhook_url),
        }


# Функция для создания готовой к использованию строки поиска
async def search_lots_for_telegram(
    query: str,
    v2_token: str | None = None,
    v3_token: str | None = None,
    limit: int = 10,
) -> str:
    """
    Быстрая функция поиска для Telegram бота

    Args:
        query: Поисковый запрос
        v2_token: Токен GraphQL v2
        v3_token: Токен REST v3
        limit: Максимальное количество результатов

    Returns:
        Форматированный текст для отправки пользователю
    """
    service = GoszakupSearchService(v2_token, v3_token)

    try:
        results = await service.search_lots(query, limit=limit)
        return await service.format_results_for_telegram(results)
    except Exception as e:
        logger.error(f"Telegram search failed: {e}")
        return f"❌ Произошла ошибка поиска: {str(e)}"


# Функция для тестирования
async def test_search_service():
    """Тестовая функция для поискового сервиса"""

    print("🔍 Testing Goszakup Search Service")
    print("=" * 50)

    # Создаем сервис без токенов (только REST v3)
    service = GoszakupSearchService()

    try:
        # Простой поиск
        print("\n📋 Simple search for 'лак':")
        results = await service.search_by_keyword("лак", limit=3)
        print(f"Found {len(results)} lots")

        for result in results[:1]:
            print(f"  - {result.lot_name}")
            print(f"    Customer: {result.customer_name}")
            print(f"    Amount: {result.amount:,.0f} {result.currency}")
            print(f"    Status: {result.status}")
            print(f"    Source: {result.source}")

        # Форматирование для Telegram
        print("\n📱 Telegram formatting:")
        formatted = await service.format_results_for_telegram(results[:1])
        print(formatted[:300] + "..." if len(formatted) > 300 else formatted)

        # Статистика
        print("\n📊 Service statistics:")
        stats = service.get_search_statistics()
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    except Exception as e:
        print(f"❌ Test error: {e}")


if __name__ == "__main__":
    import json

    asyncio.run(test_search_service())
