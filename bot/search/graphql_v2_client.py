"""
GraphQL v2 клиент для работы с API goszakup.gov.kz
Использует реальную схему из graphql_schema.json для построения запросов
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientTimeout

logger = logging.getLogger(__name__)


@dataclass
class LotResult:
    """Нормализованный результат поиска лота"""

    lot_number: str
    announcement_number: str
    announcement_name: str
    lot_name: str
    lot_description: str
    quantity: float
    amount: float
    currency: str
    trade_method: str
    status: str
    customer_name: str
    customer_bin: str
    deadline: str | None = None
    url: str | None = None
    source: str = "graphql_v2"


class GraphQLV2Client:
    """Клиент для работы с GraphQL v2 API Госзакупок"""

    def __init__(self, token: str, timeout: int = 30):
        """
        Инициализация клиента GraphQL v2

        Args:
            token: Bearer токен для авторизации
            timeout: Таймаут запросов в секундах
        """
        self.token = token
        self.graphql_url = "https://ows.goszakup.gov.kz/v2/graphql"
        self.timeout = ClientTimeout(total=timeout)

        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ZakupAI-Bot/2.0",
        }

    async def search_lots(
        self, filters: dict[str, Any], limit: int = 10, offset: int = 0
    ) -> list[LotResult]:
        """
        Поиск лотов через GraphQL v2

        Args:
            filters: Фильтры для поиска (LotsFiltersInput)
            limit: Максимальное количество результатов
            offset: Смещение для пагинации

        Returns:
            Список найденных лотов
        """
        query = self._build_search_query()

        variables = {"filter": filters, "limit": limit, "offset": offset}

        payload = {"query": query, "variables": variables}

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    self.graphql_url, json=payload, headers=self.headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        if "errors" in data:
                            logger.error(f"GraphQL v2 errors: {data['errors']}")
                            raise Exception(f"GraphQL query failed: {data['errors']}")

                        lots = data.get("data", {}).get("lots", [])
                        return self._parse_results(lots)

                    elif response.status == 401:
                        logger.error(
                            "GraphQL v2: Unauthorized - token invalid or expired"
                        )
                        raise Exception("GraphQL v2 authorization failed")

                    elif response.status == 403:
                        logger.error("GraphQL v2: Forbidden - access denied")
                        raise Exception("GraphQL v2 access forbidden")

                    else:
                        logger.error(
                            f"GraphQL v2 API returned status {response.status}"
                        )
                        raise Exception(
                            f"GraphQL v2 request failed with status {response.status}"
                        )

        except ClientError as e:
            logger.error(f"GraphQL v2 client error: {e}")
            raise Exception(f"GraphQL v2 request failed: {e}") from e

        except TimeoutError as e:
            logger.error("GraphQL v2 request timeout")
            raise Exception("GraphQL v2 request timeout") from e

    async def search_by_keyword(self, keyword: str, limit: int = 10) -> list[LotResult]:
        """
        Простой поиск по ключевому слову

        Args:
            keyword: Ключевое слово для поиска
            limit: Максимальное количество результатов

        Returns:
            Список найденных лотов
        """
        filters = {"nameRu": keyword, "nameDescriptionRu": keyword}

        return await self.search_lots(filters, limit)

    async def search_by_complex_filters(
        self,
        keyword: str | None = None,
        customer_bin: str | None = None,
        customer_name: str | None = None,
        trade_method_ids: list[int] | None = None,
        status_ids: list[int] | None = None,
        min_amount: float | None = None,
        max_amount: float | None = None,
        announcement_number: str | None = None,
        limit: int = 10,
    ) -> list[LotResult]:
        """
        Сложный поиск с множественными фильтрами

        Args:
            keyword: Ключевое слово
            customer_bin: БИН заказчика
            customer_name: Наименование заказчика
            trade_method_ids: ID способов закупки
            status_ids: ID статусов лотов
            min_amount: Минимальная сумма
            max_amount: Максимальная сумма
            announcement_number: Номер объявления
            limit: Максимальное количество результатов

        Returns:
            Список найденных лотов
        """
        filters = {}

        # Текстовые фильтры
        if keyword:
            filters.update({"nameRu": keyword, "nameDescriptionRu": keyword})

        if customer_bin:
            filters["customerBin"] = customer_bin

        if customer_name:
            filters["customerNameRu"] = customer_name

        if announcement_number:
            filters["trdBuyNumberAnno"] = announcement_number

        # Списочные фильтры
        if trade_method_ids:
            filters["refTradeMethodsId"] = trade_method_ids

        if status_ids:
            filters["refLotStatusId"] = status_ids

        # Числовые фильтры (для GraphQL v2 нужно проверить поддержку диапазонов)
        if min_amount is not None or max_amount is not None:
            # В GraphQL v2 может быть поддержка range фильтров
            # Пока используем простой фильтр по точному значению
            if min_amount is not None:
                filters["amount"] = [min_amount]

        return await self.search_lots(filters, limit)

    async def get_lot_by_number(self, lot_number: str) -> LotResult | None:
        """
        Получение конкретного лота по номеру

        Args:
            lot_number: Номер лота

        Returns:
            Найденный лот или None
        """
        filters = {"lotNumber": lot_number}

        results = await self.search_lots(filters, limit=1)
        return results[0] if results else None

    def _build_search_query(self) -> str:
        """Построение GraphQL запроса на основе реальной схемы"""
        return """
        query SearchLots($filter: LotsFiltersInput, $limit: Int, $offset: Int) {
          lots(filter: $filter, limit: $limit, offset: $offset) {
            id
            lotNumber
            nameRu
            nameKz
            descriptionRu
            descriptionKz
            amount
            count
            customerNameRu
            customerNameKz
            customerBin
            trdBuyNumberAnno
            trdBuyId
            refLotStatusId
            refTradeMethodsId
            refBuyTradeMethodsId
            lastUpdateDate
            TrdBuy {
              id
              nameRu
              nameKz
              numberAnno
              orgNameRu
              orgNameKz
              orgBin
              publishDate
              endDate
              RefTradeMethods {
                id
                nameRu
                nameKz
              }
            }
            RefLotsStatus {
              id
              nameRu
              nameKz
            }
          }
        }
        """

    def _parse_results(self, lots: list[dict[str, Any]]) -> list[LotResult]:
        """Парсинг результатов GraphQL v2 в нормализованный формат"""
        results = []

        for lot in lots:
            try:
                # Извлекаем данные с безопасными значениями по умолчанию
                trd_buy = lot.get("TrdBuy", {})
                ref_lots_status = lot.get("RefLotsStatus", {})

                # Определяем способ закупки
                trade_method = "Не указан"
                if trd_buy and trd_buy.get("RefTradeMethods"):
                    trade_method = trd_buy["RefTradeMethods"].get("nameRu", "Не указан")

                # Формируем URL лота
                announcement_id = trd_buy.get("id", "") or lot.get("trdBuyId", "")
                url = (
                    f"https://goszakup.gov.kz/ru/announce/index/{announcement_id}"
                    if announcement_id
                    else None
                )

                result = LotResult(
                    lot_number=lot.get("lotNumber", ""),
                    announcement_number=lot.get("trdBuyNumberAnno", "")
                    or trd_buy.get("numberAnno", ""),
                    announcement_name=trd_buy.get("nameRu", ""),
                    lot_name=lot.get("nameRu", ""),
                    lot_description=lot.get("descriptionRu", ""),
                    quantity=float(lot.get("count", 0)),
                    amount=float(lot.get("amount", 0)),
                    currency="KZT",
                    trade_method=trade_method,
                    status=ref_lots_status.get("nameRu", "Не указан"),
                    customer_name=lot.get("customerNameRu", "")
                    or trd_buy.get("orgNameRu", ""),
                    customer_bin=lot.get("customerBin", "")
                    or trd_buy.get("orgBin", ""),
                    deadline=trd_buy.get("endDate", ""),
                    url=url,
                    source="graphql_v2",
                )

                results.append(result)

            except Exception as e:
                logger.error(f"Error parsing GraphQL v2 lot result: {e}")
                continue

        return results

    async def validate_token(self) -> bool:
        """
        Проверка валидности токена

        Returns:
            True если токен валиден, False иначе
        """
        try:
            # Простой запрос для проверки токена
            filters = {"id": [1]}  # Ищем лот с ID 1 (если существует)
            await self.search_lots(filters, limit=1)
            return True
        except Exception as e:
            if "authorization" in str(e).lower() or "forbidden" in str(e).lower():
                return False
            # Другие ошибки могут быть не связаны с токеном
            return True

    async def get_available_filters(self) -> dict[str, Any]:
        """
        Получение доступных фильтров для GraphQL v2
        (на основе схемы LotsFiltersInput)

        Returns:
            Словарь с описанием доступных фильтров
        """
        return {
            "text_filters": {
                "nameRu": "Название на русском",
                "nameKz": "Название на казахском",
                "nameDescriptionRu": "Поиск в названии и описании на русском",
                "nameDescriptionKz": "Поиск в названии и описании на казахском",
                "lotNumber": "Номер лота",
                "customerNameRu": "Название заказчика на русском",
                "customerNameKz": "Название заказчика на казахском",
                "customerBin": "БИН заказчика",
                "trdBuyNumberAnno": "Номер объявления о закупке",
            },
            "list_filters": {
                "id": "Список ID лотов",
                "amount": "Список сумм",
                "trdBuyId": "Список ID объявлений",
                "refLotStatusId": "Список ID статусов лотов",
                "refTradeMethodsId": "Список ID способов закупки",
                "refBuyTradeMethodsId": "Список ID способов закупки (покупка)",
                "pointList": "Список ID точек",
                "enstruList": "Список ID структур",
                "lastUpdateDate": "Список дат последнего обновления",
                "indexDate": "Список дат индексации",
            },
            "numeric_filters": {
                "customerId": "ID заказчика",
                "refTrdBuySigns": "Признаки торгов",
                "unionLots": "Объединенные лоты",
                "plnPointRootrecordId": "ID корневой записи плана",
            },
            "string_filters": {"plnPointKatoList": "Список КАТО кодов"},
        }


# Функция для тестирования
async def test_graphql_v2_client():
    """Тестовая функция для GraphQL v2 клиента"""
    # Заглушка токена - используется безопасное значение для локального тестирования
    token = os.getenv("GOSZAKUP_V2_TEST_TOKEN", "dummy-graphql-token")

    client = GraphQLV2Client(token)

    try:
        # Проверка токена
        is_valid = await client.validate_token()
        print(f"Token validation: {'✅ Valid' if is_valid else '❌ Invalid'}")

        if is_valid:
            # Простой поиск
            results = await client.search_by_keyword("лак", limit=3)
            print(f"Simple search results: {len(results)} lots found")

            # Сложный поиск
            complex_results = await client.search_by_complex_filters(
                keyword="мебель", min_amount=100000, limit=2
            )
            print(f"Complex search results: {len(complex_results)} lots found")

        # Показ доступных фильтров
        filters_info = await client.get_available_filters()
        print(
            "Available filters:", json.dumps(filters_info, ensure_ascii=False, indent=2)
        )

    except Exception as e:
        print(f"Test error: {e}")


if __name__ == "__main__":
    asyncio.run(test_graphql_v2_client())
