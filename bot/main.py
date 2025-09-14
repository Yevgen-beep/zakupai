import asyncio
import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from functools import wraps

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.utils.markdown import hbold, hcode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from client import ZakupaiAPIClient, get_command_endpoint
from config import config
from db_simple import get_api_key, init_db, save_api_key
from error_handler import ErrorHandlingMiddleware

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Инициализация бота из конфигурации
TOKEN = config.telegram.bot_token

# Валидация токена в dev режиме
if TOKEN.endswith("_") or "AAAA" in TOKEN:
    logger.warning(
        "⚠️  Используется dev/placeholder токен - бот будет работать в режиме заглушки"
    )
    DEV_MODE = True
else:
    DEV_MODE = config.security.environment == "development"

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Подключаем middleware для обработки ошибок
dp.message.middleware(ErrorHandlingMiddleware())

# API клиент из конфигурации
api_client = ZakupaiAPIClient()

# Хранилище состояний поиска для пагинации
user_search_sessions = {}

# Режим работы: webhook или polling
USE_WEBHOOK = bool(
    config.telegram.webhook_url and config.security.environment != "development"
)


# Rate limiting система
class RateLimiter:
    """Простая система rate limiting для защиты от спама"""

    def __init__(self, max_requests: int = None, window_seconds: int = 60):
        self.max_requests = max_requests or config.security.max_requests_per_minute
        self.window_seconds = window_seconds
        self.requests: dict[int, list[float]] = defaultdict(list)

    def is_allowed(self, user_id: int) -> bool:
        """Проверяет, разрешен ли запрос от пользователя"""
        now = time.time()
        user_requests = self.requests[user_id]

        # Удаляем старые запросы
        self.requests[user_id] = [
            req_time
            for req_time in user_requests
            if now - req_time < self.window_seconds
        ]

        if len(self.requests[user_id]) >= self.max_requests:
            return False

        self.requests[user_id].append(now)
        return True

    def get_remaining_requests(self, user_id: int) -> int:
        """Возвращает количество оставшихся запросов"""
        return max(0, self.max_requests - len(self.requests.get(user_id, [])))


# Специальный rate limiter для /search (1 запрос/секунда)
class SearchRateLimiter:
    """Rate limiter для команды /search (1 запрос в секунду на пользователя)"""

    def __init__(self):
        self.last_request: dict[int, float] = {}

    def is_allowed(self, user_id: int) -> bool:
        """Проверяет, разрешен ли search запрос от пользователя"""
        now = time.time()
        last_time = self.last_request.get(user_id, 0)

        if now - last_time < 1.0:  # 1 секунда между запросами
            return False

        self.last_request[user_id] = now
        return True

    def get_next_allowed_time(self, user_id: int) -> float:
        """Возвращает время когда можно сделать следующий запрос"""
        last_time = self.last_request.get(user_id, 0)
        return max(0, 1.0 - (time.time() - last_time))


# Глобальные rate limiters
rate_limiter = RateLimiter()
search_rate_limiter = SearchRateLimiter()


