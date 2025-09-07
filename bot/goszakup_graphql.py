"""
Модуль для работы с GraphQL API Госзакупок
Поддерживает поиск лотов с возможностью fallback на REST v3
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientTimeout

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Результат поиска лота"""

    lot_number: str
    name_ru: str
    description_ru: str
    count: float
    amount: float
    customer_name: str
    customer_bin: str
    status: str
    trade_method: str
    announcement_number: str
    announcement_name: str


class GoszakupGraphQLClient:
    """Клиент для работы с GraphQL API Госзакупок"""

    def __init__(self, token: str, timeout: int = 30):
        """
        Инициализация клиента

        Args:
            token: Bearer токен для авторизации
            timeout: Таймаут запросов в секундах
        """
        self.token = token
        self.graphql_url = "https://ows.goszakup.gov.kz/v2/graphql"
        self.rest_url = "https://ows.goszakup.gov.kz/v3/lots"
        self.timeout = ClientTimeout(total=timeout)

        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "ZakupAI-Bot/1.0",
        }

    async def search_lots_graphql(
        self, keyword: str, limit: int = 10, filters: dict[str, Any] | None = None
    ) -> list[SearchResult]:
        """
        Поиск лотов через GraphQL API

        Args:
            keyword: Ключевое слово для поиска
            limit: Максимальное количество результатов
            filters: Дополнительные фильтры

        Returns:
            Список найденных лотов
        """
        # GraphQL запрос основан на реальной схеме
        query = """
        query SearchLots($filter: LotsFiltersInput, $limit: Int) {
          Lots(filter: $filter, limit: $limit) {
            id
            lotNumber
            nameRu
            nameKz
            descriptionRu
            descriptionKz
            amount
            count
            customerNameRu
            customerBin
            trdBuyNumberAnno
            refLotStatusId
            refTradeMethodsId
            TrdBuy {
              id
              nameRu
              numberAnno
              orgNameRu
              orgBin
              RefTradeMethods {
                nameRu
              }
            }
            RefLotsStatus {
              nameRu
            }
          }
        }
        """

        # Подготовка фильтров для поиска по ключевым словам
        search_filter = filters or {}

        # Основной поиск по названию и описанию
        if keyword:
            search_filter.update(
                {
                    "nameRu": keyword,
                    "nameDescriptionRu": keyword,  # Это поле из схемы для поиска в описании
                }
            )

        variables = {"filter": search_filter, "limit": limit}

        payload = {"query": query, "variables": variables}

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    self.graphql_url, json=payload, headers=self.headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        if "errors" in data:
                            logger.error(f"GraphQL errors: {data['errors']}")
                            raise Exception(f"GraphQL query failed: {data['errors']}")

                        lots = data.get("data", {}).get("Lots", [])
                        return self._parse_graphql_results(lots)

                    elif response.status == 401:
                        logger.error("GraphQL API: Unauthorized - token may be invalid")
                        raise Exception("GraphQL API authorization failed")

                    elif response.status == 403:
                        logger.error("GraphQL API: Forbidden - token may be blocked")
                        raise Exception("GraphQL API access forbidden")

                    else:
                        logger.error(f"GraphQL API returned status {response.status}")
                        raise Exception(
                            f"GraphQL API request failed with status {response.status}"
                        )

        except ClientError as e:
            logger.error(f"GraphQL client error: {e}")
            raise Exception(f"GraphQL request failed: {e}") from e

        except TimeoutError as e:
            logger.error("GraphQL request timeout")
            raise Exception("GraphQL request timeout") from e

    async def search_lots_rest_fallback(
        self, keyword: str, limit: int = 10
    ) -> list[SearchResult]:
        """
        Fallback поиск через REST v3 API

        Args:
            keyword: Ключевое слово для поиска
            limit: Максимальное количество результатов

        Returns:
            Список найденных лотов
        """
        params = {"limit": limit, "nameRu": keyword, "descriptionRu": keyword}

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    self.rest_url, params=params, headers=self.headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        lots = data.get("lots", [])
                        return self._parse_rest_results(lots)
                    else:
                        logger.error(f"REST API returned status {response.status}")
                        raise Exception(
                            f"REST API request failed with status {response.status}"
                        )

        except ClientError as e:
            logger.error(f"REST client error: {e}")
            raise Exception(f"REST request failed: {e}") from e

        except TimeoutError as e:
            logger.error("REST request timeout")
            raise Exception("REST request timeout") from e

    async def search_lots(
        self,
        keyword: str,
        limit: int = 10,
        use_graphql: bool = True,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """
        Универсальный поиск лотов с fallback

        Args:
            keyword: Ключевое слово для поиска
            limit: Максимальное количество результатов
            use_graphql: Использовать GraphQL API (fallback на REST при ошибке)
            filters: Дополнительные фильтры (только для GraphQL)

        Returns:
            Список найденных лотов
        """
        if not keyword or not keyword.strip():
            raise ValueError("Keyword cannot be empty")

        keyword = keyword.strip()
        logger.info(f"Searching lots for keyword: '{keyword}' (limit: {limit})")

        if use_graphql:
            try:
                results = await self.search_lots_graphql(keyword, limit, filters)
                logger.info(f"GraphQL search returned {len(results)} results")
                return results
            except Exception as e:
                logger.warning(f"GraphQL search failed: {e}")
                logger.info("Falling back to REST API")

                try:
                    results = await self.search_lots_rest_fallback(keyword, limit)
                    logger.info(f"REST fallback returned {len(results)} results")
                    return results
                except Exception as fallback_error:
                    logger.error(f"REST fallback also failed: {fallback_error}")
                    raise Exception(
                        f"Both GraphQL and REST APIs failed. GraphQL: {e}, REST: {fallback_error}"
                    ) from fallback_error
        else:
            return await self.search_lots_rest_fallback(keyword, limit)

    def _parse_graphql_results(self, lots: list[dict[str, Any]]) -> list[SearchResult]:
        """Парсинг результатов GraphQL"""
        results = []

        for lot in lots:
            try:
                # Извлекаем данные с безопасными значениями по умолчанию
                trd_buy = lot.get("TrdBuy", {})
                ref_lots_status = lot.get("RefLotsStatus", {})

                # Название способа закупки
                trade_method = "Не указан"
                if trd_buy and trd_buy.get("RefTradeMethods"):
                    trade_method = trd_buy["RefTradeMethods"].get("nameRu", "Не указан")

                result = SearchResult(
                    lot_number=lot.get("lotNumber", ""),
                    name_ru=lot.get("nameRu", ""),
                    description_ru=lot.get("descriptionRu", ""),
                    count=float(lot.get("count", 0)),
                    amount=float(lot.get("amount", 0)),
                    customer_name=lot.get("customerNameRu", "")
                    or trd_buy.get("orgNameRu", ""),
                    customer_bin=lot.get("customerBin", "")
                    or trd_buy.get("orgBin", ""),
                    status=ref_lots_status.get("nameRu", "Не указан"),
                    trade_method=trade_method,
                    announcement_number=lot.get("trdBuyNumberAnno", "")
                    or trd_buy.get("numberAnno", ""),
                    announcement_name=trd_buy.get("nameRu", ""),
                )

                results.append(result)

            except Exception as e:
                logger.error(f"Error parsing GraphQL lot result: {e}")
                continue

        return results

    def _parse_rest_results(self, lots: list[dict[str, Any]]) -> list[SearchResult]:
        """Парсинг результатов REST API"""
        results = []

        for lot in lots:
            try:
                result = SearchResult(
                    lot_number=lot.get("lot_number", ""),
                    name_ru=lot.get("name_ru", ""),
                    description_ru=lot.get("description_ru", ""),
                    count=float(lot.get("count", 0)),
                    amount=float(lot.get("amount", 0)),
                    customer_name=lot.get("customer_name_ru", ""),
                    customer_bin=lot.get("customer_bin", ""),
                    status=lot.get("ref_lots_status", {}).get("name_ru", "Не указан"),
                    trade_method=lot.get("ref_trade_methods", {}).get(
                        "name_ru", "Не указан"
                    ),
                    announcement_number=lot.get("trd_buy_number_anno", ""),
                    announcement_name=lot.get("trd_buy_name_ru", ""),
                )

                results.append(result)

            except Exception as e:
                logger.error(f"Error parsing REST lot result: {e}")
                continue

        return results


def format_search_results(results: list[SearchResult]) -> str:
    """
    Форматирование результатов поиска для пользователя

    Args:
        results: Список результатов поиска

    Returns:
        Форматированная строка с результатами
    """
    if not results:
        return "🔍 Ничего не найдено по вашему запросу."

    formatted = f"📋 Найдено лотов: {len(results)}\n\n"

    for i, result in enumerate(results, 1):
        formatted += f"🔹 **Лот {i}**\n"
        formatted += f"📝 № лота: {result.lot_number}\n"

        if result.announcement_number:
            formatted += f"📋 Объявление: {result.announcement_number}\n"

        if result.announcement_name:
            formatted += f"📄 Название: {result.announcement_name}\n"

        formatted += f"📦 Наименование: {result.name_ru}\n"

        if result.description_ru:
            # Обрезаем описание для читаемости
            description = (
                result.description_ru[:200] + "..."
                if len(result.description_ru) > 200
                else result.description_ru
            )
            formatted += f"📋 Описание: {description}\n"

        if result.count > 0:
            formatted += f"🔢 Количество: {result.count}\n"

        if result.amount > 0:
            formatted += f"💰 Сумма: {result.amount:,.0f} тг\n"

        formatted += f"🏢 Заказчик: {result.customer_name}\n"

        if result.customer_bin:
            formatted += f"🏛️ БИН: {result.customer_bin}\n"

        formatted += f"🛒 Способ закупки: {result.trade_method}\n"
        formatted += f"📌 Статус: {result.status}\n"
        formatted += "\n" + "─" * 50 + "\n\n"

    return formatted


# Функция для тестирования
async def test_search():
    """Тестовая функция для проверки работы API"""
    # Это нужно заменить на реальный токен
    token = "your_token_here"

    client = GoszakupGraphQLClient(token)

    try:
        # Тест поиска по слову "лак"
        results = await client.search_lots("лак", limit=5)

        print(f"Найдено {len(results)} результатов:")
        print(format_search_results(results))

    except Exception as e:
        print(f"Ошибка тестирования: {e}")


if __name__ == "__main__":
    asyncio.run(test_search())
