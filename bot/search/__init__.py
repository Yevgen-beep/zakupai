"""
Пакет для работы с поиском лотов в системе Госзакупок
Поддерживает GraphQL v2 и REST/GraphQL v3 API
"""

from .graphql_v2_client import GraphQLV2Client, LotResult
from .mappings import (
    GoszakupMappings,
    LotStatus,
    TradeMethod,
    get_lot_status_name,
    get_region_name,
    get_trade_method_name,
    mappings,
)
from .rest_v3_client import RestV3Client
from .search_service import (
    GoszakupSearchService,
    SearchComplexity,
    SearchQuery,
    SearchStrategy,
    search_lots_for_telegram,
)

__version__ = "2.0.0"

__all__ = [
    # Основные классы
    "GoszakupSearchService",
    "GraphQLV2Client",
    "RestV3Client",
    "GoszakupMappings",
    # Структуры данных
    "LotResult",
    "SearchQuery",
    "TradeMethod",
    "LotStatus",
    # Перечисления
    "SearchStrategy",
    "SearchComplexity",
    # Функции
    "search_lots_for_telegram",
    "get_trade_method_name",
    "get_lot_status_name",
    "get_region_name",
    # Глобальные экземпляры
    "mappings",
]