# Безопасный декоратор для команд бота с rate limiting
def validate_and_log_bot(require_key: bool = True):
    """
    Декоратор для валидации API ключа, rate limiting и безопасного логирования
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            user_id = message.from_user.id
            username = message.from_user.username or "unknown"
            endpoint = get_command_endpoint(message.text or "")

            # Rate limiting проверка
            if not rate_limiter.is_allowed(user_id):
                remaining = rate_limiter.get_remaining_requests(user_id)
                await message.answer(
                    f"⏱️ Превышен лимит запросов ({config.security.max_requests_per_minute}/мин).\n"
                    f"Попробуйте через минуту. Осталось запросов: {remaining}"
                )
                logger.warning(
                    f"Rate limit exceeded for user {user_id} (@{username}) on endpoint '{endpoint}'"
                )
                return

            # Специальная проверка для /search
            if endpoint == "search" and not search_rate_limiter.is_allowed(user_id):
                wait_time = search_rate_limiter.get_next_allowed_time(user_id)
                await message.answer(
                    f"⏱️ Поиск доступен раз в секунду.\n"
                    f"Попробуйте через {wait_time:.1f} секунд."
                )
                logger.warning(
                    f"Search rate limit exceeded for user {user_id} (@{username})"
                )
                return

            # Получаем API ключ если нужен
            api_key = (
                await get_api_key(user_id) if require_key or not DEV_MODE else None
            )

            if require_key and not DEV_MODE:
                # Проверяем наличие API ключа
                if not api_key:
                    await message.answer(
                        f"🔑 Сначала установи API ключ:\n{hcode('/key YOUR_API_KEY')}"
                    )
                    logger.info(
                        f"User {user_id} (@{username}) attempted to use {endpoint} without API key"
                    )
                    return

                # Валидируем ключ через Billing Service
                if not await api_client.validate_key(api_key, endpoint):
                    await message.answer(
                        "❌ API ключ недействителен или превышен лимит.\n"
                        "Проверьте ключ или попробуйте позже."
                    )
                    logger.warning(
                        f"Invalid/expired API key used by user {user_id} (@{username}) for endpoint '{endpoint}'"
                    )
                    return

            # Безопасное логирование начала обработки команды
            logger.info(
                f"Processing {endpoint} command for user {user_id} (@{username})"
            )

            # Выполняем основную функцию
            try:
                result = await func(message, *args, **kwargs)
                logger.debug(f"Successfully processed {endpoint} for user {user_id}")
            except Exception as e:
                logger.error(
                    f"Error processing {endpoint} for user {user_id}: {type(e).__name__}"
                )
                raise

            # Логируем использование (если есть ключ и не dev режим)
            if not DEV_MODE and api_key:
                try:
                    await api_client.log_usage(api_key, endpoint)
                    logger.debug(
                        f"Usage logged for endpoint '{endpoint}' by user {user_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to log usage for endpoint '{endpoint}': {type(e).__name__}"
                    )

            return result

        return wrapper

    return decorator


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    Обработчик команды /start
    """
    user_id = message.from_user.id

    # Проверяем наличие API ключа
    api_key = await get_api_key(user_id)

    if not api_key:
        # Создаем новый API ключ через Billing Service
        if not DEV_MODE:
            try:
                new_api_key = await api_client.create_billing_key(
                    tg_id=user_id,
                    email=None,  # email опционально
                )
                if new_api_key:
                    await save_api_key(user_id, new_api_key)
                    api_key = new_api_key
                    logger.info(f"Successfully created new API key for user {user_id}")
            except Exception as e:
                logger.error(
                    f"Failed to create API key for user {user_id}: {type(e).__name__}"
                )

        if not api_key:
            await message.answer(
                f"👋 Привет, {hbold(message.from_user.full_name)}!\n\n"
                "🔑 Для работы с ZakupAI нужен API ключ.\n"
                f"Отправь мне команду: {hcode('/key YOUR_API_KEY')}\n\n"
                "После этого используй команды:\n"
                f"• {hcode('/search')} &lt;запрос&gt; - поиск лотов\n"
                f"• {hcode('/lot <id|url>')} - анализ лота\n"
                f"• {hcode('/help')} - справка"
            )
        else:
            await message.answer(
                f"👋 Привет, {hbold(message.from_user.full_name)}!\n\n"
                "✅ API ключ создан автоматически!\n\n"
                "🚀 Доступные команды:\n"
                f"• {hcode('/search')} &lt;запрос&gt; - поиск лотов\n"
                f"• {hcode('/lot <id|url>')} - анализ лота\n"
                f"• {hcode('/help')} - справка"
            )
    else:
        # Валидируем существующий ключ
        if not DEV_MODE and not await api_client.validate_key(api_key, "start"):
            await message.answer(
                f"⚠️ Ваш API ключ недействителен или превышен лимит.\n\n"
                f"Обновите ключ: {hcode('/key YOUR_NEW_API_KEY')}"
            )
        else:
            await message.answer(
                f"✅ Добро пожаловать обратно, {hbold(message.from_user.full_name)}!\n\n"
                "🚀 Доступные команды:\n"
                f"• {hcode('/search')} &lt;запрос&gt; - поиск лотов\n"
                f"• {hcode('/lot <id|url>')} - анализ лота\n"
                f"• {hcode('/key <новый_ключ>')} - обновить API ключ\n"
                f"• {hcode('/help')} - справка"
            )


@dp.message(Command("key"))
async def command_key_handler(message: Message) -> None:
    """
    Обработчик команды /key для сохранения API ключа
    """
    user_id = message.from_user.id

    # Извлекаем API ключ из команды
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            f"❌ Неверный формат команды.\nИспользуй: {hcode('/key YOUR_API_KEY')}"
        )
        return

    api_key = args[1].strip()

    if len(api_key) < 10:  # Базовая валидация
        await message.answer("❌ API ключ слишком короткий")
        return

    try:
        if DEV_MODE:
            await save_api_key(user_id, api_key)
            await message.answer("✅ API ключ сохранён (dev режим)")
        else:
            # Проверяем валидность ключа через Billing Service
            if await api_client.validate_key(api_key, "key"):
                await save_api_key(user_id, api_key)
                await message.answer("✅ API ключ сохранён и проверен!")
                # Логируем использование для команды key
                await api_client.log_usage(api_key, "key")
            else:
                await message.answer(
                    "❌ API ключ недействителен или превышен лимит.\n"
                    "Проверьте ключ или попробуйте позже."
                )

    except Exception as e:
        logger.error(f"Failed to save API key for user {user_id}: {type(e).__name__}")
        await message.answer("❌ Ошибка сохранения API ключа")


