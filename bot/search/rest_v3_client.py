"""
REST/GraphQL v3 клиент для работы с API goszakup.gov.kz
Поддерживает как REST, так и GraphQL запросы к v3 API
"""

import asyncio
import json
import logging
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientTimeout

from .graphql_v2_client import LotResult

logger = logging.getLogger(__name__)


class RestV3Client:
    """Клиент для работы с REST/GraphQL v3 API Госзакупок"""

    def __init__(self, token: str | None = None, timeout: int = 30):
        """
        Инициализация клиента REST v3

        Args:
            token: Bearer токен для авторизации (опционально)
            timeout: Таймаут запросов в секундах
        """
        self.token = token
        self.rest_base_url = "https://ows.goszakup.gov.kz/v3"
        self.graphql_url = "https://ows.goszakup.gov.kz/v3/graphql"
        self.timeout = ClientTimeout(total=timeout)

        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ZakupAI-Bot/2.0",
        }

        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    async def search_lots_rest(
        self, params: dict[str, Any], limit: int = 10, offset: int = 0
    ) -> list[LotResult]:
        """
        Поиск лотов через REST v3 API

        Args:
            params: Параметры поиска для REST API
            limit: Максимальное количество результатов
            offset: Смещение для пагинации

        Returns:
            Список найденных лотов
        """
        # Подготовка параметров
        query_params = {
            **params,
            "limit": min(limit, 100),  # Ограничиваем максимум
            "offset": offset,
        }

        url = f"{self.rest_base_url}/lots"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    url, params=query_params, headers=self.headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        # V3 REST API может возвращать данные в разных форматах
                        lots = (
                            data.get("lots", [])
                            or data.get("items", [])
                            or data.get("data", [])
                        )

                        return self._parse_rest_results(lots)

                    elif response.status == 401:
                        logger.error("REST v3: Unauthorized")
                        raise Exception("REST v3 authorization failed")

                    else:
                        logger.error(f"REST v3 API returned status {response.status}")
                        response_text = await response.text()
                        logger.error(f"Response: {response_text[:500]}")
                        raise Exception(
                            f"REST v3 request failed with status {response.status}"
                        )

        except ClientError as e:
            logger.error(f"REST v3 client error: {e}")
            raise Exception(f"REST v3 request failed: {e}") from e

        except TimeoutError as e:
            logger.error("REST v3 request timeout")
            raise Exception("REST v3 request timeout") from e

    async def search_lots_graphql_v3(
        self, filters: dict[str, Any], limit: int = 10, offset: int = 0
    ) -> list[LotResult]:
        """
        Поиск лотов через GraphQL v3 API

        Args:
            filters: Фильтры для GraphQL v3
            limit: Максимальное количество результатов
            offset: Смещение для пагинации

        Returns:
            Список найденных лотов
        """
        query = self._build_graphql_v3_query()

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
                            logger.error(f"GraphQL v3 errors: {data['errors']}")
                            raise Exception(
                                f"GraphQL v3 query failed: {data['errors']}"
                            )

                        lots = data.get("data", {}).get("lots", [])
                        return self._parse_graphql_v3_results(lots)

                    else:
                        logger.error(
                            f"GraphQL v3 API returned status {response.status}"
                        )
                        raise Exception(
                            f"GraphQL v3 request failed with status {response.status}"
                        )

        except ClientError as e:
            logger.error(f"GraphQL v3 client error: {e}")
            raise Exception(f"GraphQL v3 request failed: {e}") from e

        except TimeoutError as e:
            logger.error("GraphQL v3 request timeout")
            raise Exception("GraphQL v3 request timeout") from e

    async def search_by_keyword(
        self, keyword: str, limit: int = 10, use_graphql: bool = False
    ) -> list[LotResult]:
        """
        Простой поиск по ключевому слову

        Args:
            keyword: Ключевое слово для поиска
            limit: Максимальное количество результатов
            use_graphql: Использовать GraphQL v3 вместо REST

        Returns:
            Список найденных лотов
        """
        if use_graphql:
            filters = {"nameRu": keyword, "descriptionRu": keyword}
            return await self.search_lots_graphql_v3(filters, limit)
        else:
            params = {
                "nameRu": keyword,
                "descriptionRu": keyword,
                "nameDescriptionRu": keyword,  # Комбинированный поиск
            }
            return await self.search_lots_rest(params, limit)

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
        publish_date_from: str | None = None,
        publish_date_to: str | None = None,
        end_date_from: str | None = None,
        end_date_to: str | None = None,
        limit: int = 10,
        use_graphql: bool = True,
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
            publish_date_from: Дата публикации от (YYYY-MM-DD)
            publish_date_to: Дата публикации до (YYYY-MM-DD)
            end_date_from: Дата окончания от (YYYY-MM-DD)
            end_date_to: Дата окончания до (YYYY-MM-DD)
            limit: Максимальное количество результатов
            use_graphql: Использовать GraphQL v3 вместо REST

        Returns:
            Список найденных лотов
        """
        if use_graphql:
            filters = {}

            if keyword:
                filters.update({"nameRu": keyword, "descriptionRu": keyword})

            if customer_bin:
                filters["customerBin"] = customer_bin

            if customer_name:
                filters["customerNameRu"] = customer_name

            if announcement_number:
                filters["trdBuyNumberAnno"] = announcement_number

            if trade_method_ids:
                filters["refTradeMethodsId"] = trade_method_ids

            if status_ids:
                filters["refLotStatusId"] = status_ids

            if min_amount is not None:
                filters["amountFrom"] = min_amount

            if max_amount is not None:
                filters["amountTo"] = max_amount

            if publish_date_from:
                filters["publishDateFrom"] = publish_date_from

            if publish_date_to:
                filters["publishDateTo"] = publish_date_to

            if end_date_from:
                filters["endDateFrom"] = end_date_from

            if end_date_to:
                filters["endDateTo"] = end_date_to

            return await self.search_lots_graphql_v3(filters, limit)

        else:
            params = {}

            if keyword:
                params.update(
                    {
                        "nameRu": keyword,
                        "descriptionRu": keyword,
                        "nameDescriptionRu": keyword,
                    }
                )

            if customer_bin:
                params["customerBin"] = customer_bin

            if customer_name:
                params["customerNameRu"] = customer_name

            if announcement_number:
                params["trdBuyNumberAnno"] = announcement_number

            if trade_method_ids:
                params["refTradeMethodsId"] = ",".join(map(str, trade_method_ids))

            if status_ids:
                params["refLotStatusId"] = ",".join(map(str, status_ids))

            if min_amount is not None:
                params["amountFrom"] = min_amount

            if max_amount is not None:
                params["amountTo"] = max_amount

            if publish_date_from:
                params["publishDateFrom"] = publish_date_from

            if publish_date_to:
                params["publishDateTo"] = publish_date_to

            if end_date_from:
                params["endDateFrom"] = end_date_from

            if end_date_to:
                params["endDateTo"] = end_date_to

            return await self.search_lots_rest(params, limit)

    async def get_lot_by_id(self, lot_id: str | int) -> LotResult | None:
        """
        Получение конкретного лота по ID

        Args:
            lot_id: ID лота

        Returns:
            Найденный лот или None
        """
        url = f"{self.rest_base_url}/lots/{lot_id}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Обрабатываем одиночный лот
                        if data:
                            results = self._parse_rest_results([data])
                            return results[0] if results else None

                    elif response.status == 404:
                        return None

                    else:
                        logger.error(f"GET lot by ID returned status {response.status}")
                        return None

        except Exception as e:
            logger.error(f"Error getting lot by ID {lot_id}: {e}")
            return None

    def _build_graphql_v3_query(self) -> str:
        """Построение GraphQL v3 запроса"""
        return """
        query SearchLotsV3($filter: LotsFilterInput, $limit: Int, $offset: Int) {
          lots(filter: $filter, limit: $limit, offset: $offset) {
            id
            lot_number
            nameRu
            descriptionRu
            count
            amount
            trd_buy_number_anno
            customer_name_ru
            customer_bin
            ref_trade_methods_id
            ref_lot_status_id
            trd_buy {
              id
              name_ru
              number_anno
              org_name_ru
              org_bin
              publish_date
              end_date
            }
            ref_lot_status {
              id
              name_ru
            }
            ref_trade_methods {
              id
              name_ru
            }
          }
        }
        """

    def _parse_rest_results(self, lots: list[dict[str, Any]]) -> list[LotResult]:
        """Парсинг результатов REST v3 в нормализованный формат"""
        results = []

        for lot in lots:
            try:
                # REST v3 может иметь разную структуру данных
                trd_buy = lot.get("trd_buy", {})
                ref_lot_status = lot.get("ref_lot_status", {})
                ref_trade_methods = lot.get("ref_trade_methods", {})

                # Формируем URL лота
                lot_id = lot.get("id") or lot.get("lot_id")
                announcement_id = trd_buy.get("id") or lot.get("trd_buy_id")

                url = None
                if announcement_id:
                    url = f"https://goszakup.gov.kz/ru/announce/index/{announcement_id}"
                elif lot_id:
                    url = f"https://goszakup.gov.kz/ru/announce/lot/{lot_id}"

                result = LotResult(
                    lot_number=lot.get("lot_number", "") or lot.get("lotNumber", ""),
                    announcement_number=lot.get("trd_buy_number_anno", "")
                    or trd_buy.get("number_anno", ""),
                    announcement_name=trd_buy.get("name_ru", "")
                    or lot.get("trd_buy_name_ru", ""),
                    lot_name=lot.get("nameRu", "") or lot.get("name_ru", ""),
                    lot_description=lot.get("descriptionRu", "")
                    or lot.get("description_ru", ""),
                    quantity=float(lot.get("count", 0)),
                    amount=float(lot.get("amount", 0) or lot.get("estimate_amount", 0)),
                    currency="KZT",
                    trade_method=ref_trade_methods.get("name_ru", "Не указан"),
                    status=ref_lot_status.get("name_ru", "Не указан"),
                    customer_name=lot.get("customer_name_ru", "")
                    or trd_buy.get("org_name_ru", ""),
                    customer_bin=lot.get("customer_bin", "")
                    or trd_buy.get("org_bin", ""),
                    deadline=trd_buy.get("end_date", ""),
                    url=url,
                    source="rest_v3",
                )

                results.append(result)

            except Exception as e:
                logger.error(f"Error parsing REST v3 lot result: {e}")
                continue

        return results

    def _parse_graphql_v3_results(self, lots: list[dict[str, Any]]) -> list[LotResult]:
        """Парсинг результатов GraphQL v3 в нормализованный формат"""
        results = []

        for lot in lots:
            try:
                trd_buy = lot.get("trd_buy", {})
                ref_lot_status = lot.get("ref_lot_status", {})
                ref_trade_methods = lot.get("ref_trade_methods", {})

                # Формируем URL лота
                announcement_id = trd_buy.get("id") or lot.get("trd_buy_id")
                url = (
                    f"https://goszakup.gov.kz/ru/announce/index/{announcement_id}"
                    if announcement_id
                    else None
                )

                result = LotResult(
                    lot_number=lot.get("lot_number", ""),
                    announcement_number=lot.get("trd_buy_number_anno", "")
                    or trd_buy.get("number_anno", ""),
                    announcement_name=trd_buy.get("name_ru", ""),
                    lot_name=lot.get("nameRu", ""),
                    lot_description=lot.get("descriptionRu", ""),
                    quantity=float(lot.get("count", 0)),
                    amount=float(lot.get("amount", 0)),
                    currency="KZT",
                    trade_method=ref_trade_methods.get("name_ru", "Не указан"),
                    status=ref_lot_status.get("name_ru", "Не указан"),
                    customer_name=lot.get("customer_name_ru", "")
                    or trd_buy.get("org_name_ru", ""),
                    customer_bin=lot.get("customer_bin", "")
                    or trd_buy.get("org_bin", ""),
                    deadline=trd_buy.get("end_date", ""),
                    url=url,
                    source="graphql_v3",
                )

                results.append(result)

            except Exception as e:
                logger.error(f"Error parsing GraphQL v3 lot result: {e}")
                continue

        return results

    async def get_available_endpoints(self) -> dict[str, str]:
        """
        Получение доступных endpoints REST v3 API

        Returns:
            Словарь с описанием endpoints
        """
        return {
            "lots": f"{self.rest_base_url}/lots",
            "lots_by_id": f"{self.rest_base_url}/lots/{{id}}",
            "announcements": f"{self.rest_base_url}/trd/buy",
            "trade_methods": f"{self.rest_base_url}/ref/trade-methods",
            "lot_statuses": f"{self.rest_base_url}/ref/lot-statuses",
            "graphql": self.graphql_url,
        }

    def is_token_available(self) -> bool:
        """Проверка наличия токена"""
        return self.token is not None


# Функция для тестирования
async def test_rest_v3_client():
    """Тестовая функция для REST v3 клиента"""
    # Без токена для публичных endpoints
    client = RestV3Client()

    try:
        # Простой поиск через REST
        results = await client.search_by_keyword("лак", limit=3, use_graphql=False)
        print(f"REST search results: {len(results)} lots found")

        for result in results[:1]:
            print(
                f"- {result.lot_name} | {result.customer_name} | {result.amount:,.0f} тг"
            )

        # Показ endpoints
        endpoints = await client.get_available_endpoints()
        print(
            "Available endpoints:", json.dumps(endpoints, ensure_ascii=False, indent=2)
        )

    except Exception as e:
        print(f"Test error: {e}")


if __name__ == "__main__":
    asyncio.run(test_rest_v3_client())
