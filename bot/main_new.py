import asyncio
import logging
import os
import re
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.markdown import hbold, hcode
from client_new import LotPipeline, ZakupaiHTTPClient
from db_new import close_db, get_api_key, init_db, save_api_key
from models_new import LotRequest
from notifications import NotificationService

# Logging setup
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Bot initialization
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не установлен")

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Global services
notification_service: NotificationService | None = None


async def get_bot() -> Bot:
    """Get bot instance for external use"""
    return bot


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Handle /start command"""
    user_id = message.from_user.id
    api_key = await get_api_key(user_id)

    if not api_key:
        await message.answer(
            f"👋 Привет, {hbold(message.from_user.full_name)}!\n\n"
            "🔑 Для работы с ZakupAI нужен API ключ.\n"
            f"Отправь: {hcode('api YOUR_API_KEY')}\n\n"
            "Команды:\n"
            f"• {hcode('/lot <id|url>')} - анализ лота\n"
            f"• {hcode('/help')} - справка"
        )
    else:
        await message.answer(
            f"✅ Добро пожаловать, {hbold(message.from_user.full_name)}!\n\n"
            "Команды:\n"
            f"• {hcode('/lot <id|url>')} - анализ лота\n"
            f"• {hcode('api <новый_ключ>')} - обновить ключ\n"
            f"• {hcode('/help')} - справка\n\n"
            "🔥 Уведомления о горячих лотах включены автоматически"
        )


@dp.message(F.text.startswith("api "))
async def cmd_api(message: Message) -> None:
    """Handle api <KEY> command"""
    user_id = message.from_user.id

    try:
        # Delete user message for security
        await message.delete()
    except:
        pass

    # Extract API key
    parts = message.text.split(" ", 1)
    if len(parts) < 2:
        await message.answer("❌ Формат: api <ключ>")
        return

    api_key = parts[1].strip()

    if len(api_key) < 10:
        await message.answer("❌ API ключ слишком короткий")
        return

    # Validate key via health check
    client = ZakupaiHTTPClient(GATEWAY_URL, api_key)

    try:
        health = await client.health_check()
        if not health or health.get("status") != "ok":
            await message.answer("⚠️ API ключ не прошёл проверку")
            return

        # Save key
        saved = await save_api_key(user_id, api_key)
        if saved:
            await message.answer("✅ API ключ сохранён и проверен!")
        else:
            await message.answer("❌ Ошибка сохранения ключа")

    except Exception as e:
        logger.error(f"API validation failed for user {user_id}: {e}")
        await message.answer(f"❌ Ошибка проверки: {str(e)}")


@dp.message(Command("lot"))
async def cmd_lot(message: Message) -> None:
    """Handle /lot <id|url> command"""
    user_id = message.from_user.id

    # Check API key
    api_key = await get_api_key(user_id)
    if not api_key:
        await message.answer(f"🔑 Установите API ключ: {hcode('api YOUR_KEY')}")
        return

    # Extract lot ID
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(f"❌ Формат: {hcode('/lot <id|url>')}")
        return

    lot_input = args[1].strip()
    lot_id = extract_lot_id(lot_input)

    if not lot_id:
        await message.answer("❌ Не удалось извлечь ID лота")
        return

    # Validate lot ID
    try:
        LotRequest(lot_id=lot_id)
    except Exception:
        await message.answer("❌ Некорректный ID лота")
        return

    # Send processing message
    processing_msg = await message.answer("🔄 Анализирую лот... Это займёт ~10-15 сек")

    try:
        # Run pipeline
        client = ZakupaiHTTPClient(GATEWAY_URL, api_key)
        pipeline = LotPipeline(client)

        result = await pipeline.process_lot(lot_id)

        # Format and send result
        formatted = format_pipeline_result(result)

        await processing_msg.edit_text(
            formatted, reply_markup=create_lot_keyboard(lot_id)
        )

    except Exception as e:
        logger.error(f"Lot analysis failed for user {user_id}, lot {lot_id}: {e}")
        await processing_msg.edit_text(f"❌ Ошибка анализа: {str(e)}")


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help command"""
    help_text = f"""🤖 **ZakupAI Telegram Bot**

📋 **Команды:**
• {hcode('/start')} - начать работу
• {hcode('api <ключ>')} - установить API ключ
• {hcode('/lot <id|url>')} - анализ лота
• {hcode('/help')} - эта справка

🔍 **Примеры:**
• {hcode('/lot 12345')}
• {hcode('/lot https://goszakup.gov.kz/ru/announce/index/12345')}

🔥 **Горячие лоты:**
• Автоматические уведомления каждые 15 минут
• Критерии: маржа ≥15%, риск ≥60%, дедлайн ≤3 дня

🔧 **Поддержка:** @zakupai_support"""

    await message.answer(help_text)


