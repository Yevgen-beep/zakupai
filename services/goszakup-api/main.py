"""
Универсальный API Gateway для работы с Goszakup API
Объединяет GraphQL v2, REST v3 с динамическим роутингом
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import aiohttp
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field
from starlette.responses import Response

from zakupai_common.fastapi.metrics import add_prometheus_middleware
from zakupai_common.metrics import record_goszakup_error

logger = logging.getLogger(__name__)

SERVICE_NAME = "goszakup"


# Модели данных
class SearchRequest(BaseModel):
    keyword: str = Field(..., description="Ключевое слово для поиска")
    limit: int = Field(default=10, ge=1, le=100)
    api_version: str = Field(default="auto", pattern="^(auto|graphql_v2|rest_v3)$")
    filters: dict[str, Any] | None = None


class LotResult(BaseModel):
    lot_number: str
    announcement_number: str
    name_ru: str
    description_ru: str
    amount: float
    count: float
    customer_name: str
    customer_bin: str
    status: str
    trade_method: str
    source: str


class SearchResponse(BaseModel):
    results: list[LotResult]
    total_found: int
    api_used: str
    query_time_ms: int


# Универсальный клиент Goszakup
class UniversalGoszakupClient:
    """Универсальный клиент с автоматическим выбором API"""

    def __init__(self, token: str):
        self.token = token
        self.graphql_url = "https://ows.goszakup.gov.kz/v2/graphql"
        self.rest_v3_url = "https://ows.goszakup.gov.kz/v3/lots"

        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "ZakupAI/1.0",
        }

    async def search_lots(self, request: SearchRequest) -> SearchResponse:
        """Универсальный поиск с автоматическим выбором API"""
        start_time = asyncio.get_event_loop().time()

        # Выбор API
        api_to_use = self._select_api(request)

        try:
            if api_to_use == "graphql_v2":
                results = await self._search_graphql(request)
            else:  # rest_v3
                results = await self._search_rest(request)

            query_time = int((asyncio.get_event_loop().time() - start_time) * 1000)

            return SearchResponse(
                results=results,
                total_found=len(results),
                api_used=api_to_use,
                query_time_ms=query_time,
            )

        except Exception as e:
            logger.error(f"Search failed with {api_to_use}: {e}")
            record_goszakup_error(SERVICE_NAME, api_to_use, type(e).__name__)
            # Fallback
            if api_to_use == "graphql_v2":
                logger.info("Falling back to REST v3")
                results = await self._search_rest(request)
                query_time = int((asyncio.get_event_loop().time() - start_time) * 1000)
                return SearchResponse(
                    results=results,
                    total_found=len(results),
                    api_used="rest_v3_fallback",
                    query_time_ms=query_time,
                )
            raise HTTPException(
                status_code=500, detail=f"API call failed: {str(e)}"
            ) from e

    def _select_api(self, request: SearchRequest) -> str:
        """Выбор оптимального API"""
        if request.api_version != "auto":
            return request.api_version

        # Логика автовыбора
        if request.filters:
            return "graphql_v2"  # GraphQL лучше для сложных фильтров
        if len(request.keyword) > 50:
            return "rest_v3"  # REST лучше для длинных запросов

        return "graphql_v2"  # По умолчанию GraphQL

    async def _search_graphql(self, request: SearchRequest) -> list[LotResult]:
        """Поиск через GraphQL v2"""
        query = """
        query SearchLots($filter: LotsFiltersInput, $limit: Int) {
          Lots(filter: $filter, limit: $limit) {
            lotNumber
            nameRu
            descriptionRu
            amount
            count
            customerNameRu
            customerBin
            TrdBuy {
              nameRu
              numberAnno
              RefTradeMethods { nameRu }
            }
            RefLotsStatus { nameRu }
          }
        }
        """

        # Формирование фильтров
        filters = {
            "nameRu": request.keyword,
            "nameDescriptionRu": request.keyword,
        }
        if request.filters:
            filters.update(request.filters)

        variables = {"filter": filters, "limit": request.limit}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.graphql_url,
                headers=self.headers,
                json={"query": query, "variables": variables},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    raise Exception(f"GraphQL request failed: {resp.status}")

                data = await resp.json()

                if "errors" in data:
                    raise Exception(f"GraphQL errors: {data['errors']}")

                lots = data.get("data", {}).get("Lots", [])
                return [self._parse_graphql_lot(lot) for lot in lots]

    async def _search_rest(self, request: SearchRequest) -> list[LotResult]:
        """Поиск через REST v3"""
        params = {
            "nameRu": request.keyword,
            "descriptionRu": request.keyword,
            "limit": request.limit,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.rest_v3_url,
                headers=self.headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    raise Exception(f"REST request failed: {resp.status}")

                data = await resp.json()
                lots = data.get("lots", [])
                return [self._parse_rest_lot(lot) for lot in lots]

    def _parse_graphql_lot(self, lot: dict) -> LotResult:
        """Парсинг лота из GraphQL ответа"""
        return LotResult(
            lot_number=lot.get("lotNumber", ""),
            announcement_number=lot.get("TrdBuy", {}).get("numberAnno", ""),
            name_ru=lot.get("nameRu", ""),
            description_ru=lot.get("descriptionRu", ""),
            amount=float(lot.get("amount", 0)),
            count=float(lot.get("count", 0)),
            customer_name=lot.get("customerNameRu", ""),
            customer_bin=lot.get("customerBin", ""),
            status=lot.get("RefLotsStatus", {}).get("nameRu", ""),
            trade_method=lot.get("TrdBuy", {})
            .get("RefTradeMethods", {})
            .get("nameRu", ""),
            source="graphql_v2",
        )

    def _parse_rest_lot(self, lot: dict) -> LotResult:
        """Парсинг лота из REST ответа"""
        return LotResult(
            lot_number=lot.get("lotNumber", ""),
            announcement_number=lot.get("trdBuyNumberAnno", ""),
            name_ru=lot.get("nameRu", ""),
            description_ru=lot.get("descriptionRu", ""),
            amount=float(lot.get("amount", 0)),
            count=float(lot.get("count", 0)),
            customer_name=lot.get("customerNameRu", ""),
            customer_bin=lot.get("customerBin", ""),
            status=lot.get("refLotsStatusNameRu", ""),
            trade_method=lot.get("refTradeMethodsNameRu", ""),
            source="rest_v3",
        )


# Глобальный клиент
client: UniversalGoszakupClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения"""
    global client
    token = os.getenv("GOSZAKUP_TOKEN")
    if not token:
        logger.error("GOSZAKUP_TOKEN not found")
    else:
        client = UniversalGoszakupClient(token)
        logger.info("Goszakup client initialized")
    yield


# FastAPI приложение
app = FastAPI(
    title="ZakupAI Goszakup Gateway",
    description="Универсальный API Gateway для работы с Goszakup API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
add_prometheus_middleware(app, SERVICE_NAME)


# Эндпоинты
@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {"status": "healthy", "service": "goszakup-api"}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/search", response_model=SearchResponse)
async def search_lots(request: SearchRequest):
    """Универсальный поиск лотов"""
    if not client:
        raise HTTPException(status_code=500, detail="Client not initialized")

    return await client.search_lots(request)


@app.get("/search", response_model=SearchResponse)
async def search_lots_get(
    keyword: str = Query(..., description="Ключевое слово"),
    limit: int = Query(10, ge=1, le=100),
    api_version: str = Query("auto", pattern="^(auto|graphql_v2|rest_v3)$"),
):
    """Поиск лотов через GET запрос"""
    request = SearchRequest(keyword=keyword, limit=limit, api_version=api_version)
    return await search_lots(request)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("APP_HOST", "0.0.0.0")  # nosec B104
    port = int(os.getenv("APP_PORT", "8001"))

    uvicorn.run(app, host=host, port=port, log_level="info", access_log=True)
