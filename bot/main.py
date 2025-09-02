import asyncio
import logging
import os
from contextlib import asynccontextmanager

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
        # Сохраняем API ключ
        await save_api_key(user_id, api_key)

        if DEV_MODE:
            await message.answer("✅ API ключ сохранён (dev режим)")
        else:
            # Проверяем валидность ключа
            test_client = ZakupaiAPIClient(
                base_url=os.getenv("ZAKUPAI_API_URL", "http://localhost:8080"),
                api_key=api_key,
            )

            health_check = await test_client.health_check()
            if health_check and health_check.get("status") == "ok":
                await message.answer("✅ API ключ сохранён и проверен!")
            else:
                await message.answer("⚠️ API ключ сохранён, но не прошёл проверку")

    except Exception as e:
        logger.error(f"Ошибка сохранения API ключа для {user_id}: {e}")
        await message.answer("❌ Ошибка сохранения API ключа")


@dp.message(Command("lot"))
async def command_lot_handler(message: Message) -> None:
    """
    Обработчик команды /lot для анализа лота
    """
    user_id = message.from_user.id

    # Проверяем API ключ
    api_key = await get_api_key(user_id)
    if not api_key:
        await message.answer(
            "🔑 Сначала установи API ключ:\n" f"{hcode('/key YOUR_API_KEY')}"
        )
        return

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
        f"• {hcode('/help')} - эта справка\n\n"
        "🔍 Пример анализа лота:\n"
        f"{hcode('/lot 12345')}\n"
        f"{hcode('/lot https://goszakup.gov.kz/ru/announce/index/12345')}\n\n"
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
