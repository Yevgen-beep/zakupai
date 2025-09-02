"""
Интеграционный модуль для работы с внешними сервисами ZakupAI
"""

import logging
from datetime import datetime
from typing import Any

import aiohttp
from config import config
from error_handler import handle_api_error, log_security_event
from models import (
    LotAnalysisResult,
    MarginResponse,
    RiskScoreResponse,
    SearchResult,
    TLDRResponse,
    VATResponse,
)

logger = logging.getLogger(__name__)


class BillingService:
    """Сервис для работы с биллинговой системой"""

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
                    if response.status == 401:
                        log_security_event(
                            "INVALID_API_KEY", user_id, {"endpoint": endpoint}
                        )
                        return {"valid": False, "error": "🔑 Недействительный API ключ"}

                    if response.status == 429:
                        log_security_event(
                            "RATE_LIMIT_EXCEEDED", user_id, {"endpoint": endpoint}
                        )
                        return {
                            "valid": False,
                            "error": "⏱️ Превышен лимит запросов. Попробуйте позже",
                        }

                    if response.status != 200:
                        logger.error(f"Billing service error: {response.status}")
                        return {"valid": False, "error": "❌ Ошибка сервиса биллинга"}

                    result = await response.json()

                    if not result.get("valid", False):
                        return {
                            "valid": False,
                            "error": result.get("message", "Ошибка валидации ключа"),
                        }

                # Логируем использование
                usage_data = {
                    "api_key": api_key,
                    "user_id": user_id,
                    "endpoint": endpoint,
                    "cost": cost,
                    "timestamp": datetime.now().isoformat(),
                }

                async with session.post(
                    f"{self.base_url}/billing/usage", json=usage_data, headers=headers
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to log usage: {response.status}")
                        # Не блокируем выполнение если логирование не удалось

                return {"valid": True, "user_plan": result.get("plan", "free")}

        except TimeoutError:
            logger.error(f"Timeout validating API key for user {user_id}")
            return {"valid": False, "error": "⏱️ Превышено время ожидания"}
        except Exception as e:
            logger.error(f"Error validating API key: {type(e).__name__}")
            return {"valid": False, "error": handle_api_error(e, "billing validation")}


class GoszakupService:
    """Сервис для работы с API goszakup.gov.kz"""

    def __init__(self):
        self.base_url = "https://ows.goszakup.gov.kz/v3/trd/lots"

    async def search_lots(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Поиск лотов по ключевым словам"""

        params = {
            "nameRu": query,
            "limit": min(limit, 50),  # Ограничиваем максимум
            "offset": 0,
        }

        headers = {"User-Agent": "ZakupAI Bot/1.0", "Accept": "application/json"}

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                connector=aiohttp.TCPConnector(ssl=True),
            ) as session:
                async with session.get(
                    self.base_url, params=params, headers=headers
                ) as response:
                    if response.status != 200:
                        logger.error(f"Goszakup API error: {response.status}")
                        return []

                    data = await response.json()
                    lots = data.get("items", [])

                    # Форматируем результаты
                    formatted_lots = []
                    for lot in lots[:limit]:
                        formatted_lot = {
                            "id": str(lot.get("id", "")),
                            "name": lot.get("nameRu", "Без названия"),
                            "customer": lot.get("customer", {}).get(
                                "nameRu", "Неизвестный заказчик"
                            ),
                            "price": lot.get("estimateAmount", 0),
                            "currency": "KZT",
                            "status": lot.get("status", {}).get("nameRu", "Неизвестно"),
                            "deadline": lot.get("endDate", ""),
                            "url": f"https://goszakup.gov.kz/ru/announce/index/{lot.get('id', '')}",
                        }
                        formatted_lots.append(formatted_lot)

                    return formatted_lots

        except TimeoutError:
            logger.error("Timeout searching lots in goszakup")
            return []
        except Exception as e:
            logger.error(f"Error searching lots: {type(e).__name__}")
            return []


class ZakupAIService:
    """Сервис для работы с внутренними API ZakupAI"""

    def __init__(self):
        self.gateway_url = config.api.zakupai_api_url

    async def get_tldr(self, lot_id: str, api_key: str) -> TLDRResponse | None:
        """Получение TL;DR для лота"""
        return await self._make_request(
            "/doc/tldr", {"lot_id": lot_id}, api_key, TLDRResponse
        )

    async def get_risk_score(
        self, lot_id: str, api_key: str
    ) -> RiskScoreResponse | None:
        """Получение риск-скора для лота"""
        return await self._make_request(
            "/risk/score", {"lot_id": lot_id}, api_key, RiskScoreResponse
        )

    async def calculate_vat(
        self, amount: float, api_key: str, vat_rate: float = 0.12
    ) -> VATResponse | None:
        """Расчет НДС"""
        return await self._make_request(
            "/calc/vat", {"amount": amount, "vat_rate": vat_rate}, api_key, VATResponse
        )

    async def calculate_margin(
        self, cost_price: float, selling_price: float, api_key: str, quantity: int = 1
    ) -> MarginResponse | None:
        """Расчет маржинальности"""
        return await self._make_request(
            "/calc/margin",
            {
                "cost_price": cost_price,
                "selling_price": selling_price,
                "quantity": quantity,
            },
            api_key,
            MarginResponse,
        )

    async def search_documents(
        self, query: str, api_key: str, limit: int = 5
    ) -> list[SearchResult]:
        """Поиск в документах"""
        result = await self._make_request(
            "/embedding/search",
            {"query": query, "limit": limit, "threshold": 0.7},
            api_key,
            dict,  # SearchResponse
        )

        if result and "results" in result:
            return [SearchResult(**item) for item in result["results"]]
        return []

    async def _make_request(
        self, endpoint: str, data: dict[str, Any], api_key: str, response_model: type
    ) -> Any | None:
        """Универсальный метод для запросов к API"""

        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=config.security.request_timeout),
                connector=aiohttp.TCPConnector(ssl=config.security.ssl_verify),
            ) as session:
                async with session.post(
                    f"{self.gateway_url}{endpoint}", json=data, headers=headers
                ) as response:
                    if response.status == 401:
                        logger.warning(f"Unauthorized request to {endpoint}")
                        return None

                    if response.status != 200:
                        logger.error(f"API error {response.status} for {endpoint}")
                        return None

                    result = await response.json()

                    if response_model is dict:
                        return result

                    try:
                        return response_model(**result)
                    except Exception as e:
                        logger.error(f"Failed to parse response: {type(e).__name__}")
                        return None

        except TimeoutError:
            logger.error(f"Timeout for {endpoint}")
            return None
        except Exception as e:
            logger.error(f"Error calling {endpoint}: {type(e).__name__}")
            return None


# Инициализация сервисов
billing_service = BillingService()
goszakup_service = GoszakupService()
zakupai_service = ZakupAIService()


def format_search_results(lots: list[dict[str, Any]]) -> str:
    """Форматирование результатов поиска для отображения в боте"""

    if not lots:
        return "🔍 Лоты не найдены по вашему запросу."

    text = f"🔍 Найдено лотов: {len(lots)}\n\n"

    for i, lot in enumerate(lots, 1):
        price_str = f"{lot['price']:,.0f} тг" if lot["price"] > 0 else "Цена не указана"

        text += f"<b>{i}. {lot['name'][:100]}</b>\n"
        text += f"💰 {price_str}\n"
        text += f"🏢 {lot['customer'][:80]}\n"
        text += f"📅 Статус: {lot['status']}\n"

        if lot["deadline"]:
            text += f"⏰ До: {lot['deadline'][:10]}\n"

        text += f"🔗 <a href=\"{lot['url']}\">Подробнее</a>\n"
        text += f"📊 Анализ: /lot {lot['id']}\n\n"

        # Ограничиваем размер сообщения
        if len(text) > 3500:
            remaining = len(lots) - i
            if remaining > 0:
                text += f"... и еще {remaining} лотов\n"
            break

    text += "💡 Используйте /lot <ID> для полного анализа лота"

    return text


def format_lot_analysis(analysis: LotAnalysisResult) -> str:
    """Форматирование результата анализа лота"""

    text = f"📊 <b>Анализ лота {analysis.lot_id}</b>\n\n"

    # TL;DR
    if analysis.tldr:
        text += f"📋 <b>{analysis.tldr.title or 'Без названия'}</b>\n"
        text += f"💰 {analysis.tldr.price:,.0f} {analysis.tldr.currency}\n"
        text += f"🏢 {analysis.tldr.customer}\n"
        if analysis.tldr.summary:
            text += f"📝 {analysis.tldr.summary[:200]}...\n"
        text += "\n"

    # Риск-анализ
    if analysis.risk:
        risk_emoji = (
            "🟢"
            if analysis.risk.level == "low"
            else "🟡" if analysis.risk.level == "medium" else "🔴"
        )
        text += f"{risk_emoji} <b>Риск: {analysis.risk.level.upper()}</b> ({analysis.risk.score:.2f})\n"
        if analysis.risk.explanation:
            text += f"⚠️ {analysis.risk.explanation[:150]}...\n"
        text += "\n"

    # Финансы
    if analysis.finance:
        text += "💵 <b>НДС анализ:</b>\n"
        text += f"Сумма без НДС: {analysis.finance.amount_without_vat:,.0f} тг\n"
        text += f"НДС ({analysis.finance.vat_rate*100:.0f}%): {analysis.finance.vat_amount:,.0f} тг\n"
        text += f"Итого с НДС: {analysis.finance.total_with_vat:,.0f} тг\n\n"

    # Ошибки
    if analysis.errors:
        text += f"⚠️ Ошибки: {', '.join(analysis.errors[:2])}\n"

    return text
