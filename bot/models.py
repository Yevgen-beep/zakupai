from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class RiskLevel(str, Enum):
    """Уровни риска"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ServiceStatus(str, Enum):
    """Статусы сервисов"""

    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"


# === API Response Models ===


class HealthResponse(BaseModel):
    """Ответ health check"""

    status: str
    timestamp: datetime | None = None
    service: str | None = None


class InfoResponse(BaseModel):
    """Ответ info endpoint"""

    service: str
    version: str
    environment: str
    uptime: str | None = None


# === Doc Service Models ===


class TLDRRequest(BaseModel):
    """Запрос TL;DR"""

    lot_id: str = Field(..., description="ID лота")


class TLDRResponse(BaseModel):
    """Ответ TL;DR"""

    lot_id: str
    title: str | None = None
    description: str | None = None
    price: float | None = None
    currency: str = "KZT"
    customer: str | None = None
    customer_bin: str | None = None
    deadline: str | None = None
    summary: str | None = None


class LetterGenerateRequest(BaseModel):
    """Запрос генерации письма"""

    template: str = Field(..., description="Тип шаблона")
    context: dict[str, Any] = Field(..., description="Контекст для шаблона")


class LetterGenerateResponse(BaseModel):
    """Ответ генерации письма"""

    content: str
    template_used: str
    generated_at: datetime


class RenderRequest(BaseModel):
    """Запрос рендеринга"""

    content: str = Field(..., description="Контент для рендеринга")
    html_content: str | None = None  # Для PDF рендеринга


class RenderResponse(BaseModel):
    """Ответ рендеринга"""

    rendered_content: str | None = None
    rendered_html: str | None = None
    file_path: str | None = None
    file_size: int | None = None


# === Risk Engine Models ===


class RiskScoreRequest(BaseModel):
    """Запрос риск-скора"""

    lot_id: str = Field(..., description="ID лота")


class RiskScoreResponse(BaseModel):
    """Ответ риск-скора"""

    lot_id: str
    score: float = Field(..., ge=0.0, le=1.0, description="Риск-скор от 0 до 1")
    level: RiskLevel
    explanation: str | None = None
    factors: list[str] | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    evaluated_at: datetime

    @field_validator("score", "confidence")
    @classmethod
    def validate_score_range(cls, v):
        """Валидация диапазона скоров"""
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("Score must be between 0.0 and 1.0")
        return v


class RiskExplanationResponse(BaseModel):
    """Ответ объяснения рисков"""

    lot_id: str
    detailed_explanation: str
    risk_factors: list[dict[str, Any]]
    recommendations: list[str] | None = None


# === Calc Service Models ===


class VATRequest(BaseModel):
    """Запрос расчёта НДС"""

    amount: float = Field(..., gt=0, description="Сумма для расчёта НДС")
    vat_rate: float = Field(0.12, ge=0.0, le=1.0, description="Ставка НДС")

    @field_validator("amount")
    @classmethod
    def validate_positive_amount(cls, v):
        """Валидация положительных сумм"""
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


class VATResponse(BaseModel):
    """Ответ расчёта НДС"""

    amount: float
    vat_rate: float
    vat_amount: float
    amount_without_vat: float
    total_with_vat: float


class MarginRequest(BaseModel):
    """Запрос расчёта маржи"""

    cost_price: float = Field(..., gt=0, description="Себестоимость")
    selling_price: float = Field(..., gt=0, description="Цена продажи")
    quantity: int = Field(1, gt=0, description="Количество")

    @field_validator("cost_price", "selling_price")
    @classmethod
    def validate_positive_amount(cls, v):
        """Валидация положительных сумм"""
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


class MarginResponse(BaseModel):
    """Ответ расчёта маржи"""

    cost_price: float
    selling_price: float
    quantity: int
    total_cost: float
    total_revenue: float
    margin_amount: float
    margin_percentage: float
    roi_percentage: float


class PenaltyRequest(BaseModel):
    """Запрос расчёта пени"""

    contract_amount: float = Field(..., gt=0, description="Сумма контракта")
    days_overdue: int = Field(..., gt=0, description="Дни просрочки")
    penalty_rate: float = Field(0.1, ge=0.0, le=1.0, description="Ставка пени в день")

    @field_validator("contract_amount")
    @classmethod
    def validate_positive_amount(cls, v):
        """Валидация положительных сумм"""
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


class PenaltyResponse(BaseModel):
    """Ответ расчёта пени"""

    contract_amount: float
    days_overdue: int
    penalty_rate: float
    penalty_amount: float
    total_amount: float


# === Embedding API Models ===


class EmbedRequest(BaseModel):
    """Запрос эмбеддинга"""

    text: str = Field(..., min_length=1, description="Текст для эмбеддинга")
    model: str = Field("all-MiniLM-L6-v2", description="Модель эмбеддинга")


class EmbedResponse(BaseModel):
    """Ответ эмбеддинга"""

    embedding: list[float]
    model: str
    dimension: int
    text_length: int


class IndexRequest(BaseModel):
    """Запрос индексации документа"""

    doc_id: str = Field(..., description="Уникальный ID документа")
    content: str = Field(..., min_length=1, description="Содержимое документа")
    metadata: dict[str, Any] | None = None


class IndexResponse(BaseModel):
    """Ответ индексации"""

    doc_id: str
    indexed: bool
    embedding_dimension: int
    content_length: int


class SearchRequest(BaseModel):
    """Запрос поиска"""

    query: str = Field(..., min_length=1, description="Поисковый запрос")
    limit: int = Field(10, gt=0, le=100, description="Лимит результатов")
    threshold: float = Field(0.7, ge=0.0, le=1.0, description="Порог схожести")


class SearchResult(BaseModel):
    """Результат поиска"""

    doc_id: str
    content: str
    score: float
    metadata: dict[str, Any] | None = None


class SearchResponse(BaseModel):
    """Ответ поиска"""

    query: str
    results: list[SearchResult]
    total_found: int
    search_time: float


# === Database Models ===


class TelegramUser(BaseModel):
    """Модель пользователя Telegram"""

    user_id: int = Field(..., description="Telegram user ID")
    api_key: str = Field(..., min_length=10, description="API ключ ZakupAI")
    created_at: datetime
    updated_at: datetime
    is_active: bool = True


class UserStats(BaseModel):
    """Статистика пользователя"""

    user_id: int
    registered_at: datetime
    last_updated: datetime
    is_active: bool
    requests_count: int | None = 0
    last_request_at: datetime | None = None


# === Analysis Models ===


class LotAnalysisResult(BaseModel):
    """Результат полного анализа лота"""

    lot_id: str
    tldr: TLDRResponse | None = None
    risk: RiskScoreResponse | None = None
    finance: VATResponse | None = None
    documents: list[SearchResult] | None = None
    errors: list[str] = []
    analysis_time: float | None = None
    analyzed_at: datetime


class PipelineStatus(BaseModel):
    """Статус выполнения пайплайна"""

    lot_id: str
    stage: str  # tldr, risk, finance, documents
    status: ServiceStatus
    progress: float = Field(0.0, ge=0.0, le=1.0)
    message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


# === Bot Models ===


class BotCommand(BaseModel):
    """Команда бота"""

    command: str
    user_id: int
    chat_id: int
    message_text: str
    timestamp: datetime


class BotResponse(BaseModel):
    """Ответ бота"""

    text: str
    parse_mode: str | None = "HTML"
    reply_markup: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Стандартный ответ об ошибке"""

    error: str
    code: str | None = None
    details: dict[str, Any] | None = None
    timestamp: datetime


