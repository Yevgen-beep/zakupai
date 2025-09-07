"""
Гибридная поисковая система, объединяющая GraphQL v2 и REST v3 API
С морфологическим анализом и фильтрацией релевантности
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .graphql_v2_client import GraphQLV2Client, LotResult
from .morphology import MorphAnalysisResult, get_morphology_analyzer
from .rest_v3_client import RestV3Client

logger = logging.getLogger(__name__)


class SearchStrategy(Enum):
    """Стратегии поиска"""

    GRAPHQL_V2_ONLY = "graphql_v2"
    REST_V3_ONLY = "rest_v3"
    HYBRID = "hybrid"
    AUTO = "auto"


@dataclass
class SearchMetrics:
    """Метрики поиска"""

    strategy_used: str
    total_time: float
    graphql_v2_time: float | None = None
    rest_v3_time: float | None = None
    n8n_time: float | None = None

    graphql_v2_results: int = 0
    rest_v3_results: int = 0
    n8n_results: int = 0

    morphology_variants: int = 0
    queries_attempted: int = 0

    duplicates_removed: int = 0
    relevance_filtered: int = 0
    final_results: int = 0

    errors: list[str] = field(default_factory=list)


@dataclass
class SearchResult:
    """Результат поиска с метриками"""

    lots: list[LotResult]
    metrics: SearchMetrics
    morphology_analysis: MorphAnalysisResult | None = None


class HybridSearchService:
    """Гибридная поисковая система"""

    def __init__(
        self,
        graphql_v2_token: str | None = None,
        rest_v3_token: str | None = None,
        n8n_webhook_url: str | None = None,
        default_strategy: SearchStrategy = SearchStrategy.AUTO,
    ):
        """
        Инициализация гибридного поиска

        Args:
            graphql_v2_token: Токен для GraphQL v2 API
            rest_v3_token: Токен для REST v3 API
            n8n_webhook_url: URL для n8n webhook
            default_strategy: Стратегия поиска по умолчанию
        """
        # Инициализация клиентов
        self.graphql_client = (
            GraphQLV2Client(graphql_v2_token) if graphql_v2_token else None
        )
        self.rest_client = RestV3Client(rest_v3_token) if rest_v3_token else None
        self.n8n_webhook_url = n8n_webhook_url

        # Морфологический анализатор
        self.morphology = get_morphology_analyzer()

        # Настройки
        self.default_strategy = default_strategy
        self.max_results_per_api = 50
        self.search_timeout = 30

        logger.info(
            f"Hybrid search initialized: GraphQL v2={bool(graphql_v2_token)}, "
            f"REST v3={bool(rest_v3_token)}, n8n={bool(n8n_webhook_url)}, "
            f"morphology={self.morphology.is_enabled()}"
        )

    async def search_lots(
        self,
        query: str,
        limit: int = 10,
        strategy: SearchStrategy | None = None,
        user_id: int | None = None,
        use_morphology: bool = True,
        use_relevance_filter: bool = True,
    ) -> SearchResult:
        """
        Основной метод поиска лотов

        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов
            strategy: Стратегия поиска (если None, используется default_strategy)
            user_id: ID пользователя для метрик
            use_morphology: Использовать морфологический анализ
            use_relevance_filter: Использовать фильтр релевантности

        Returns:
            Результат поиска с метриками
        """
        start_time = time.time()

        # Определяем стратегию
        search_strategy = strategy or self.default_strategy
        if search_strategy == SearchStrategy.AUTO:
            search_strategy = self._determine_auto_strategy()

        logger.info(
            f"Starting search: query='{query}', strategy={search_strategy.value}, "
            f"morphology={use_morphology}, user_id={user_id}"
        )

        # Инициализируем метрики
        metrics = SearchMetrics(strategy_used=search_strategy.value, total_time=0.0)

        # Морфологический анализ
        morphology_analysis = None
        search_queries = [query.strip()]

        if use_morphology and self.morphology.is_enabled():
            try:
                morphology_analysis = self.morphology.expand_query(query)
                search_queries = morphology_analysis.expanded_queries
                metrics.morphology_variants = morphology_analysis.variants_count
                metrics.queries_attempted = len(search_queries)

                logger.info(
                    f"Morphology analysis: {morphology_analysis.word_count} words → "
                    f"{morphology_analysis.variants_count} variants → "
                    f"{len(search_queries)} queries"
                )
            except Exception as e:
                logger.error(f"Morphology analysis failed: {e}")
                metrics.errors.append(f"Morphology error: {e}")

        # Выполняем поиск по выбранной стратегии
        all_results = []

        if search_strategy == SearchStrategy.GRAPHQL_V2_ONLY:
            all_results = await self._search_graphql_v2_only(search_queries, metrics)

        elif search_strategy == SearchStrategy.REST_V3_ONLY:
            all_results = await self._search_rest_v3_only(search_queries, metrics)

        elif search_strategy == SearchStrategy.HYBRID:
            all_results = await self._search_hybrid(search_queries, metrics)

        # Убираем дубликаты
        unique_results = self._remove_duplicates(all_results)
        metrics.duplicates_removed = len(all_results) - len(unique_results)

        # Фильтруем по релевантности
        if use_relevance_filter and morphology_analysis:
            relevant_results = self._filter_by_relevance(
                unique_results, query, morphology_analysis
            )
            metrics.relevance_filtered = len(unique_results) - len(relevant_results)
            unique_results = relevant_results

        # Ограничиваем количество результатов
        final_results = unique_results[:limit]
        metrics.final_results = len(final_results)

        # Финализируем метрики
        metrics.total_time = time.time() - start_time

        logger.info(
            f"Search completed: {len(final_results)} results in {metrics.total_time:.2f}s, "
            f"duplicates removed: {metrics.duplicates_removed}, "
            f"relevance filtered: {metrics.relevance_filtered}"
        )

        return SearchResult(
            lots=final_results, metrics=metrics, morphology_analysis=morphology_analysis
        )

    async def _search_graphql_v2_only(
        self, queries: list[str], metrics: SearchMetrics
    ) -> list[LotResult]:
        """Поиск только через GraphQL v2"""
        if not self.graphql_client:
            metrics.errors.append("GraphQL v2 client not available")
            return []

        all_results = []
        start_time = time.time()

        try:
            for query in queries:
                try:
                    # Используем nameDescriptionRu для поиска по названию и описанию
                    filters = {"nameDescriptionRu": query}
                    results = await self.graphql_client.search_lots(
                        filters, limit=min(self.max_results_per_api, 20)
                    )
                    all_results.extend(results)

                    if len(all_results) >= self.max_results_per_api:
                        break

                except Exception as e:
                    logger.error(f"GraphQL v2 query '{query}' failed: {e}")
                    metrics.errors.append(f"GraphQL v2 error: {e}")

            metrics.graphql_v2_results = len(all_results)

        except Exception as e:
            logger.error(f"GraphQL v2 search failed: {e}")
            metrics.errors.append(f"GraphQL v2 failed: {e}")

        metrics.graphql_v2_time = time.time() - start_time
        return all_results

    async def _search_rest_v3_only(
        self, queries: list[str], metrics: SearchMetrics
    ) -> list[LotResult]:
        """Поиск только через REST v3"""
        if not self.rest_client:
            metrics.errors.append("REST v3 client not available")
            return []

        all_results = []
        start_time = time.time()

        try:
            for query in queries:
                try:
                    results = await self.rest_client.search_by_keyword(
                        query, limit=min(self.max_results_per_api, 20)
                    )
                    all_results.extend(results)

                    if len(all_results) >= self.max_results_per_api:
                        break

                except Exception as e:
                    logger.error(f"REST v3 query '{query}' failed: {e}")
                    metrics.errors.append(f"REST v3 error: {e}")

            metrics.rest_v3_results = len(all_results)

        except Exception as e:
            logger.error(f"REST v3 search failed: {e}")
            metrics.errors.append(f"REST v3 failed: {e}")

        metrics.rest_v3_time = time.time() - start_time
        return all_results

    async def _search_hybrid(
        self, queries: list[str], metrics: SearchMetrics
    ) -> list[LotResult]:
        """Гибридный поиск через оба API"""
        tasks = []

        # Создаём задачи для параллельного выполнения
        if self.graphql_client:
            task_graphql = self._search_graphql_v2_only(
                queries, SearchMetrics("graphql_v2", 0.0)
            )
            tasks.append(("graphql", task_graphql))

        if self.rest_client:
            task_rest = self._search_rest_v3_only(
                queries, SearchMetrics("rest_v3", 0.0)
            )
            tasks.append(("rest", task_rest))

        if not tasks:
            metrics.errors.append("No API clients available for hybrid search")
            return []

        # Выполняем поиск параллельно
        all_results = []

        try:
            # Ждём завершения всех задач с таймаутом
            completed_tasks = await asyncio.wait_for(
                asyncio.gather(*[task for _, task in tasks], return_exceptions=True),
                timeout=self.search_timeout,
            )

            # Обрабатываем результаты
            for i, (api_name, _task) in enumerate(tasks):
                result = completed_tasks[i]

                if isinstance(result, Exception):
                    logger.error(f"Hybrid {api_name} search failed: {result}")
                    metrics.errors.append(f"{api_name} error: {result}")
                else:
                    all_results.extend(result)

                    if api_name == "graphql":
                        metrics.graphql_v2_results = len(result)
                    elif api_name == "rest":
                        metrics.rest_v3_results = len(result)

        except TimeoutError:
            logger.error("Hybrid search timeout")
            metrics.errors.append("Search timeout")
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            metrics.errors.append(f"Hybrid search error: {e}")

        return all_results

    def _determine_auto_strategy(self) -> SearchStrategy:
        """Определение автоматической стратегии поиска"""
        if self.graphql_client and self.rest_client:
            return SearchStrategy.HYBRID
        elif self.graphql_client:
            return SearchStrategy.GRAPHQL_V2_ONLY
        elif self.rest_client:
            return SearchStrategy.REST_V3_ONLY
        else:
            logger.warning("No API clients available")
            return SearchStrategy.REST_V3_ONLY  # Fallback

    def _remove_duplicates(self, results: list[LotResult]) -> list[LotResult]:
        """Удаление дубликатов по номеру лота"""
        seen_lots = set()
        unique_results = []

        for result in results:
            # Используем lot_number или announcement_number как уникальный ключ
            lot_key = result.lot_number or result.announcement_number

            if lot_key and lot_key not in seen_lots:
                seen_lots.add(lot_key)
                unique_results.append(result)

        return unique_results

    def _filter_by_relevance(
        self,
        results: list[LotResult],
        original_query: str,
        morphology_analysis: MorphAnalysisResult,
    ) -> list[LotResult]:
        """Фильтрация результатов по релевантности"""
        relevant_results = []

        for result in results:
            # Объединяем название и описание для проверки релевантности
            text_to_check = f"{result.lot_name} {result.lot_description}".lower()

            # Проверяем релевантность через морфологический анализатор
            if self.morphology.is_relevant_result(text_to_check, original_query):
                relevant_results.append(result)
            else:
                logger.debug(
                    f"Filtered out irrelevant result: {result.lot_name[:50]}..."
                )

        return relevant_results

    async def search_complex(
        self,
        keyword: str | None = None,
        customer_bin: str | None = None,
        customer_name: str | None = None,
        trade_methods: list[str] | None = None,
        statuses: list[str] | None = None,
        min_amount: float | None = None,
        max_amount: float | None = None,
        limit: int = 10,
        user_id: int | None = None,
    ) -> SearchResult:
        """
        Комплексный поиск с фильтрами

        Args:
            keyword: Ключевое слово
            customer_bin: БИН заказчика
            customer_name: Название заказчика
            trade_methods: Способы закупки
            statuses: Статусы лотов
            min_amount: Минимальная сумма
            max_amount: Максимальная сумма
            limit: Максимальное количество результатов
            user_id: ID пользователя для метрик

        Returns:
            Результат поиска
        """
        # Если есть только ключевое слово, используем обычный поиск
        if keyword and not any(
            [
                customer_bin,
                customer_name,
                trade_methods,
                statuses,
                min_amount,
                max_amount,
            ]
        ):
            return await self.search_lots(keyword, limit, user_id=user_id)

        # Используем сложные фильтры для GraphQL v2
        start_time = time.time()
        metrics = SearchMetrics(strategy_used="complex_filters", total_time=0.0)

        all_results = []

        # Пробуем GraphQL v2 для сложных фильтров
        if self.graphql_client:
            try:
                gql_start = time.time()

                results = await self.graphql_client.search_by_complex_filters(
                    keyword=keyword,
                    customer_bin=customer_bin,
                    customer_name=customer_name,
                    min_amount=min_amount,
                    max_amount=max_amount,
                    limit=limit,
                )

                all_results.extend(results)
                metrics.graphql_v2_results = len(results)
                metrics.graphql_v2_time = time.time() - gql_start

            except Exception as e:
                logger.error(f"Complex GraphQL search failed: {e}")
                metrics.errors.append(f"GraphQL complex search error: {e}")

        # Fallback на REST v3 если нужно
        if not all_results and self.rest_client and keyword:
            try:
                rest_start = time.time()

                results = await self.rest_client.search_by_keyword(keyword, limit)
                all_results.extend(results)
                metrics.rest_v3_results = len(results)
                metrics.rest_v3_time = time.time() - rest_start

            except Exception as e:
                logger.error(f"Complex REST search failed: {e}")
                metrics.errors.append(f"REST complex search error: {e}")

        # Ограничиваем результаты
        final_results = all_results[:limit]
        metrics.final_results = len(final_results)
        metrics.total_time = time.time() - start_time

        return SearchResult(lots=final_results, metrics=metrics)

    async def get_lot_by_number(self, lot_number: str) -> LotResult | None:
        """Получение лота по номеру"""
        # Пробуем сначала GraphQL v2
        if self.graphql_client:
            try:
                result = await self.graphql_client.get_lot_by_number(lot_number)
                if result:
                    return result
            except Exception as e:
                logger.error(f"GraphQL v2 get_lot_by_number failed: {e}")

        # Fallback на REST v3
        if self.rest_client:
            try:
                return await self.rest_client.get_lot_by_number(lot_number)
            except Exception as e:
                logger.error(f"REST v3 get_lot_by_number failed: {e}")

        return None

    def get_search_statistics(self) -> dict[str, Any]:
        """Получение статистики поисковой системы"""
        return {
            "graphql_v2_available": bool(self.graphql_client),
            "rest_v3_available": bool(self.rest_client),
            "n8n_webhook_available": bool(self.n8n_webhook_url),
            "morphology_enabled": self.morphology.is_enabled(),
            "morphology_stats": self.morphology.get_statistics(),
            "default_strategy": self.default_strategy.value,
            "max_results_per_api": self.max_results_per_api,
            "search_timeout": self.search_timeout,
        }
