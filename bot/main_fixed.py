"""
ZakupAI Telegram Bot - исправленная версия с поддержкой webhook/polling
"""

import asyncio
import json
import logging
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiohttp
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, WebhookInfo
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
from config import config
from db_simple import get_api_key, init_db, save_api_key
from error_handler import ErrorHandlingMiddleware

# Настройка логирования
log_file_path = Path(tempfile.gettempdir()) / "zakupai_bot.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file_path, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# Инициализация бота
TOKEN = config.telegram.bot_token
USE_WEBHOOK = config.security.environment in ["staging", "production"]
WEBHOOK_URL = config.telegram.webhook_url or ""
WEBHOOK_SECRET = config.telegram.webhook_secret or ""

logger.info(f"Bot starting in {'WEBHOOK' if USE_WEBHOOK else 'POLLING'} mode")
logger.info(f"Environment: {config.security.environment}")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()

# Подключаем middleware и router
dp.message.middleware(ErrorHandlingMiddleware())
dp.include_router(router)

# API клиенты
billing_service_url = config.api.billing_service_url
zakupai_api_url = config.api.zakupai_base_url
n8n_webhook_url = config.api.n8n_webhook_url


async def setup_webhook():
    """Настройка webhook для бота"""
    if not USE_WEBHOOK or not WEBHOOK_URL:
        logger.info("Webhook setup skipped (using polling mode)")
        return False

    try:
        # Получаем текущую информацию о webhook
        webhook_info: WebhookInfo = await bot.get_webhook_info()
        logger.info(f"Current webhook: {webhook_info.url}")

        # Устанавливаем webhook если он не установлен или неверный
        if webhook_info.url != WEBHOOK_URL:
            logger.info(f"Setting webhook to: {WEBHOOK_URL}")

            success = await bot.set_webhook(
                url=WEBHOOK_URL,
                secret_token=WEBHOOK_SECRET,
                allowed_updates=["message"],
                drop_pending_updates=True,
            )

            if success:
                logger.info("✅ Webhook установлен успешно")
                return True
            else:
                logger.error("❌ Ошибка установки webhook")
                return False
        else:
            logger.info("✅ Webhook уже установлен корректно")
            return True

    except Exception as e:
        logger.error(f"Ошибка настройки webhook: {type(e).__name__}: {e}")
        return False


async def remove_webhook():
    """Удаление webhook (для polling режима)"""
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook удален (переход в polling режим)")
    except Exception as e:
        logger.error(f"Ошибка удаления webhook: {e}")


# === BILLING SERVICE INTEGRATION ===


async def create_billing_key(tg_id: int) -> str:
    """Создание API ключа через Billing Service"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{billing_service_url}/billing/create_key",
                json={"tg_id": tg_id, "email": None},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    api_key = data.get("api_key", "")
                    if api_key:
                        logger.info(f"✅ Created API key for user {tg_id}")
                        return api_key
                    else:
                        logger.warning(f"❌ Empty API key returned for user {tg_id}")
                        return ""
                else:
                    logger.error(
                        f"❌ Billing service error {response.status} for user {tg_id}"
                    )
                    return ""
    except Exception as e:
        logger.error(f"❌ Error creating API key for user {tg_id}: {type(e).__name__}")
        return ""


async def validate_billing_key(api_key: str, endpoint: str) -> dict[str, Any]:
    """Валидация API ключа через Billing Service"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{billing_service_url}/billing/validate_key",
                json={"api_key": api_key, "endpoint": endpoint},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    is_valid = data.get("valid", False)
                    logger.info(
                        f"🔑 Key validation for {endpoint}: {'✅ valid' if is_valid else '❌ invalid'}"
                    )
                    return data
                elif response.status == 429:
                    logger.warning(f"⏱️ Rate limit exceeded for {endpoint}")
                    return {"valid": False, "error": "Rate limit exceeded"}
                else:
                    logger.error(f"❌ Billing validation error {response.status}")
                    return {"valid": False, "error": "Service error"}
    except Exception as e:
        logger.error(f"❌ Error validating key: {type(e).__name__}")
        return {"valid": False, "error": "Network error"}