@dp.message(Command("search"))
@validate_and_log_bot(require_key=True)
async def command_search_handler(message: Message) -> None:
    """
    Обработчик команды /search для поиска лотов через новую поисковую систему
    """
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"

    logger.info(f"Processing search command for user {user_id} (@{username})")

    # Извлекаем поисковый запрос
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "🔍 Использование: /search &lt;ключевые слова&gt;\n\n"
            "Примеры:\n"
            f"• {hcode('/search ЛАК')}\n"
            f"• {hcode('/search компьютеры')}\n"
            f"• {hcode('/search строительство дорог')}\n"
            f"• {hcode('/search медицинское оборудование')}"
        )
        return

    raw_query = args[1].strip()

    # Валидация запроса
    if len(raw_query) < 2:
        await message.answer("❌ Поисковый запрос слишком короткий (минимум 2 символа)")
        return

    if len(raw_query) > 200:
        await message.answer(
            "❌ Поисковый запрос слишком длинный (максимум 200 символов)"
        )
        return

    # Показываем индикатор поиска
    loading_message = await message.answer(
        "🔍 Ищу лоты... Это может занять несколько секунд"
    )

    try:
        # Используем новую логику поиска с нормализацией и n8n fallback
        from services_v2 import search_lots_for_telegram_v2

        results_text = await search_lots_for_telegram_v2(
            raw_query, limit=10, show_source=True, user_id=user_id
        )

        # Удаляем индикатор загрузки
        await loading_message.delete()

        # Отправляем результаты
        await message.answer(
            results_text, parse_mode="HTML", disable_web_page_preview=True
        )

        # Сохраняем состояние поиска для пагинации
        user_search_sessions[user_id] = {
            "query": raw_query,
            "offset": 10,  # Следующая страница начинается с 10-го элемента
            "limit": 10,
            "timestamp": message.date.timestamp(),
        }

        logger.info(
            f"Search completed for user {user_id} (@{username}) with query '{raw_query}'"
        )

    except Exception as e:
        await loading_message.delete()
        await message.answer(f"⚠️ Ошибка поиска: {type(e).__name__}")
        logger.error(
            f"Error searching for '{raw_query}' by user {user_id}: {type(e).__name__}"
        )


@dp.message(Command("search_continue"))
@validate_and_log_bot(require_key=True)
async def command_search_continue_handler(message: Message) -> None:
    """
    Обработчик команды /search_continue для продолжения поиска лотов
    """
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"

    logger.info(f"Processing search_continue command for user {user_id} (@{username})")

    # Проверяем наличие сохраненного поиска для пользователя
    if user_id not in user_search_sessions:
        await message.answer(
            "❌ Нет активного поиска для продолжения.\n\n"
            "Сначала выполните поиск с помощью команды /search"
        )
        return

    search_session = user_search_sessions[user_id]

    # Проверяем, не истек ли поиск (15 минут)
    import time

    if time.time() - search_session["timestamp"] > 900:  # 15 минут
        del user_search_sessions[user_id]
        await message.answer(
            "⏰ Сессия поиска истекла.\n\n"
            "Выполните новый поиск с помощью команды /search"
        )
        return

    # Показываем индикатор поиска
    loading_message = await message.answer("🔍 Загружаю следующие результаты...")

    try:
        # Используем сохраненные параметры поиска
        query = search_session["query"]
        offset = search_session["offset"]
        limit = search_session["limit"]

        # Выполняем поиск со смещением
        from services_v2 import search_lots_for_telegram_v2

        results_text = await search_lots_for_telegram_v2(
            query, limit=limit, offset=offset, show_source=True, user_id=user_id
        )

        # Удаляем индикатор загрузки
        await loading_message.delete()

        # Отправляем результаты
        await message.answer(
            results_text, parse_mode="HTML", disable_web_page_preview=True
        )

        # Обновляем смещение для следующей страницы
        search_session["offset"] += limit
        search_session["timestamp"] = message.date.timestamp()

        logger.info(
            f"Search continue completed for user {user_id} (@{username}) with query '{query}', offset {offset}"
        )

    except Exception as e:
        await loading_message.delete()
        await message.answer(f"⚠️ Ошибка продолжения поиска: {type(e).__name__}")
        logger.error(f"Search continue failed for user {user_id}: {e}")


