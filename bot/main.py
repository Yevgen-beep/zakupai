import asyncio
import logging
import os
from contextlib import asynccontextmanager
from functools import wraps

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.utils.markdown import hbold, hcode
from client import ZakupaiAPIClient
from db_simple import get_api_key, init_db, save_api_key

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Инициализация бота
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN или TELEGRAM_TOKEN не установлен")

# Валидация токена в dev режиме
if TOKEN.endswith("_") or "AAAA" in TOKEN:
    logger.warning(
        "⚠️  Используется dev/placeholder токен - бот будет работать в режиме заглушки"
    )
    DEV_MODE = True
else:
    DEV_MODE = False

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# API клиент
api_client = ZakupaiAPIClient(
    base_url=os.getenv("ZAKUPAI_API_URL", "http://localhost:8080"),
    api_key=os.getenv("ZAKUPAI_API_KEY", ""),
)


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
                    logger.info(f"Created new API key for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to create API key for user {user_id}: {e}")

        if not api_key:
            await message.answer(
                f"👋 Привет, {hbold(message.from_user.full_name)}!\n\n"
                "🔑 Для работы с ZakupAI нужен API ключ.\n"
                f"Отправь мне команду: {hcode('/key YOUR_API_KEY')}\n\n"
                "После этого используй команды:\n"
                f"• {hcode('/lot <id|url>')} - анализ лота\n"
                f"• {hcode('/help')} - справка"
            )
        else:
            await message.answer(
                f"👋 Привет, {hbold(message.from_user.full_name)}!\n\n"
                "✅ API ключ создан автоматически!\n\n"
                "🚀 Доступные команды:\n"
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
            "❌ Неверный формат команды.\n" f"Используй: {hcode('/key YOUR_API_KEY')}"
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
        logger.error(f"Ошибка сохранения API ключа для {user_id}: {e}")
        await message.answer("❌ Ошибка сохранения API ключа")


@dp.message(Command("lot"))
async def command_lot_handler(message: Message) -> None:
    """
    Обработчик команды /lot для анализа лота
    """
    user_id = message.from_user.id

    # Извлекаем ID лота
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "❌ Укажи ID или URL лота.\n" f"Пример: {hcode('/lot 12345')}"
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
            # Получаем API ключ
            api_key = await get_api_key(user_id)

            # Создаём клиент с пользовательским API ключом
            user_client = ZakupaiAPIClient(
                base_url=os.getenv("ZAKUPAI_API_URL", "http://localhost:8080"),
                api_key=api_key,
            )

            # Запускаем полный анализ лота
            result = await analyze_lot_pipeline(user_client, lot_id)

            # Форматируем и отправляем результат
            formatted_result = format_lot_analysis(result)
            await message.answer(formatted_result)

        except Exception as e:
            logger.error(f"Ошибка анализа лота {lot_id} для {user_id}: {e}")
            await message.answer("❌ Ошибка анализа лота")


@dp.message(Command("help"))
async def command_help_handler(message: Message) -> None:
    """
    Обработчик команды /help
    """
    help_text = (
        "🤖 ZakupAI Telegram Bot\n\n"
        "📋 Доступные команды:\n"
        f"• {hcode('/start')} - начать работу\n"
        f"• {hcode('/key <api_key>')} - установить API ключ\n"
        f"• {hcode('/lot <id|url>')} - анализ лота\n"
        f"• {hcode('/stats')} - ваша статистика\n"
        f"• {hcode('/help')} - эта справка\n\n"
        "🔍 Пример анализа лота:\n"
        f"{hcode('/lot 12345')}\n"
        f"{hcode('/lot https://goszakup.gov.kz/ru/announce/index/12345')}\n\n"
        "💰 Тарифы:\n"
        "• Free: 100 запросов/день, 20/час\n"
        "• Premium: 5000 запросов/день, 500/час\n\n"
        "🔧 Поддержка: @zakupai_support"
    )
    await message.answer(help_text)


# Пример новой команды - показывает универсальность системы
@dp.message(Command("stats"))
async def command_stats_handler(message: Message) -> None:
    """
    Обработчик команды /stats - статистика пользователя
    """
    user_id = message.from_user.id

    if DEV_MODE:
        await message.answer(
            "📊 Статистика (Dev режим):\n\n"
            "🔑 План: Free\n"
            "📈 Использовано сегодня: 5\n"
            "📊 Всего запросов: 25\n"
            "⏰ Осталось сегодня: 95\n"
            "🕐 Осталось в час: 15"
        )
    else:
        try:
            import aiohttp

            # Простой запрос к Billing Service для статистики
            billing_url = f"http://billing-service:7004/billing/stats/{user_id}"
            headers = {"Content-Type": "application/json"}

            async with aiohttp.ClientSession() as session:
                async with session.get(billing_url, headers=headers) as response:
                    if response.status == 200:
                        stats = await response.json()
                        stats_text = (
                            f"📊 Ваша статистика:\n\n"
                            f"🔑 План: {stats.get('plan', 'N/A')}\n"
                            f"📈 Использовано сегодня: {stats.get('usage', {}).get('today_requests', 0)}\n"
                            f"📊 Всего запросов: {stats.get('usage', {}).get('total_requests', 0)}\n"
                            f"⏰ Осталось сегодня: {stats.get('limits', {}).get('daily_remaining', 0)}\n"
                            f"🕐 Осталось в час: {stats.get('limits', {}).get('hourly_remaining', 0)}"
                        )
                        await message.answer(stats_text)
                    else:
                        await message.answer("❌ Не удалось получить статистику")

        except Exception as e:
            logger.error(f"Error getting stats for user {user_id}: {e}")
            await message.answer("❌ Ошибка получения статистики")


def get_command_endpoint(message_text: str) -> str:
    """
    Извлекает имя команды для использования как endpoint в Billing Service
    """
    if message_text.startswith("/"):
        command = message_text.split()[0][1:]  # Убираем '/' и берем первое слово
        return command
    return "unknown"


def validate_and_log(require_key: bool = True):
    """
    Декоратор для валидации API ключа и логирования использования
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            user_id = message.from_user.id
            endpoint = get_command_endpoint(message.text)

            # Получаем API ключ если нужен или есть
            api_key = (
                await get_api_key(user_id) if require_key or not DEV_MODE else None
            )

            if require_key:
                # Проверяем наличие API ключа
                if not api_key:
                    await message.answer(
                        "🔑 Сначала установи API ключ:\n"
                        f"{hcode('/key YOUR_API_KEY')}"
                    )
                    return

                # Валидируем ключ через Billing Service (кроме dev режима)
                if not DEV_MODE:
                    if not await api_client.validate_key(api_key, endpoint):
                        await message.answer(
                            "❌ API ключ недействителен или превышен лимит.\n"
                            "Проверьте ключ или попробуйте позже."
                        )
                        return

            # Выполняем основную функцию
            result = await func(message, *args, **kwargs)

            # Логируем использование (если есть ключ и не dev режим)
            if not DEV_MODE and api_key:
                try:
                    await api_client.log_usage(api_key, endpoint)
                    logger.debug(
                        f"Logged usage for endpoint '{endpoint}' by user {user_id}"
                    )
                except Exception as e:
                    logger.error(f"Failed to log usage for endpoint '{endpoint}': {e}")

            return result

        return wrapper

    return decorator


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


@asynccontextmanager
async def lifespan_context():
    """
    Контекст жизненного цикла приложения
    """
    # Инициализация БД
    await init_db()
    logger.info("База данных инициализирована")

    yield

    logger.info("Завершение работы бота")


async def main() -> None:
    """
    Основная функция запуска бота
    """
    async with lifespan_context():
        logger.info("Запуск ZakupAI Telegram Bot")
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