async def log_usage(api_key: str, endpoint: str) -> bool:
    """Логирование использования API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{billing_service_url}/billing/usage",
                json={"api_key": api_key, "endpoint": endpoint, "requests": 1},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                if response.status == 200:
                    logger.debug(f"📝 Usage logged for {endpoint}")
                    return True
                else:
                    logger.warning(f"⚠️ Usage logging failed: {response.status}")
                    return False
    except Exception as e:
        logger.error(f"❌ Error logging usage: {type(e).__name__}")
        return False


# === BOT COMMAND HANDLERS ===


@router.message(CommandStart())
async def start_command(message: Message):
    """Команда /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"

    logger.info(f"📱 /start from user {user_id} (@{username})")

    try:
        # Проверяем существующий API ключ
        api_key = await get_api_key(user_id)

        if not api_key:
            # Создаем новый ключ через Billing Service
            logger.info(f"🔑 Creating new API key for user {user_id}")
            api_key = await create_billing_key(user_id)

            if api_key:
                await save_api_key(user_id, api_key)
                logger.info(f"✅ API key saved for user {user_id}")

                await message.answer(
                    f"👋 Привет, {message.from_user.full_name}!\n\n"
                    "✅ API ключ создан автоматически!\n\n"
                    "🚀 Доступные команды:\n"
                    "• /search <запрос> - поиск лотов\n"
                    "• /lot <ID> - анализ лота\n"
                    "• /help - справка"
                )
            else:
                await message.answer(
                    f"👋 Привет, {message.from_user.full_name}!\n\n"
                    "❌ Не удалось создать API ключ автоматически.\n"
                    "Используйте /key <ваш_ключ> для ручной привязки."
                )
        else:
            await message.answer(
                f"👋 Добро пожаловать обратно, {message.from_user.full_name}!\n\n"
                "🚀 Доступные команды:\n"
                "• /search <запрос> - поиск лотов\n"
                "• /lot <ID> - анализ лота\n"
                "• /help - справка"
            )

    except Exception as e:
        logger.error(
            f"❌ Error in start command for user {user_id}: {type(e).__name__}"
        )
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(Command("key"))
async def key_command(message: Message):
    """Команда /key - привязка API ключа"""
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"

    logger.info(f"🔑 /key from user {user_id} (@{username})")

    # Извлекаем ключ из команды
    args = message.text.split(" ", 1)
    if len(args) < 2:
        await message.answer(
            "🔑 Использование: /key <ваш_api_ключ>\n"
            "Пример: /key 12345678-1234-1234-1234-123456789abc"
        )
        return

    api_key = args[1].strip()

    if len(api_key) < 10:
        await message.answer("❌ API ключ слишком короткий")
        return

    try:
        # Валидируем ключ через Billing Service
        validation = await validate_billing_key(api_key, "key")

        if validation.get("valid", False):
            await save_api_key(user_id, api_key)
            await log_usage(api_key, "key")

            plan = validation.get("plan", "free")
            await message.answer(
                f"✅ API ключ успешно привязан!\n"
                f"📋 План: {plan.upper()}\n"
                "🚀 Теперь вы можете использовать все команды"
            )
            logger.info(
                f"✅ API key validated and saved for user {user_id} (plan: {plan})"
            )
        else:
            error_msg = validation.get("error", "Неверный ключ")
            await message.answer(f"❌ {error_msg}")
            logger.warning(f"❌ Invalid API key from user {user_id}")

    except Exception as e:
        logger.error(f"❌ Error in key command for user {user_id}: {type(e).__name__}")
        await message.answer("❌ Ошибка проверки ключа")