# === Validation and Utility Functions ===


def validate_lot_id(lot_id: str) -> bool:
    """Безопасная валидация ID лота"""
    import re

    if not lot_id or not isinstance(lot_id, str):
        return False

    # Только цифры, от 1 до 20 символов
    if not re.match(r"^[0-9]{1,20}$", lot_id):
        return False

    # Дополнительная проверка диапазона
    try:
        lot_num = int(lot_id)
        return 1 <= lot_num <= 99999999999999999999  # Разумные пределы
    except ValueError:
        return False


def extract_lot_id_from_url(url: str) -> str | None:
    """Безопасное извлечение ID лота из URL"""
    import re
    from urllib.parse import urlparse

    if not url or not isinstance(url, str):
        return None

    # Ограничиваем длину URL для защиты от DoS
    if len(url) > 2048:
        return None

    # Валидация URL
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            return None
        if not parsed.netloc:
            return None
        # Проверяем на подозрительные схемы
        if parsed.scheme in ["javascript", "data", "vbscript"]:
            return None
    except Exception:
        return None

    # Безопасные паттерны для извлечения ID
    safe_patterns = [
        r"/announce/index/(\d{1,20})",
        r"/lot/(\d{1,20})",
        r"lot_id=(\d{1,20})",
        r"id=(\d{1,20})",
    ]

    for pattern in safe_patterns:
        try:
            match = re.search(pattern, url)
            if match:
                lot_id = match.group(1)
                # Дополнительная валидация извлеченного ID
                if validate_lot_id(lot_id):
                    return lot_id
        except re.error:
            continue  # Пропускаем некорректные паттерны

    return None


def sanitize_text_input(text: str, max_length: int = 1000) -> str:
    """Санитизация текстового ввода от пользователя"""
    import html

    if not text or not isinstance(text, str):
        return ""

    # Ограничиваем длину
    text = text[:max_length]

    # Удаляем потенциально опасные символы
    text = html.escape(text)

    # Удаляем управляющие символы кроме переводов строк и табов
    clean_text = ""
    for char in text:
        if ord(char) >= 32 or char in ["\n", "\t"]:
            clean_text += char

    return clean_text.strip()


def validate_email_format(email: str) -> bool:
    """Безопасная валидация email"""
    import re

    if not email or not isinstance(email, str):
        return False

    if len(email) > 254:  # RFC 5321 limit
        return False

    # Простая но надежная проверка email
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def format_currency(amount: float, currency: str = "KZT") -> str:
    """Безопасное форматирование валюты"""
    # Валидация входных данных
    if not isinstance(amount, int | float):
        return "N/A"

    if not isinstance(currency, str) or len(currency) > 10:
        currency = "KZT"

    # Санитизация валюты
    currency = sanitize_text_input(currency, 10).upper()

    try:
        if currency == "KZT":
            return f"{amount:,.0f} тг"
        return f"{amount:,.2f} {currency}"
    except (ValueError, OverflowError):
        return "N/A"


def get_risk_level_emoji(level: RiskLevel) -> str:
    """Получение эмодзи для уровня риска"""
    emoji_map = {RiskLevel.LOW: "🟢", RiskLevel.MEDIUM: "🟡", RiskLevel.HIGH: "🔴"}
    return emoji_map.get(level, "⚪")


def calculate_risk_level(score: float) -> RiskLevel:
    """Вычисление уровня риска по скору"""
    if score < 0.3:
        return RiskLevel.LOW
    elif score < 0.7:
        return RiskLevel.MEDIUM
    else:
        return RiskLevel.HIGH
