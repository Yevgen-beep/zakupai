"""
Универсальный асинхронный клиент для работы с API госзакупок Казахстана v3
Поддерживает GraphQL API с полной типизацией и расширенными возможностями
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientSession, ClientTimeout

logger = logging.getLogger(__name__)


# === ENUMS ===


class TradeMethod(Enum):
    """Способы закупок"""

    OPEN_TENDER = 1  # Открытый конкурс
    REQUEST_QUOTATIONS = 2  # Запрос ценовых предложений
    FROM_ONE_SOURCE = 3  # Из одного источника
    COMPETITION_WORKS = 4  # Конкурс на выполнение работ
    ELECTRONIC_STORE = 5  # Электронный магазин
    SPECIAL_TENDER = 6  # Специальный конкурс


class LotStatus(Enum):
    """Статусы лотов"""

    DRAFT = 1  # Черновик
    PUBLISHED = 2  # Опубликован
    ACCEPTING_APPLICATIONS = 3  # Прием заявок
    APPLICATIONS_REVIEW = 4  # Рассмотрение заявок
    WINNER_SELECTION = 5  # Определение победителя
    COMPLETED = 6  # Завершен
    CANCELLED = 7  # Отменен


class ContractStatus(Enum):
    """Статусы контрактов"""

    DRAFT = 1  # Черновик
    ACTIVE = 2  # Действующий
    COMPLETED = 3  # Исполнен
    TERMINATED = 4  # Расторгнут
    SUSPENDED = 5  # Приостановлен


class SubjectType(Enum):
    """Типы участников"""

    LEGAL_ENTITY = 1  # Юридическое лицо
    INDIVIDUAL = 2  # Физическое лицо
    FOREIGN_ENTITY = 3  # Иностранное юридическое лицо


# === FILTER DATACLASSES ===


@dataclass
class LotsFiltersInput:
    """Фильтры для поиска лотов согласно GraphQL схеме"""

    # Основные поля
    lotNumber: str | None = None
    nameRu: str | None = None
    nameKz: str | None = None
    nameDescriptionRu: str | None = None  # Морфологический поиск
    nameDescriptionKz: str | None = None
    descriptionRu: str | None = None
    descriptionKz: str | None = None

    # Количество и суммы
    count: float | None = None
    amount: float | None = None
    amountFrom: float | None = None
    amountTo: float | None = None

    # Заказчик
    customerNameRu: str | None = None
    customerNameKz: str | None = None
    customerBin: list[str] | None = None
    orgNameRu: str | None = None
    orgNameKz: str | None = None
    orgBin: list[str] | None = None

    # Статусы и методы
    refLotStatusId: list[int] | None = None
    refTradeMethodsId: list[int] | None = None

    # Объявления
    trdBuyNumberAnno: str | None = None
    trdBuyNameRu: str | None = None
    trdBuyNameKz: str | None = None

    # Даты
    publishDate: str | None = None
    publishDateFrom: str | None = None
    publishDateTo: str | None = None
    endDate: str | None = None
    endDateFrom: str | None = None
    endDateTo: str | None = None

    # Дополнительные поля
    isLotOfSmallScale: bool | None = None
    enstruList: list[str] | None = None
    isConstructionWork: bool | None = None

    # Пагинация
    after: str | None = None
    before: str | None = None


@dataclass
class ContractFiltersInput:
    """Фильтры для поиска контрактов"""

    contractNumber: str | None = None
    contractNumberSys: str | None = None

    # Участники
    supplierBiin: list[str] | None = None
    supplierNameRu: str | None = None
    supplierNameKz: str | None = None
    customerBin: list[str] | None = None
    customerNameRu: str | None = None

    # Суммы
    contractSum: float | None = None
    contractSumFrom: float | None = None
    contractSumTo: float | None = None

    # Даты
    signDate: str | None = None
    signDateFrom: str | None = None
    signDateTo: str | None = None
    startDate: str | None = None
    startDateFrom: str | None = None
    startDateTo: str | None = None
    endDate: str | None = None
    endDateFrom: str | None = None
    endDateTo: str | None = None

    # Статусы
    refContractStatusId: list[int] | None = None
    refContractTypeId: list[int] | None = None

    # Связи
    lotId: list[str] | None = None
    trdBuyId: list[str] | None = None

    # Пагинация
    after: str | None = None
    before: str | None = None


@dataclass
class SubjectFiltersInput:
    """Фильтры для поиска участников"""

    bin: list[str] | None = None
    nameRu: str | None = None
    nameKz: str | None = None

    # Адрес
    addressRu: str | None = None
    addressKz: str | None = None

    # Типы
    refSubjectTypeId: list[int] | None = None

    # Статус
    isActive: bool | None = None

    # Даты
    regDate: str | None = None
    regDateFrom: str | None = None
    regDateTo: str | None = None

    # Пагинация
    after: str | None = None
    before: str | None = None


@dataclass
class TrdBuyFiltersInput:
    """Фильтры для поиска объявлений"""

    numberAnno: str | None = None
    nameRu: str | None = None
    nameKz: str | None = None

    # Организатор
    orgBin: list[str] | None = None
    orgNameRu: str | None = None

    # Методы закупок
    refTradeMethodsId: list[int] | None = None

    # Даты
    startDate: str | None = None
    startDateFrom: str | None = None
    startDateTo: str | None = None
    endDate: str | None = None
    endDateFrom: str | None = None
    endDateTo: str | None = None

    # Статус
    refBuyStatusId: list[int] | None = None

    # Пагинация
    after: str | None = None
    before: str | None = None


@dataclass
class SearchRequest:
    """Базовый запрос для поиска"""

    filters: (
        LotsFiltersInput
        | ContractFiltersInput
        | SubjectFiltersInput
        | TrdBuyFiltersInput
    )
    limit: int = 50
    return_fields: list[str] | None = None
    include_nested: bool = True


# === RESULT DATACLASSES ===


@dataclass
class LotResult:
    """Результат поиска лота"""

    id: str
    lotNumber: str = ""
    nameRu: str = ""
    nameKz: str = ""
    descriptionRu: str = ""
    descriptionKz: str = ""
    count: float = 0
    amount: float = 0
    customerNameRu: str = ""
    customerBin: str = ""
    publishDate: str | None = None
    endDate: str | None = None
    status: str = ""
    tradeMethod: str = ""
    trdBuy: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContractResult:
    """Результат поиска контракта"""

    id: str
    contractNumber: str = ""
    contractNumberSys: str = ""
    supplierBiin: str = ""
    supplierNameRu: str = ""
    customerBin: str = ""
    customerNameRu: str = ""
    contractSum: float = 0
    signDate: str | None = None
    startDate: str | None = None
    endDate: str | None = None
    status: str = ""
    acts: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SubjectResult:
    """Результат поиска участника"""

    id: str
    bin: str = ""
    nameRu: str = ""
    nameKz: str = ""
    addressRu: str = ""
    subjectType: str = ""
    isActive: bool = True
    regDate: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# === CACHING ===


@dataclass
class CacheEntry:
    """Элемент кеша"""

    data: Any
    timestamp: float
    ttl: int

    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl


class AsyncCache:
    """Асинхронный кеш с TTL"""

    def __init__(self):
        self._cache: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

    def _make_key(self, *args, **kwargs) -> str:
        """Создание ключа кеша"""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(key_data.encode(), usedforsecurity=False).hexdigest()  # nosec B324

    async def get(self, key: str) -> Any | None:
        """Получение из кеша"""
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if not entry.is_expired():
                    logger.debug(f"Cache hit for key: {key[:10]}...")
                    return entry.data
                else:
                    del self._cache[key]
                    logger.debug(f"Cache expired for key: {key[:10]}...")
            return None

    async def set(self, key: str, data: Any, ttl: int = 300) -> None:
        """Сохранение в кеш"""
        async with self._lock:
            self._cache[key] = CacheEntry(data, time.time(), ttl)
            logger.debug(f"Cached data for key: {key[:10]}... (TTL: {ttl}s)")

    async def clear(self) -> None:
        """Очистка кеша"""
        async with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")


# === RETRY LOGIC ===


class RetryConfig:
    """Конфигурация retry логики"""

    def __init__(
        self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay


async def with_retry(
    func: Callable, retry_config: RetryConfig = RetryConfig(), *args, **kwargs
) -> Any:
    """Выполнение функции с retry логикой и exponential backoff"""
    last_exception = None

    for attempt in range(retry_config.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except (TimeoutError, ClientError, aiohttp.ServerDisconnectedError) as e:
            last_exception = e

            if attempt == retry_config.max_retries:
                logger.error(f"Max retries reached for {func.__name__}")
                break

            # Exponential backoff
            delay = min(retry_config.base_delay * (2**attempt), retry_config.max_delay)

            logger.warning(
                f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {delay}s..."
            )
            await asyncio.sleep(delay)

    raise last_exception


# === MAIN CLIENT ===


class GoszakupClient:
    """
    Универсальный асинхронный клиент для работы с API госзакупок Казахстана v3

    Основные возможности:
    - Полная поддержка GraphQL API v3
    - Расширенная система фильтров
    - Кеширование с TTL
    - Retry логика с exponential backoff
    - Пагинация и field selection
    - Экспорт в различные форматы
    - Мониторинг и webhook поддержка
    """

    def __init__(
        self,
        token: str,
        graphql_url: str = "https://ows.goszakup.gov.kz/v3/graphql",
        timeout: int = 30,
        enable_cache: bool = True,
        cache_ttl: int = 300,
        retry_config: RetryConfig | None = None,
    ):
        self.token = token
        self.graphql_url = graphql_url
        self.timeout = ClientTimeout(total=timeout)
        self.retry_config = retry_config or RetryConfig()

        # Кеш
        self.cache_enabled = enable_cache
        self.cache_ttl = cache_ttl
        self._cache = AsyncCache() if enable_cache else None

        # HTTP заголовки
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "GoszakupClient-v3/1.0",
            "X-Request-ID": "",
        }

        # Статистика
        self._stats = {
            "requests_total": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "retries_total": 0,
            "errors_total": 0,
        }

        # Сессия будет создана при первом использовании
        self._session: ClientSession | None = None

        # Мониторинг
        self._subscriptions: list[dict[str, Any]] = []
        self._monitoring_task: asyncio.Task | None = None

    async def __aenter__(self):
        """Асинхронный контекстный менеджер - вход"""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный контекстный менеджер - выход"""
        await self.close()

    async def _ensure_session(self):
        """Создание HTTP сессии если необходимо"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self.timeout, headers=self.headers
            )

    async def close(self):
        """Закрытие клиента и освобождение ресурсов"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        if self._session and not self._session.closed:
            await self._session.close()

        if self._cache:
            await self._cache.clear()

    def _generate_query(
        self,
        entity_type: str,
        filters: dict[str, Any],
        return_fields: list[str],
        limit: int = 50,
        after: str | None = None,
    ) -> dict[str, Any]:
        """Генерация GraphQL запроса"""

        # Поля по умолчанию для разных типов сущностей
        default_fields = {
            "Lots": [
                "id",
                "lotNumber",
                "nameRu",
                "nameKz",
                "descriptionRu",
                "count",
                "amount",
                "customerNameRu",
                "customerBin",
                "RefLotsStatus { nameRu }",
                "TrdBuy { id numberAnno nameRu orgNameRu orgBin startDate endDate publishDate RefTradeMethods { nameRu } }",
            ],
            "Contract": [
                "id",
                "contractNumber",
                "contractNumberSys",
                "supplierBiin",
                "supplierNameRu",
                "customerBin",
                "customerNameRu",
                "contractSum",
                "signDate",
                "startDate",
                "endDate",
                "RefContractStatus { nameRu }",
                "Acts { id actNumber actSum signDate }",
            ],
            "Subjects": [
                "id",
                "bin",
                "nameRu",
                "nameKz",
                "addressRu",
                "isActive",
                "regDate",
                "RefSubjectType { nameRu }",
            ],
            "TrdBuy": [
                "id",
                "numberAnno",
                "nameRu",
                "nameKz",
                "orgNameRu",
                "orgBin",
                "startDate",
                "endDate",
                "RefTradeMethods { nameRu }",
                "RefBuyStatus { nameRu }",
            ],
        }

        # Используем указанные поля или поля по умолчанию
        fields = (
            return_fields if return_fields else default_fields.get(entity_type, ["id"])
        )
        fields_str = " ".join(fields)

        # Создание переменных для пагинации
        pagination_vars = []
        if limit:
            pagination_vars.append("limit: $limit")
        if after:
            pagination_vars.append("after: $after")

        # Определяем переменные для GraphQL запроса
        query_variables = [f"$filter: {entity_type}FiltersInput"]
        if limit:
            query_variables.append("$limit: Int")
        if after:
            query_variables.append("$after: String")

        variables_str = ", ".join(query_variables)

        # Генерация запроса
        query = f"""
        query Search{entity_type}({variables_str}) {{
          {entity_type}(filter: $filter{", " + ", ".join(pagination_vars) if pagination_vars else ""}) {{
            {fields_str}
          }}
        }}
        """

        variables = {"filter": filters, "limit": limit}

        if after:
            variables["after"] = after

        return {"query": query.strip(), "variables": variables}

    async def _make_request(self, query: dict[str, Any]) -> dict[str, Any]:
        """Выполнение GraphQL запроса"""
        await self._ensure_session()

        # Генерация уникального ID запроса
        request_id = str(uuid.uuid4())
        headers = self.headers.copy()
        headers["X-Request-ID"] = request_id

        self._stats["requests_total"] += 1

        logger.debug(f"GraphQL request {request_id}: {query['query'][:100]}...")

        async def _do_request():
            async with self._session.post(
                self.graphql_url, json=query, headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    if "errors" in data:
                        self._stats["errors_total"] += 1
                        error_msg = f"GraphQL errors: {data['errors']}"
                        logger.error(error_msg)
                        raise Exception(error_msg)

                    return data

                elif response.status == 401:
                    self._stats["errors_total"] += 1
                    raise Exception("GraphQL API authorization failed - invalid token")

                elif response.status == 403:
                    self._stats["errors_total"] += 1
                    raise Exception(
                        "GraphQL API access forbidden - token may be blocked"
                    )

                else:
                    self._stats["errors_total"] += 1
                    error_text = await response.text()
                    raise Exception(
                        f"GraphQL API error {response.status}: {error_text}"
                    )

        # Выполнение с retry логикой
        return await with_retry(_do_request, self.retry_config)

    async def _cached_request(self, query: dict[str, Any]) -> dict[str, Any]:
        """Выполнение запроса с кешированием"""
        if not self.cache_enabled or not self._cache:
            return await self._make_request(query)

        # Создание ключа кеша
        cache_key = self._cache._make_key(query)

        # Проверка кеша
        cached_result = await self._cache.get(cache_key)
        if cached_result is not None:
            self._stats["cache_hits"] += 1
            return cached_result

        # Выполнение запроса
        self._stats["cache_misses"] += 1
        result = await self._make_request(query)

        # Сохранение в кеш
        await self._cache.set(cache_key, result, self.cache_ttl)

        return result

    def _clean_filters(self, filters: dict[str, Any] | Any) -> dict[str, Any]:
        """Очистка фильтров от None значений"""
        if hasattr(filters, "__dict__"):
            filters = asdict(filters)

        return {k: v for k, v in filters.items() if v is not None}

    # === PUBLIC METHODS ===

    async def search_lots(
        self,
        keyword: str | None = None,
        customer_bin: list[str] | None = None,
        trade_methods: list[TradeMethod] | None = None,
        status: list[LotStatus] | None = None,
        amount_range: tuple[float, float] | None = None,
        publish_date_from: str | None = None,
        publish_date_to: str | None = None,
        end_date_from: str | None = None,
        end_date_to: str | None = None,
        regions: list[str] | None = None,
        limit: int = 50,
        after: str | None = None,
        return_fields: list[str] | None = None,
        **additional_filters,
    ) -> list[LotResult]:
        """
        Поиск лотов с расширенными фильтрами

        Args:
            keyword: Ключевое слово для поиска в названии/описании
            customer_bin: Список БИН заказчиков
            trade_methods: Способы закупок
            status: Статусы лотов
            amount_range: Диапазон сумм (от, до)
            publish_date_from: Дата публикации от (ISO format)
            publish_date_to: Дата публикации до
            end_date_from: Дата завершения от
            end_date_to: Дата завершения до
            regions: Регионы (будет искать в названии организации)
            limit: Максимальное количество результатов
            after: Курсор для пагинации
            return_fields: Поля для возврата
            **additional_filters: Дополнительные фильтры

        Returns:
            Список найденных лотов
        """
        # Создание фильтров
        filters = LotsFiltersInput()

        if keyword:
            filters.nameDescriptionRu = keyword

        if customer_bin:
            filters.customerBin = customer_bin

        if trade_methods:
            filters.refTradeMethodsId = [method.value for method in trade_methods]

        if status:
            filters.refLotStatusId = [stat.value for stat in status]

        if amount_range:
            filters.amountFrom, filters.amountTo = amount_range

        if publish_date_from:
            filters.publishDateFrom = publish_date_from
        if publish_date_to:
            filters.publishDateTo = publish_date_to
        if end_date_from:
            filters.endDateFrom = end_date_from
        if end_date_to:
            filters.endDateTo = end_date_to

        if regions:
            # Поиск по регионам через название организации
            region_pattern = "|".join(regions)
            filters.orgNameRu = region_pattern

        if after:
            filters.after = after

        # Добавление дополнительных фильтров
        for key, value in additional_filters.items():
            if hasattr(filters, key):
                setattr(filters, key, value)

        # Очистка от None значений
        clean_filters = self._clean_filters(filters)

        # Генерация и выполнение запроса
        query = self._generate_query(
            "Lots", clean_filters, return_fields or [], limit, after
        )
        result = await self._cached_request(query)

        # Парсинг результатов
        lots_data = result.get("data", {}).get("Lots", [])
        return [self._parse_lot_result(lot) for lot in lots_data]

    async def search_contracts(
        self,
        supplier_bin: list[str] | None = None,
        customer_bin: list[str] | None = None,
        contract_sum_range: tuple[float, float] | None = None,
        sign_date_from: str | None = None,
        sign_date_to: str | None = None,
        status: list[ContractStatus] | None = None,
        include_acts: bool = False,
        include_payments: bool = False,
        limit: int = 50,
        after: str | None = None,
        return_fields: list[str] | None = None,
        **additional_filters,
    ) -> list[ContractResult]:
        """
        Поиск контрактов

        Args:
            supplier_bin: БИН поставщиков
            customer_bin: БИН заказчиков
            contract_sum_range: Диапазон сумм контрактов
            sign_date_from: Дата подписания от
            sign_date_to: Дата подписания до
            status: Статусы контрактов
            include_acts: Включить акты в результат
            include_payments: Включить платежи в результат
            limit: Максимальное количество результатов
            after: Курсор для пагинации
            return_fields: Поля для возврата
            **additional_filters: Дополнительные фильтры

        Returns:
            Список найденных контрактов
        """
        filters = ContractFiltersInput()

        if supplier_bin:
            filters.supplierBiin = supplier_bin
        if customer_bin:
            filters.customerBin = customer_bin
        if contract_sum_range:
            filters.contractSumFrom, filters.contractSumTo = contract_sum_range
        if sign_date_from:
            filters.signDateFrom = sign_date_from
        if sign_date_to:
            filters.signDateTo = sign_date_to
        if status:
            filters.refContractStatusId = [stat.value for stat in status]
        if after:
            filters.after = after

        # Добавление дополнительных фильтров
        for key, value in additional_filters.items():
            if hasattr(filters, key):
                setattr(filters, key, value)

        clean_filters = self._clean_filters(filters)

        # Расширение полей возврата при необходимости
        if not return_fields:
            return_fields = [
                "id",
                "contractNumber",
                "contractNumberSys",
                "supplierBiin",
                "supplierNameRu",
                "customerBin",
                "customerNameRu",
                "contractSum",
                "signDate",
                "startDate",
                "endDate",
                "RefContractStatus { nameRu }",
            ]

            if include_acts:
                return_fields.append("Acts { id actNumber actSum signDate }")

            if include_payments:
                return_fields.append("Payments { id paymentSum paymentDate }")

        query = self._generate_query(
            "Contract", clean_filters, return_fields, limit, after
        )
        result = await self._cached_request(query)

        contracts_data = result.get("data", {}).get("Contract", [])
        return [self._parse_contract_result(contract) for contract in contracts_data]

    async def search_subjects(
        self,
        bin_list: list[str] | None = None,
        name_keyword: str | None = None,
        subject_type: list[SubjectType] | None = None,
        is_active: bool | None = None,
        limit: int = 50,
        after: str | None = None,
        return_fields: list[str] | None = None,
        **additional_filters,
    ) -> list[SubjectResult]:
        """
        Поиск участников

        Args:
            bin_list: Список БИН для поиска
            name_keyword: Ключевое слово в названии
            subject_type: Тип участника
            is_active: Активный статус
            limit: Максимальное количество результатов
            after: Курсор для пагинации
            return_fields: Поля для возврата
            **additional_filters: Дополнительные фильтры

        Returns:
            Список найденных участников
        """
        filters = SubjectFiltersInput()

        if bin_list:
            filters.bin = bin_list
        if name_keyword:
            filters.nameRu = name_keyword
        if subject_type:
            filters.refSubjectTypeId = [stype.value for stype in subject_type]
        if is_active is not None:
            filters.isActive = is_active
        if after:
            filters.after = after

        for key, value in additional_filters.items():
            if hasattr(filters, key):
                setattr(filters, key, value)

        clean_filters = self._clean_filters(filters)
        query = self._generate_query(
            "Subjects", clean_filters, return_fields or [], limit, after
        )
        result = await self._cached_request(query)

        subjects_data = result.get("data", {}).get("Subjects", [])
        return [self._parse_subject_result(subject) for subject in subjects_data]

    async def search_trd_buy(
        self,
        announcement_number: str | None = None,
        name_keyword: str | None = None,
        org_bin: list[str] | None = None,
        trade_methods: list[TradeMethod] | None = None,
        start_date_from: str | None = None,
        start_date_to: str | None = None,
        limit: int = 50,
        after: str | None = None,
        return_fields: list[str] | None = None,
        **additional_filters,
    ) -> list[dict[str, Any]]:
        """
        Поиск объявлений о закупках

        Args:
            announcement_number: Номер объявления
            name_keyword: Ключевое слово в названии
            org_bin: БИН организатора
            trade_methods: Способы закупок
            start_date_from: Дата начала от
            start_date_to: Дата начала до
            limit: Максимальное количество результатов
            after: Курсор для пагинации
            return_fields: Поля для возврата
            **additional_filters: Дополнительные фильтры

        Returns:
            Список найденных объявлений
        """
        filters = TrdBuyFiltersInput()

        if announcement_number:
            filters.numberAnno = announcement_number
        if name_keyword:
            filters.nameRu = name_keyword
        if org_bin:
            filters.orgBin = org_bin
        if trade_methods:
            filters.refTradeMethodsId = [method.value for method in trade_methods]
        if start_date_from:
            filters.startDateFrom = start_date_from
        if start_date_to:
            filters.startDateTo = start_date_to
        if after:
            filters.after = after

        for key, value in additional_filters.items():
            if hasattr(filters, key):
                setattr(filters, key, value)

        clean_filters = self._clean_filters(filters)
        query = self._generate_query(
            "TrdBuy", clean_filters, return_fields or [], limit, after
        )
        result = await self._cached_request(query)

        return result.get("data", {}).get("TrdBuy", [])

    # === PARSING METHODS ===

    def _parse_lot_result(self, lot_data: dict[str, Any]) -> LotResult:
        """Парсинг данных лота"""
        ref_status = lot_data.get("RefLotsStatus", {})
        trd_buy = lot_data.get("TrdBuy", {})

        return LotResult(
            id=lot_data.get("id", ""),
            lotNumber=lot_data.get("lotNumber", ""),
            nameRu=lot_data.get("nameRu", ""),
            nameKz=lot_data.get("nameKz", ""),
            descriptionRu=lot_data.get("descriptionRu", ""),
            descriptionKz=lot_data.get("descriptionKz", ""),
            count=float(lot_data.get("count", 0)),
            amount=float(lot_data.get("amount", 0)),
            customerNameRu=lot_data.get("customerNameRu", ""),
            customerBin=lot_data.get("customerBin", ""),
            publishDate=lot_data.get("publishDate"),
            endDate=lot_data.get("endDate"),
            status=ref_status.get("nameRu", "") if ref_status else "",
            tradeMethod=(
                trd_buy.get("RefTradeMethods", {}).get("nameRu", "") if trd_buy else ""
            ),
            trdBuy=trd_buy if trd_buy else None,
        )

    def _parse_contract_result(self, contract_data: dict[str, Any]) -> ContractResult:
        """Парсинг данных контракта"""
        ref_status = contract_data.get("RefContractStatus", {})
        acts = contract_data.get("Acts", [])

        return ContractResult(
            id=contract_data.get("id", ""),
            contractNumber=contract_data.get("contractNumber", ""),
            contractNumberSys=contract_data.get("contractNumberSys", ""),
            supplierBiin=contract_data.get("supplierBiin", ""),
            supplierNameRu=contract_data.get("supplierNameRu", ""),
            customerBin=contract_data.get("customerBin", ""),
            customerNameRu=contract_data.get("customerNameRu", ""),
            contractSum=float(contract_data.get("contractSum", 0)),
            signDate=contract_data.get("signDate"),
            startDate=contract_data.get("startDate"),
            endDate=contract_data.get("endDate"),
            status=ref_status.get("nameRu", "") if ref_status else "",
            acts=acts if acts else None,
        )

    def _parse_subject_result(self, subject_data: dict[str, Any]) -> SubjectResult:
        """Парсинг данных участника"""
        ref_type = subject_data.get("RefSubjectType", {})

        return SubjectResult(
            id=subject_data.get("id", ""),
            bin=subject_data.get("bin", ""),
            nameRu=subject_data.get("nameRu", ""),
            nameKz=subject_data.get("nameKz", ""),
            addressRu=subject_data.get("addressRu", ""),
            subjectType=ref_type.get("nameRu", "") if ref_type else "",
            isActive=bool(subject_data.get("isActive", True)),
            regDate=subject_data.get("regDate"),
        )

    # === UTILITY METHODS ===

    async def get_stats(self) -> dict[str, Any]:
        """Получение статистики использования клиента"""
        return {
            "stats": self._stats.copy(),
            "cache_enabled": self.cache_enabled,
            "cache_size": len(self._cache._cache) if self._cache else 0,
            "active_subscriptions": len(self._subscriptions),
        }

    async def clear_cache(self):
        """Очистка кеша"""
        if self._cache:
            await self._cache.clear()

    def disable_cache(self):
        """Отключение кеширования"""
        self.cache_enabled = False

    def enable_cache(self):
        """Включение кеширования"""
        self.cache_enabled = True