@router.message(Command("search"))
async def search_command(message: Message):
    """Команда /search - поиск через n8n"""
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"

    logger.info(f"🔍 /search from user {user_id} (@{username})")

    # Проверяем API ключ
    api_key = await get_api_key(user_id)
    if not api_key:
        await message.answer(
            "🔑 API ключ не найден. Используйте /key <ваш_ключ> или /start"
        )
        return

    # Валидируем ключ
    validation = await validate_billing_key(api_key, "search")
    if not validation.get("valid", False):
        error_msg = validation.get("error", "Неверный ключ")
        await message.answer(f"❌ {error_msg}")
        return

    # Извлекаем поисковый запрос
    args = message.text.split(" ", 1)
    if len(args) < 2:
        await message.answer(
            "🔍 Использование: /search <ключевые слова>\n\n"
            "Примеры:\n"
            "• /search компьютеры\n"
            "• /search строительство дорог"
        )
        return

    query = args[1].strip()

    if len(query) < 2:
        await message.answer("❌ Поисковый запрос слишком короткий")
        return

    try:
        # Отправляем запрос в n8n
        logger.info(f"🔍 Searching for '{query}' via n8n for user {user_id}")

        loading_msg = await message.answer("🔍 Ищу лоты...")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                n8n_webhook_url,
                json={"query": query},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    lots = data.get("lots", []) if isinstance(data, dict) else data

                    await loading_msg.delete()

                    if not lots:
                        await message.answer("❌ Лоты не найдены по вашему запросу")
                        return

                    # Форматируем результаты (до 5 лотов)
                    result_lines = [f"🔍 <b>Найдено лотов по запросу:</b> {query}\n"]

                    for i, lot in enumerate(lots[:5], 1):
                        lot_id = lot.get("id", lot.get("lot_id", ""))
                        title = lot.get("title", lot.get("name", "Без названия"))[:100]
                        url = lot.get("url", lot.get("link", ""))

                        result_lines.append(f"📌 <b>{i}.</b> {title}")
                        if url:
                            result_lines.append(f'🔗 <a href="{url}">Подробнее</a>')
                        if lot_id:
                            result_lines.append(f"📊 Анализ: /lot {lot_id}")
                        result_lines.append("")

                    if len(lots) > 5:
                        result_lines.append(
                            f"💡 Показано 5 из {len(lots)} найденных лотов"
                        )

                    result_text = "\n".join(result_lines)
                    await message.answer(
                        result_text, parse_mode="HTML", disable_web_page_preview=True
                    )

                    # Логируем использование
                    await log_usage(api_key, "search")
                    logger.info(
                        f"✅ Search completed for user {user_id}: {len(lots)} lots found"
                    )

                else:
                    await loading_msg.delete()
                    await message.answer("❌ Ошибка поиска. Попробуйте позже.")
                    logger.error(f"❌ n8n webhook error {response.status}")

    except TimeoutError:
        await loading_msg.delete()
        await message.answer("⏱️ Превышено время ожидания поиска")
        logger.error(f"⏱️ Search timeout for user {user_id}")
    except Exception as e:
        try:
            await loading_msg.delete()
        except Exception as delete_err:
            logger.debug("Failed to delete loading message: %s", delete_err)
        await message.answer("❌ Ошибка поиска")
        logger.error(f"❌ Search error for user {user_id}: {type(e).__name__}")


@router.message(Command("lot"))
async def lot_command(message: Message):
    """Команда /lot - анализ лота"""
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"

    logger.info(f"📊 /lot from user {user_id} (@{username})")

    # Проверяем API ключ
    api_key = await get_api_key(user_id)
    if not api_key:
        await message.answer(
            "🔑 API ключ не найден. Используйте /key <ваш_ключ> или /start"
        )
        return

    # Валидируем ключ
    validation = await validate_billing_key(api_key, "lot")
    if not validation.get("valid", False):
        error_msg = validation.get("error", "Неверный ключ")
        await message.answer(f"❌ {error_msg}")
        return

    # Извлекаем ID лота
    args = message.text.split(" ", 1)
    if len(args) < 2:
        await message.answer("📊 Использование: /lot <ID_лота>\nПример: /lot 123456789")
        return

    lot_id = args[1].strip()

    if not lot_id.isdigit():
        await message.answer("❌ ID лота должен состоять только из цифр")
        return

    try:
        logger.info(f"📊 Analyzing lot {lot_id} for user {user_id}")

        loading_msg = await message.answer("📊 Анализирую лот...")

        # Запрос к API Gateway
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{zakupai_api_url}/lot/{lot_id}",
                headers={"X-API-Key": api_key},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    await loading_msg.delete()

                    # Простое форматирование анализа
                    result_lines = [f"📊 <b>Анализ лота {lot_id}</b>\n"]

                    if data.get("title"):
                        result_lines.append(f"📋 <b>Название:</b> {data['title']}")
                    if data.get("price"):
                        result_lines.append(f"💰 <b>Цена:</b> {data['price']} тг")
                    if data.get("customer"):
                        result_lines.append(f"🏢 <b>Заказчик:</b> {data['customer']}")
                    if data.get("risk_score"):
                        risk = data["risk_score"]
                        emoji = "🟢" if risk < 0.3 else "🟡" if risk < 0.7 else "🔴"
                        result_lines.append(f"{emoji} <b>Риск:</b> {risk:.2f}")

                    result_text = "\n".join(result_lines)
                    await message.answer(result_text, parse_mode="HTML")

                    # Логируем использование
                    await log_usage(api_key, "lot")
                    logger.info(f"✅ Lot analysis completed for user {user_id}")

                elif response.status == 404:
                    await loading_msg.delete()
                    await message.answer("❌ Лот не найден")
                    logger.warning(f"❌ Lot {lot_id} not found for user {user_id}")
                else:
                    await loading_msg.delete()
                    await message.answer("❌ Ошибка анализа лота")
                    logger.error(
                        f"❌ API Gateway error {response.status} for lot {lot_id}"
                    )

    except TimeoutError:
        await loading_msg.delete()
        await message.answer("⏱️ Превышено время ожидания анализа")
        logger.error(f"⏱️ Lot analysis timeout for user {user_id}")
    except Exception as e:
        try:
            await loading_msg.delete()
        except Exception as delete_err:
            logger.debug("Failed to delete loading message: %s", delete_err)
        await message.answer("❌ Ошибка анализа лота")
        logger.error(f"❌ Lot analysis error for user {user_id}: {type(e).__name__}")