@dp.callback_query(F.data.startswith(("analyze_", "pdf_", "json_")))
async def handle_lot_actions(callback: CallbackQuery) -> None:
    """Handle inline keyboard callbacks"""
    user_id = callback.from_user.id
    data = callback.data

    # Extract action and lot_id
    action, lot_id = data.split("_", 1)

    api_key = await get_api_key(user_id)
    if not api_key:
        await callback.answer("🔑 API ключ не найден", show_alert=True)
        return

    await callback.answer("🔄 Обрабатываю...")

    try:
        client = ZakupaiHTTPClient(GATEWAY_URL, api_key)

        if action == "analyze":
            # Re-run analysis
            pipeline = LotPipeline(client)
            result = await pipeline.process_lot(lot_id)
            formatted = format_pipeline_result(result)

            await callback.message.answer(formatted)

        elif action == "pdf":
            # Generate PDF (placeholder - needs doc-service integration)
            await callback.message.answer("📄 PDF генерация в разработке")

        elif action == "json":
            # Send JSON data
            pipeline = LotPipeline(client)
            result = await pipeline.process_lot(lot_id)

            # Format as JSON string
            import json

            json_str = json.dumps(result, ensure_ascii=False, indent=2)

            if len(json_str) > 4000:
                json_str = json_str[:4000] + "..."

            await callback.message.answer(
                f"```json\n{json_str}\n```", parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Callback action {action} failed for user {user_id}: {e}")
        await callback.message.answer("❌ Ошибка выполнения действия")


def extract_lot_id(lot_input: str) -> str | None:
    """Extract lot ID from string or URL"""
    if lot_input.isdigit():
        return lot_input

    # URL patterns
    patterns = [
        r"/announce/index/(\d+)",
        r"/lot/(\d+)",
        r"lot_id=(\d+)",
        r"id=(\d+)",
        r"(\d{6,})",  # 6+ digits
    ]

    for pattern in patterns:
        match = re.search(pattern, lot_input)
        if match:
            return match.group(1)

    return None


def format_pipeline_result(result: dict) -> str:
    """Format pipeline result for Telegram"""
    lot_id = result["lot_id"]

    if result.get("errors"):
        errors = "\n".join(result["errors"])
        return f"❌ **Ошибки анализа лота {lot_id}:**\n{errors}"

    output = [f"📊 **Анализ лота {hbold(lot_id)}**"]

    # Goszakup data
    if result.get("goszakup"):
        gosz = result["goszakup"]
        output.append("\n📝 **Основная информация:**")
        output.append(f"• Название: {gosz.get('title', 'N/A')}")
        output.append(f"• Цена: {gosz.get('price', 'N/A')} тг")
        output.append(f"• Заказчик: {gosz.get('customer', 'N/A')}")
        output.append(f"• Дедлайн: {gosz.get('deadline', 'N/A')}")

    # Risk analysis
    if result.get("risk"):
        risk = result["risk"]
        score = risk.get("score", 0) * 100  # Convert to percentage
        level_emoji = "🟢" if score < 30 else "🟡" if score < 70 else "🔴"

        output.append("\n⚠️ **Риск-анализ:**")
        output.append(f"• Уровень: {level_emoji} {score:.1f}%")
        if risk.get("explanation"):
            output.append(f"• Причины: {risk['explanation']}")

    # Financial calculations
    if result.get("calc"):
        calc = result["calc"]
        output.append("\n💰 **Финансы:**")

        if calc.get("margin"):
            margin = calc["margin"] * 100
            margin_emoji = "💰" if margin >= 15 else "💵"
            output.append(f"• {margin_emoji} Маржа: {margin:.1f}%")

        if calc.get("vat"):
            output.append(f"• НДС: {calc['vat']:.0f} тг")

        if calc.get("total"):
            output.append(f"• Итого: {calc['total']:,.0f} тг")

    # Document
    if result.get("doc") and result["doc"].get("tldr"):
        output.append(f"\n📋 **TL;DR:** {result['doc']['tldr']}")

    return "\n".join(output)


def create_lot_keyboard(lot_id: str) -> InlineKeyboardMarkup:
    """Create inline keyboard for lot actions"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📄 PDF", callback_data=f"pdf_{lot_id}"),
                InlineKeyboardButton(text="📋 JSON", callback_data=f"json_{lot_id}"),
            ],
            [
                InlineKeyboardButton(
                    text="🔍 Goszakup",
                    url=f"https://goszakup.gov.kz/ru/announce/index/{lot_id}",
                )
            ],
        ]
    )
    return keyboard


@asynccontextmanager
async def lifespan():
    """Application lifespan context"""
    global notification_service

    # Startup
    await init_db()
    notification_service = NotificationService(bot)
    logger.info("ZakupAI Bot started")

    yield

    # Shutdown
    await close_db()
    logger.info("ZakupAI Bot stopped")


async def main():
    """Main bot runner"""
    async with lifespan():
        logger.info("Starting bot polling...")
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