@dp.message(Command("lot"))
@validate_and_log_bot(require_key=True)
async def command_lot_handler(message: Message) -> None:
    """
    Обработчик команды /lot для анализа лота
    """
    user_id = message.from_user.id

    # Извлекаем ID лота
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            f"❌ Укажи ID или URL лота.\nПример: {hcode('/lot 12345')}"
        )
        return

    lot_input = args[1].strip()

    # Извлекаем ID из URL если нужно
    lot_id = extract_lot_id(lot_input)
    if not lot_id:
        await message.answer("❌ Не удалось извлечь ID лота")
        return

    if DEV_MODE:
        await message.answer("🔄 Dev режим: эмуляция анализа лота...")
        # Эмуляция результата в dev режиме
        dev_result = {
            "lot_id": lot_id,
            "tldr": {
                "title": f"Тестовый лот {lot_id}",
                "price": "1000000",
                "customer": "Тестовый заказчик",
            },
            "risk": {"score": 0.3, "explanation": "Средний уровень риска (dev)"},
            "finance": {
                "amount_without_vat": "892857",
                "vat_amount": "107143",
                "total_with_vat": "1000000",
            },
        }
        formatted_result = format_lot_analysis(dev_result)
        await message.answer(formatted_result)
    else:
        await message.answer("🔄 Анализирую лот...")

        try:
            # Получаем API ключ (уже проверен декоратором)
            api_key = await get_api_key(user_id)

            # Создаём клиент с пользовательским API ключом
            user_client = ZakupaiAPIClient(
                base_url=config.api.zakupai_base_url,
                api_key=api_key,
            )

            # Запускаем полный анализ лота
            result = await analyze_lot_pipeline(user_client, lot_id)

            # Форматируем и отправляем результат
            formatted_result = format_lot_analysis(result)
            await message.answer(formatted_result)

        except Exception as e:
            logger.error(
                f"Failed to analyze lot {lot_id} for user {user_id}: {type(e).__name__}"
            )
            await message.answer("❌ Ошибка анализа лота")


@dp.message(Command("help"))
@validate_and_log_bot(require_key=False)
async def command_help_handler(message: Message) -> None:
    """
    Обработчик команды /help
    """
    help_text = (
        "🤖 ZakupAI Telegram Bot\n\n"
        "📋 Доступные команды:\n"
        f"• {hcode('/start')} - начать работу\n"
        f"• {hcode('/key <api_key>')} - установить API ключ\n"
        f"• {hcode('/search')} &lt;запрос&gt; - поиск лотов по ключевым словам\n"
        f"• {hcode('/lot <id|url>')} - анализ лота\n"
        f"• {hcode('/help')} - эта справка\n\n"
        "🔍 Примеры поиска:\n"
        f"{hcode('/search компьютеры')}\n"
        f"{hcode('/search строительство дорог')}\n\n"
        "📊 Пример анализа лота:\n"
        f"{hcode('/lot 12345')}\n"
        f"{hcode('/lot https://goszakup.gov.kz/ru/announce/index/12345')}\n\n"
        "💰 Тарифы:\n"
        "• Free: 100 запросов/день, 20/час\n"
        "• Premium: 5000 запросов/день, 500/час\n\n"
        "⚡ Лимиты:\n"
        "• Поиск: 1 запрос в секунду\n"
        "• Остальные команды: 10 запросов в минуту\n\n"
        "🔧 Поддержка: @zakupai_support"
    )
    await message.answer(help_text)


def extract_lot_id(lot_input: str) -> str:
    """
    Извлекает ID лота из строки (ID или URL)
    """
    import re

    # Если это уже число
    if lot_input.isdigit():
        return lot_input

    # Извлекаем из URL
    url_patterns = [
        r"/announce/index/(\d+)",
        r"/lot/(\d+)",
        r"lot_id=(\d+)",
        r"id=(\d+)",
    ]

    for pattern in url_patterns:
        match = re.search(pattern, lot_input)
        if match:
            return match.group(1)

    return ""


async def analyze_lot_pipeline(client: ZakupaiAPIClient, lot_id: str) -> dict:
    """
    Полный пайплайн анализа лота
    """
    result = {
        "lot_id": lot_id,
        "tldr": None,
        "risk": None,
        "finance": None,
        "error": None,
    }

    try:
        # 1. TL;DR через doc-service
        tldr_data = await client.get_tldr(lot_id)
        result["tldr"] = tldr_data

        # 2. Риск-анализ
        risk_data = await client.get_risk_score(lot_id)
        result["risk"] = risk_data

        # 3. Финансовые расчёты (пример с НДС)
        if tldr_data and "price" in tldr_data:
            vat_data = await client.calculate_vat(tldr_data["price"])
            result["finance"] = vat_data

    except Exception as e:
        result["error"] = str(e)

    return result


