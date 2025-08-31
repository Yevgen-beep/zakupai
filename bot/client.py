import asyncio
import logging
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientTimeout

logger = logging.getLogger(__name__)


class ZakupaiAPIClient:
    """
    Асинхронный клиент для взаимодействия с ZakupAI API
    """

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = ClientTimeout(total=30)
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "ZakupAI-TelegramBot/1.0",
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: dict | None = None,
        params: dict | None = None,
    ) -> dict[Any, Any] | None:
        """
        Универсальный метод для HTTP запросов
        """
        url = f"{self.base_url}{endpoint}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=json_data,
                    params=params,
                ) as response:
                    if response.status == 429:
                        logger.warning(f"Rate limit exceeded for {endpoint}")
                        raise Exception("Превышен лимит запросов, попробуйте позже")

                    if response.status == 401:
                        logger.error(f"Unauthorized request to {endpoint}")
                        raise Exception("Неверный API ключ")

                    if response.status == 404:
                        logger.error(f"Endpoint not found: {endpoint}")
                        raise Exception("Сервис недоступен")

                    if response.status >= 400:
                        error_text = await response.text()
                        logger.error(f"API error {response.status}: {error_text}")
                        raise Exception(f"Ошибка API: {response.status}")

                    return await response.json()

        except ClientError as e:
            logger.error(f"Network error for {endpoint}: {e}")
            raise Exception("Ошибка сети, попробуйте позже") from e
        except TimeoutError as e:
            logger.error(f"Timeout for {endpoint}")
            raise Exception("Превышено время ожидания") from e

    async def health_check(self) -> dict[Any, Any] | None:
        """
        Проверка доступности API
        """
        try:
            return await self._make_request("GET", "/health")
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return None

    async def get_info(self) -> dict[Any, Any] | None:
        """
        Получение информации о системе (требует X-API-Key)
        """
        return await self._make_request("GET", "/info")

    # === DOC-SERVICE ===

    async def get_tldr(self, lot_id: str) -> dict[Any, Any]:
        """
        Получение краткого описания лота
        """
        return await self._make_request(
            "POST", "/doc/tldr", json_data={"lot_id": lot_id}
        )

    async def generate_letter(
        self, template_type: str, context: dict[str, Any]
    ) -> dict[Any, Any]:
        """
        Генерация письма/документа
        """
        return await self._make_request(
            "POST",
            "/doc/letters/generate",
            json_data={"template": template_type, "context": context},
        )

    async def render_html(self, content: str) -> dict[Any, Any]:
        """
        Рендеринг HTML документа
        """
        return await self._make_request(
            "POST", "/doc/render/html", json_data={"content": content}
        )

    async def render_pdf(self, html_content: str) -> dict[Any, Any]:
        """
        Рендеринг PDF из HTML
        """
        return await self._make_request(
            "POST", "/doc/render/pdf", json_data={"html_content": html_content}
        )

    # === RISK-ENGINE ===

    async def get_risk_score(self, lot_id: str) -> dict[Any, Any]:
        """
        Получение риск-скора для лота
        """
        return await self._make_request(
            "POST", "/risk/score", json_data={"lot_id": lot_id}
        )

    async def get_risk_explanation(self, lot_id: str) -> dict[Any, Any]:
        """
        Получение объяснения риск-скора
        """
        return await self._make_request("GET", f"/risk/explain/{lot_id}")

    # === CALC-SERVICE ===

    async def calculate_vat(
        self, amount: float, vat_rate: float = 0.12
    ) -> dict[Any, Any]:
        """
        Расчёт НДС
        """
        return await self._make_request(
            "POST", "/calc/vat", json_data={"amount": amount, "vat_rate": vat_rate}
        )

    async def calculate_margin(
        self, cost_price: float, selling_price: float, quantity: int = 1
    ) -> dict[Any, Any]:
        """
        Расчёт маржи и прибыли
        """
        return await self._make_request(
            "POST",
            "/calc/margin",
            json_data={
                "cost_price": cost_price,
                "selling_price": selling_price,
                "quantity": quantity,
            },
        )

    async def calculate_penalty(
        self, contract_amount: float, days_overdue: int, penalty_rate: float = 0.1
    ) -> dict[Any, Any]:
        """
        Расчёт пени по контракту
        """
        return await self._make_request(
            "POST",
            "/calc/penalty",
            json_data={
                "contract_amount": contract_amount,
                "days_overdue": days_overdue,
                "penalty_rate": penalty_rate,
            },
        )

    # === BILLING-SERVICE ===

    async def validate_key(self, api_key: str, endpoint: str = "unknown") -> bool:
        """
        Валидация API ключа через Billing Service
        """
        try:
            # Создаем временную сессию для обращения к billing-service напрямую
            billing_url = "http://billing-service:7004/billing/validate_key"
            headers = {"Content-Type": "application/json"}

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    billing_url,
                    headers=headers,
                    json={"api_key": api_key, "endpoint": endpoint},
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("valid", False)
                    else:
                        logger.error(f"Billing service error: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"Key validation error: {e}")
            return False

    async def create_billing_key(self, tg_id: int, email: str = None) -> str:
        """
        Создание API ключа через Billing Service
        """
        try:
            # Создаем временную сессию для обращения к billing-service напрямую
            billing_url = "http://billing-service:7004/billing/create_key"
            headers = {"Content-Type": "application/json"}

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    billing_url, headers=headers, json={"tg_id": tg_id, "email": email}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("api_key", "")
                    else:
                        logger.error(f"Billing service error: {response.status}")
                        return ""
        except Exception as e:
            logger.error(f"Key creation error: {e}")
            return ""

    async def log_usage(self, api_key: str, endpoint: str, requests: int = 1) -> bool:
        """
        Логирование использования API
        """
        try:
            # Создаем временную сессию для обращения к billing-service напрямую
            billing_url = "http://billing-service:7004/billing/usage"
            headers = {"Content-Type": "application/json"}

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    billing_url,
                    headers=headers,
                    json={
                        "api_key": api_key,
                        "endpoint": endpoint,
                        "requests": requests,
                    },
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("logged", False)
                    else:
                        logger.error(f"Billing service error: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"Usage logging error: {e}")
            return False

    # === EMBEDDING-API ===

    async def embed_text(
        self, text: str, model: str = "all-MiniLM-L6-v2"
    ) -> dict[Any, Any]:
        """
        Получение эмбеддингов для текста
        """
        return await self._make_request(
            "POST", "/embed", json_data={"text": text, "model": model}
        )

    async def index_document(
        self, doc_id: str, content: str, metadata: dict | None = None
    ) -> dict[Any, Any]:
        """
        Индексация документа
        """
        return await self._make_request(
            "POST",
            "/index",
            json_data={
                "doc_id": doc_id,
                "content": content,
                "metadata": metadata or {},
            },
        )

    async def search_documents(
        self, query: str, limit: int = 10, threshold: float = 0.7
    ) -> dict[Any, Any]:
        """
        Поиск по документам
        """
        return await self._make_request(
            "POST",
            "/search",
            json_data={"query": query, "limit": limit, "threshold": threshold},
        )


class ZakupaiPipelineClient:
    """
    Высокоуровневый клиент для комплексного анализа лотов
    """

    def __init__(self, api_client: ZakupaiAPIClient):
        self.api = api_client

    async def analyze_lot_full(self, lot_id: str) -> dict[str, Any]:
        """
        Полный анализ лота: TL;DR + риск + финансы
        """
        result = {
            "lot_id": lot_id,
            "tldr": None,
            "risk": None,
            "finance": None,
            "documents": None,
            "errors": [],
        }

        # Параллельные запросы для TL;DR и риск-анализа
        try:
            tldr_task = self.api.get_tldr(lot_id)
            risk_task = self.api.get_risk_score(lot_id)

            tldr_result, risk_result = await asyncio.gather(
                tldr_task, risk_task, return_exceptions=True
            )

            if isinstance(tldr_result, Exception):
                result["errors"].append(f"TL;DR error: {tldr_result}")
            else:
                result["tldr"] = tldr_result

            if isinstance(risk_result, Exception):
                result["errors"].append(f"Risk error: {risk_result}")
            else:
                result["risk"] = risk_result

        except Exception as e:
            result["errors"].append(f"Analysis error: {e}")

        # Финансовые расчёты на основе TL;DR
        if result["tldr"] and "price" in result["tldr"]:
            try:
                price = float(result["tldr"]["price"])
                vat_result = await self.api.calculate_vat(price)
                result["finance"] = vat_result
            except Exception as e:
                result["errors"].append(f"Finance error: {e}")

        return result

    async def generate_lot_report(self, lot_id: str) -> str:
        """
        Генерация отчёта по лоту в формате HTML
        """
        analysis = await self.analyze_lot_full(lot_id)

        html_content = self._format_analysis_html(analysis)

        try:
            render_result = await self.api.render_html(html_content)
            return render_result.get("rendered_html", html_content)
        except Exception as e:
            logger.error(f"HTML render error: {e}")
            return html_content

    def _format_analysis_html(self, analysis: dict[str, Any]) -> str:
        """
        Форматирование анализа в HTML
        """
        lot_id = analysis["lot_id"]

        html = f"""
        <html>
        <head>
            <title>Анализ лота {lot_id}</title>
            <meta charset="utf-8">
        </head>
        <body>
            <h1>Анализ лота {lot_id}</h1>
        """

        if analysis.get("tldr"):
            tldr = analysis["tldr"]
            html += f"""
            <h2>Краткое описание</h2>
            <ul>
                <li><strong>Название:</strong> {tldr.get('title', 'N/A')}</li>
                <li><strong>Цена:</strong> {tldr.get('price', 'N/A')} тг</li>
                <li><strong>Заказчик:</strong> {tldr.get('customer', 'N/A')}</li>
            </ul>
            """

        if analysis.get("risk"):
            risk = analysis["risk"]
            html += f"""
            <h2>Риск-анализ</h2>
            <p><strong>Уровень риска:</strong> {risk.get('score', 0):.2f}</p>
            <p><strong>Объяснение:</strong> {risk.get('explanation', 'N/A')}</p>
            """

        if analysis.get("finance"):
            finance = analysis["finance"]
            html += f"""
            <h2>Финансовые расчёты</h2>
            <ul>
                <li><strong>Без НДС:</strong> {finance.get('amount_without_vat', 'N/A')} тг</li>
                <li><strong>НДС:</strong> {finance.get('vat_amount', 'N/A')} тг</li>
                <li><strong>Итого:</strong> {finance.get('total_with_vat', 'N/A')} тг</li>
            </ul>
            """

        if analysis.get("errors"):
            html += "<h2>Ошибки</h2><ul>"
            for error in analysis["errors"]:
                html += f"<li>{error}</li>"
            html += "</ul>"

        html += "</body></html>"
        return html
