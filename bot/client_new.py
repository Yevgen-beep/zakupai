import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
from httpx import Limits, Timeout

logger = logging.getLogger(__name__)


class ZakupaiHTTPClient:
    """
    Async HTTP client for ZakupAI API with retries and timeouts
    """

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

        # Configure timeouts and limits
        self.timeout = Timeout(connect=10.0, read=30.0, write=10.0, pool=60.0)

        self.limits = Limits(max_keepalive_connections=5, max_connections=20)

        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "ZakupAI-TelegramBot/1.0",
        }

    async def request_with_retries(
        self,
        method: str,
        endpoint: str,
        json_data: dict | None = None,
        params: dict | None = None,
        retries: int = 3,
    ) -> dict[Any, Any] | None:
        """
        HTTP request with exponential backoff retries
        """
        url = f"{self.base_url}{endpoint}"

        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout, limits=self.limits, headers=self.headers
                ) as client:
                    response = await client.request(
                        method=method, url=url, json=json_data, params=params
                    )

                    if response.status_code == 429:
                        if attempt < retries:
                            wait_time = 2**attempt
                            logger.warning(f"Rate limited, retrying in {wait_time}s")
                            await asyncio.sleep(wait_time)
                            continue
                        raise Exception("Rate limit exceeded")

                    if response.status_code == 401:
                        raise Exception("Неверный API ключ")

                    if response.status_code == 404:
                        raise Exception("Эндпоинт не найден")

                    if response.status_code >= 500:
                        if attempt < retries:
                            wait_time = 2**attempt
                            logger.warning(
                                f"Server error {response.status_code}, retrying in {wait_time}s"
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        raise Exception(f"Ошибка сервера: {response.status_code}")

                    if response.status_code >= 400:
                        raise Exception(f"API error: {response.status_code}")

                    return response.json()

            except httpx.TimeoutException:
                if attempt < retries:
                    wait_time = 2**attempt
                    logger.warning(f"Timeout, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                raise Exception("Превышено время ожидания")
            except httpx.ConnectError:
                if attempt < retries:
                    wait_time = 2**attempt
                    logger.warning(f"Connection error, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                raise Exception("Ошибка подключения")

        return None

    async def health_check(self) -> dict[Any, Any] | None:
        """Health check via calc service"""
        return await self.request_with_retries("GET", "/calc/health")

    async def get_goszakup_lot(self, lot_id: str) -> dict[Any, Any]:
        """Get lot from Goszakup API"""
        return await self.request_with_retries("GET", f"/goszakup/lot/{lot_id}")

    async def calc_lot(self, lot_data: dict[str, Any]) -> dict[Any, Any]:
        """Calculate lot financials"""
        return await self.request_with_retries("POST", "/calc/calc", json_data=lot_data)

    async def analyze_risk(self, lot_data: dict[str, Any]) -> dict[Any, Any]:
        """Analyze lot risk"""
        return await self.request_with_retries(
            "POST", "/risk/analyze", json_data=lot_data
        )

    async def generate_doc(
        self, lot_data: dict[str, Any], doc_type: str = "tldr"
    ) -> dict[Any, Any]:
        """Generate document"""
        payload = {**lot_data, "type": doc_type}
        return await self.request_with_retries(
            "POST", "/doc/generate", json_data=payload
        )

    async def ingest_embedding(self, lot_data: dict[str, Any]) -> dict[Any, Any] | None:
        """Ingest to embeddings (non-blocking)"""
        try:
            return await self.request_with_retries(
                "POST", "/emb/ingest", json_data=lot_data, retries=1
            )
        except Exception as e:
            logger.warning(f"Embedding ingest failed (non-critical): {e}")
            return None

    async def search_hot_lots(self, criteria: dict[str, Any]) -> dict[Any, Any]:
        """Search for hot lots based on criteria"""
        return await self.request_with_retries(
            "POST", "/search/hot-lots", json_data=criteria
        )


class LotPipeline:
    """
    Full lot analysis pipeline
    """

    def __init__(self, client: ZakupaiHTTPClient):
        self.client = client

    async def process_lot(self, lot_id: str) -> dict[str, Any]:
        """
        Full pipeline: Goszakup → Calc → Risk → Doc → Embedding
        """
        result = {
            "lot_id": lot_id,
            "goszakup": None,
            "calc": None,
            "risk": None,
            "doc": None,
            "embedding": None,
            "errors": [],
        }

        try:
            # 1. Get lot from Goszakup
            goszakup_data = await self.client.get_goszakup_lot(lot_id)
            result["goszakup"] = goszakup_data

            # 2. Calculate financials
            calc_data = await self.client.calc_lot(goszakup_data)
            result["calc"] = calc_data

            # 3. Analyze risk
            risk_data = await self.client.analyze_risk({**goszakup_data, **calc_data})
            result["risk"] = risk_data

            # 4. Generate document
            doc_data = await self.client.generate_doc(
                {**goszakup_data, **calc_data, **risk_data}
            )
            result["doc"] = doc_data

            # 5. Ingest to embeddings (non-blocking)
            embedding_task = asyncio.create_task(
                self.client.ingest_embedding(
                    {**goszakup_data, **calc_data, **risk_data}
                )
            )
            result["embedding"] = await embedding_task

        except Exception as e:
            result["errors"].append(f"Pipeline error: {str(e)}")

        return result

    async def find_hot_lots(self) -> dict[str, Any]:
        """
        Find hot lots: margin ≥ 15%, risk.score ≥ 60, deadline ≤ 3 days
        """
        deadline_cutoff = datetime.now() + timedelta(days=3)

        criteria = {
            "margin_min": 15.0,
            "risk_score_min": 60.0,
            "deadline_max": deadline_cutoff.isoformat(),
            "limit": 20,
        }

        return await self.client.search_hot_lots(criteria)