def format_lot_analysis(result: dict) -> str:
    """
    Форматирует результат анализа лота для отправки
    """
    lot_id = result["lot_id"]

    if result.get("error"):
        return f"❌ Ошибка анализа лота {lot_id}: {result['error']}"

    output = [f"📊 Анализ лота {hbold(lot_id)}"]

    # TL;DR
    if result.get("tldr"):
        tldr = result["tldr"]
        output.append(f"\n📝 {hbold('Краткое описание:')}")
        output.append(f"• Название: {tldr.get('title', 'N/A')}")
        output.append(f"• Цена: {tldr.get('price', 'N/A')} тг")
        output.append(f"• Заказчик: {tldr.get('customer', 'N/A')}")

    # Риск-анализ
    if result.get("risk"):
        risk = result["risk"]
        risk_score = risk.get("score", 0)
        risk_level = (
            "🟢 Низкий"
            if risk_score < 0.3
            else "🟡 Средний" if risk_score < 0.7 else "🔴 Высокий"
        )

        output.append(f"\n⚠️ {hbold('Риск-анализ:')}")
        output.append(f"• Уровень риска: {risk_level} ({risk_score:.2f})")
        if "explanation" in risk:
            output.append(f"• Причины: {risk['explanation']}")

    # Финансовые расчёты
    if result.get("finance"):
        finance = result["finance"]
        output.append(f"\n💰 {hbold('Финансы:')}")
        output.append(f"• Сумма без НДС: {finance.get('amount_without_vat', 'N/A')} тг")
        output.append(f"• НДС (12%): {finance.get('vat_amount', 'N/A')} тг")
        output.append(f"• Итого с НДС: {finance.get('total_with_vat', 'N/A')} тг")

    return "\n".join(output)


async def setup_webhook():
    """Настройка webhook для production режима"""
    if not USE_WEBHOOK:
        return

    webhook_url = config.telegram.webhook_url
    webhook_secret = config.telegram.webhook_secret

    logger.info(f"Setting webhook to: {webhook_url}")

    # Удаляем существующий webhook
    await bot.delete_webhook(drop_pending_updates=True)

    # Устанавливаем новый webhook
    await bot.set_webhook(
        url=webhook_url, secret_token=webhook_secret, drop_pending_updates=True
    )

    # Проверяем webhook
    webhook_info = await bot.get_webhook_info()
    logger.info(f"Webhook info: {webhook_info}")


@asynccontextmanager
async def lifespan_context():
    """
    Контекст жизненного цикла приложения
    """
    # Инициализация БД
    await init_db()
    logger.info("База данных инициализирована")

    # Настройка webhook если нужно
    if USE_WEBHOOK:
        await setup_webhook()

    yield

    # Очистка при завершении
    if USE_WEBHOOK:
        await bot.delete_webhook(drop_pending_updates=False)

    logger.info("Завершение работы бота")


async def webhook_main() -> None:
    """
    Запуск в webhook режиме
    """
    async with lifespan_context():
        app = web.Application()

        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            secret_token=config.telegram.webhook_secret,
        )
        webhook_requests_handler.register(app, path="/webhook/telegram")

        # Health check endpoint
        async def health_check(request):
            return web.Response(text="OK", status=200)

        app.router.add_get("/health", health_check)

        # Setup application and start server
        setup_application(app, dp, bot=bot)

        logger.info("🚀 ZakupAI Telegram Bot запущен в webhook режиме")

        # Запуск сервера
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=8000)  # nosec B104
        await site.start()

        # Бесконечный цикл
        try:
            await asyncio.Future()  # run forever
        except KeyboardInterrupt:
            logger.info("Получен сигнал завершения")
        finally:
            await runner.cleanup()


async def polling_main() -> None:
    """
    Запуск в polling режиме
    """
    async with lifespan_context():
        logger.info("🚀 ZakupAI Telegram Bot запущен в polling режиме")
        await dp.start_polling(bot)


async def main() -> None:
    """
    Основная функция запуска бота
    """
    if USE_WEBHOOK:
        logger.info(f"Режим: Webhook ({config.telegram.webhook_url})")
        await webhook_main()
    else:
        logger.info("Режим: Polling (development)")
        await polling_main()


if __name__ == "__main__":
    asyncio.run(main())