@router.message(Command("help"))
async def help_command(message: Message):
    """Команда /help"""
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"

    logger.info(f"ℹ️ /help from user {user_id} (@{username})")

    help_text = """
🤖 <b>ZakupAI - Помощник по госзакупкам</b>

<b>🔍 Основные команды:</b>
• /start - приветствие и создание API ключа
• /key &lt;ключ&gt; - привязка API ключа
• /search &lt;запрос&gt; - поиск лотов по ключевым словам
• /lot &lt;ID&gt; - анализ конкретного лота
• /help - эта справка

<b>💡 Примеры:</b>
• <code>/search компьютеры офисные</code>
• <code>/search строительство дорог</code>
• <code>/lot 123456789</code>

<b>🔑 API ключи:</b>
Создаются автоматически при первом запуске (/start)
Или привязываются вручную через /key

<b>📞 Поддержка:</b>
По вопросам работы бота обращайтесь в техподдержку.
"""

    await message.answer(help_text, parse_mode="HTML")


# === WEBHOOK SERVER ===


async def health_handler(request):
    """Health check endpoint"""
    return web.json_response(
        {"status": "ok", "mode": "webhook" if USE_WEBHOOK else "polling"}
    )


async def webhook_handler(request, bot: Bot):
    """Webhook handler for Telegram updates"""
    try:
        data = await request.json()
        logger.debug(
            f"📨 Incoming webhook update: {json.dumps(data, ensure_ascii=False)}"
        )

        # Проверяем secret token
        if WEBHOOK_SECRET:
            received_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if received_token != WEBHOOK_SECRET:
                logger.warning("❌ Invalid webhook secret token")
                return web.Response(status=403)

        # Обрабатываем update
        from aiogram.types import Update

        update = Update(**data)
        await dp.feed_update(bot, update)

        return web.Response(status=200)

    except Exception as e:
        logger.error(f"❌ Webhook error: {type(e).__name__}: {e}")
        return web.Response(status=500)


# === MAIN APPLICATION ===


@asynccontextmanager
async def lifespan_context():
    """Контекст жизненного цикла приложения"""
    try:
        # Инициализация БД
        await init_db()
        logger.info("✅ Database initialized")

        yield

    finally:
        logger.info("🛑 Bot shutting down")


async def main():
    """Основная функция запуска бота"""
    async with lifespan_context():
        logger.info("🚀 ZakupAI Telegram Bot starting...")
        logger.info(f"🔧 Mode: {'WEBHOOK' if USE_WEBHOOK else 'POLLING'}")
        logger.info(f"🌍 Environment: {config.security.environment}")

        if USE_WEBHOOK:
            # Webhook режим
            webhook_success = await setup_webhook()

            if webhook_success:
                # Создаем webhook сервер
                app = web.Application()
                app.router.add_get("/health", health_handler)

                # Настраиваем webhook обработчик
                webhook_requests_handler = SimpleRequestHandler(
                    dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET
                )
                webhook_requests_handler.register(app, path="/bot")

                logger.info("🌐 Starting webhook server on port 8000")
                logger.info(f"🔗 Webhook URL: {WEBHOOK_URL}")
                logger.info(
                    f"🔒 Secret token: {'✅ set' if WEBHOOK_SECRET else '❌ not set'}"
                )

                # Запускаем сервер
                runner = web.AppRunner(app)
                await runner.setup()
                site = web.TCPSite(runner, host="0.0.0.0", port=8000)  # nosec B104
                await site.start()

                logger.info("✅ Webhook server started successfully")

                # Ждем завершения
                try:
                    await asyncio.Future()  # run forever
                except KeyboardInterrupt:
                    logger.info("👋 Received interrupt signal")
                finally:
                    await runner.cleanup()
            else:
                logger.error("❌ Failed to setup webhook, falling back to polling")
                await remove_webhook()
                await dp.start_polling(bot)
        else:
            # Polling режим
            await remove_webhook()
            logger.info("🔄 Starting polling mode")
            await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Critical error: {type(e).__name__}: {e}")
