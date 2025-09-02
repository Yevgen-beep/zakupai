"""
Обработчики команд Telegram-бота ZakupAI
"""

import asyncio
import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from db_simple import get_user_api_key, get_user_stats, save_user_api_key
from error_handler import (
    ValidationException,
    check_user_permissions,
    validate_user_input,
)
from models import (
    LotAnalysisResult,
    RiskScoreResponse,
    TLDRResponse,
    VATResponse,
    extract_lot_id_from_url,
    validate_lot_id,
)

from services import (
    billing_service,
    format_lot_analysis,
    format_search_results,
    goszakup_service,
    zakupai_service,
)

logger = logging.getLogger(__name__)
router = Router()


async def require_api_key_and_log_usage(
    message: Message, endpoint: str, cost: int = 1
) -> str | None:
    """Универсальный декоратор для проверки API ключа и логирования использования"""

    user_id = message.from_user.id

    # Проверяем разрешения пользователя
    if not await check_user_permissions(user_id, endpoint):
        await message.answer("❌ Недостаточно прав для выполнения команды")
        return None

    # Получаем API ключ пользователя
    api_key = await get_user_api_key(user_id)
    if not api_key:
        await message.answer(
            "🔑 API ключ не найден. Используйте /key <ваш_ключ> для привязки ключа"
        )
        return None

    # Валидируем ключ и логируем использование
    validation_result = await billing_service.validate_key_and_log_usage(
        api_key, user_id, endpoint, cost
    )

    if not validation_result.get("valid", False):
        error_msg = validation_result.get("error", "Ошибка валидации ключа")
        await message.answer(error_msg)
        return None

    return api_key


@router.message(CommandStart())
async def start_command(message: Message):
    """Команда /start - приветствие и регистрация"""

    user_id = message.from_user.id
    username = message.from_user.username or "без_имени"

    logger.info(f"User {user_id} (@{username}) started the bot")

    welcome_text = """
👋 Добро пожаловать в <b>ZakupAI</b>!

🤖 Я помогаю анализировать государственные закупки Казахстана:
• 🔍 Поиск лотов по ключевым словам
• 📊 Полный анализ тендеров (TL;DR, риски, финансы)
• 💡 Рекомендации по участию
• 📄 Генерация документов и жалоб

<b>🚀 Основные команды:</b>
/search <слово> — поиск лотов
/lot <ID> — анализ конкретного лота
/key <ключ> — привязка API ключа
/help — справка по командам

<b>🔑 Получение API ключа:</b>
1. Перейдите на zakupai.kz
2. Зарегистрируйтесь и получите ключ
3. Используйте /key для привязки

Начните с команды /search или получите API ключ! 🎯
"""

    await message.answer(welcome_text, parse_mode="HTML")


@router.message(Command("key"))
async def key_command(message: Message):
    """Команда /key - привязка API ключа"""

    user_id = message.from_user.id
    username = message.from_user.username or "без_имени"

    # Извлекаем ключ из команды
    command_args = message.text.split(" ", 1)
    if len(command_args) < 2:
        await message.answer(
            "🔑 Использование: /key <ваш_api_ключ>\n"
            "Пример: /key 12345678-1234-1234-1234-123456789abc"
        )
        return

    try:
        api_key = await validate_user_input(command_args[1], max_length=100)

        # Базовая валидация формата ключа (UUID-подобный)
        if len(api_key) < 10 or not all(c.isalnum() or c in "-_" for c in api_key):
            raise ValidationException("Неверный формат API ключа")

        # Проверяем ключ через billing service
        validation_result = await billing_service.validate_key_and_log_usage(
            api_key, user_id, "key_validation", cost=0
        )

        if not validation_result.get("valid", False):
            error_msg = validation_result.get("error", "Недействительный API ключ")
            await message.answer(f"❌ {error_msg}")
            return

        # Сохраняем ключ
        success = await save_user_api_key(user_id, api_key)
        if not success:
            await message.answer("❌ Ошибка сохранения ключа. Попробуйте позже")
            return

        user_plan = validation_result.get("user_plan", "free")

        await message.answer(
            f"✅ API ключ успешно привязан!\n"
            f"📋 План: {user_plan.upper()}\n"
            f"🚀 Теперь вы можете использовать все команды бота"
        )

        logger.info(
            f"User {user_id} (@{username}) connected API key (plan: {user_plan})"
        )

    except ValidationException as e:
        await message.answer(f"❌ {str(e)}")
    except Exception as e:
        logger.error(f"Error in key command for user {user_id}: {type(e).__name__}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже")


@router.message(Command("search"))
async def search_command(message: Message):
    """Команда /search - поиск лотов по ключевым словам"""

    user_id = message.from_user.id

    # Проверяем API ключ и логируем использование
    api_key = await require_api_key_and_log_usage(message, "search", cost=2)
    if not api_key:
        return

    # Извлекаем поисковый запрос
    command_args = message.text.split(" ", 1)
    if len(command_args) < 2:
        await message.answer(
            "🔍 Использование: /search <ключевые слова>\n"
            "Пример: /search компьютеры\n"
            "Пример: /search строительство дорог"
        )
        return

    try:
        query = await validate_user_input(command_args[1], max_length=200)

        if len(query) < 2:
            raise ValidationException(
                "Поисковый запрос слишком короткий (минимум 2 символа)"
            )

        # Отправляем уведомление о поиске
        loading_msg = await message.answer(
            "🔍 Ищу лоты... Это может занять несколько секунд"
        )

        # Выполняем поиск
        lots = await goszakup_service.search_lots(query, limit=10)

        # Удаляем сообщение о загрузке
        await loading_msg.delete()

        # Форматируем и отправляем результаты
        results_text = format_search_results(lots)
        await message.answer(
            results_text, parse_mode="HTML", disable_web_page_preview=True
        )

        logger.info(f"User {user_id} searched for '{query}' - found {len(lots)} lots")

    except ValidationException as e:
        await message.answer(f"❌ {str(e)}")
    except Exception as e:
        logger.error(f"Error in search command for user {user_id}: {type(e).__name__}")
        await message.answer("❌ Произошла ошибка поиска. Попробуйте позже")


@router.message(Command("lot"))
async def lot_command(message: Message):
    """Команда /lot - полный анализ лота"""

    user_id = message.from_user.id

    # Проверяем API ключ и логируем использование (анализ стоит дороже)
    api_key = await require_api_key_and_log_usage(message, "lot_analysis", cost=5)
    if not api_key:
        return

    # Извлекаем ID лота
    command_args = message.text.split(" ", 1)
    if len(command_args) < 2:
        await message.answer(
            "📊 Использование: /lot <ID_лота или URL>\n"
            "Пример: /lot 123456789\n"
            "Пример: /lot https://goszakup.gov.kz/ru/announce/index/123456789"
        )
        return

    try:
        lot_input = await validate_user_input(command_args[1], max_length=500)

        # Определяем, это ID или URL
        if lot_input.startswith("http"):
            lot_id = extract_lot_id_from_url(lot_input)
            if not lot_id:
                raise ValidationException("Не удалось извлечь ID лота из URL")
        else:
            lot_id = lot_input

        # Валидируем ID лота
        if not validate_lot_id(lot_id):
            raise ValidationException("Неверный формат ID лота")

        # Отправляем уведомление об анализе
        loading_msg = await message.answer(
            "📊 Анализирую лот... Это может занять до минуты"
        )

        # Выполняем параллельный анализ
        start_time = datetime.now()

        tasks = [
            zakupai_service.get_tldr(lot_id, api_key),
            zakupai_service.get_risk_score(lot_id, api_key),
            zakupai_service.calculate_vat(
                100000, api_key
            ),  # Примерная сумма для демонстрации
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Обрабатываем результаты
        tldr_result, risk_result, vat_result = results

        analysis = LotAnalysisResult(
            lot_id=lot_id,
            tldr=tldr_result if isinstance(tldr_result, TLDRResponse) else None,
            risk=risk_result if isinstance(risk_result, RiskScoreResponse) else None,
            finance=vat_result if isinstance(vat_result, VATResponse) else None,
            errors=[str(r) for r in results if isinstance(r, Exception)],
            analysis_time=(datetime.now() - start_time).total_seconds(),
            analyzed_at=datetime.now(),
        )

        # Удаляем сообщение о загрузке
        await loading_msg.delete()

        # Отправляем результат анализа
        analysis_text = format_lot_analysis(analysis)
        await message.answer(
            analysis_text, parse_mode="HTML", disable_web_page_preview=True
        )

        logger.info(
            f"User {user_id} analyzed lot {lot_id} in {analysis.analysis_time:.2f}s"
        )

    except ValidationException as e:
        await message.answer(f"❌ {str(e)}")
    except Exception as e:
        logger.error(f"Error in lot analysis for user {user_id}: {type(e).__name__}")
        await message.answer("❌ Произошла ошибка анализа. Попробуйте позже")


@router.message(Command("stats"))
async def stats_command(message: Message):
    """Команда /stats - статистика пользователя"""

    user_id = message.from_user.id

    # Проверяем API ключ (статистика бесплатная)
    api_key = await require_api_key_and_log_usage(message, "stats", cost=0)
    if not api_key:
        return

    try:
        # Получаем статистику из базы
        user_stats = await get_user_stats(user_id)

        if not user_stats:
            await message.answer("📊 Статистика недоступна")
            return

        stats_text = f"""
📊 <b>Ваша статистика</b>

👤 ID пользователя: {user_id}
📅 Дата регистрации: {user_stats.registered_at.strftime('%d.%m.%Y')}
🔄 Последнее обновление: {user_stats.last_updated.strftime('%d.%m.%Y %H:%M')}
📈 Количество запросов: {user_stats.requests_count or 0}

{"🟢 Активен" if user_stats.is_active else "🔴 Неактивен"}

💡 Используйте команды для анализа тендеров!
"""

        await message.answer(stats_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error getting stats for user {user_id}: {type(e).__name__}")
        await message.answer("❌ Ошибка получения статистики")


@router.message(Command("help"))
async def help_command(message: Message):
    """Команда /help - справка по командам"""

    help_text = """
🤖 <b>ZakupAI - Помощник по госзакупкам</b>

<b>🔍 Основные команды:</b>
/start — приветствие и инструкции
/key &lt;ключ&gt; — привязка API ключа
/search &lt;слова&gt; — поиск лотов по ключевым словам
/lot &lt;ID&gt; — полный анализ конкретного лота
/stats — ваша статистика использования
/help — эта справка

<b>💡 Примеры использования:</b>
• <code>/search компьютеры офисные</code>
• <code>/search строительство дорог</code>
• <code>/lot 123456789</code>
• <code>/lot https://goszakup.gov.kz/ru/announce/index/123456789</code>

<b>🔑 Получение API ключа:</b>
1. Зарегистрируйтесь на zakupai.kz
2. Получите API ключ в личном кабинете
3. Привяжите его командой /key

<b>🎯 Планы подписки:</b>
• FREE: 100 запросов/день, 20/час
• PREMIUM: 5000 запросов/день, 500/час

<b>📞 Поддержка:</b>
По вопросам работы бота обращайтесь в техподдержку zakupai.kz

<b>🔒 Безопасность:</b>
Все данные защищены, API ключи не передаются третьим лицам.
"""

    await message.answer(help_text, parse_mode="HTML")


# Дополнительные команды для будущих интеграций


@router.message(Command("risk"))
async def risk_command(message: Message):
    """Команда /risk - подробный риск-анализ (будущая интеграция)"""

    await message.answer(
        "🔧 Команда /risk в разработке\n"
        "Скоро здесь будет подробный риск-анализ с рекомендациями.\n"
        "Пока используйте /lot для базового анализа рисков."
    )


@router.message(Command("profit"))
async def profit_command(message: Message):
    """Команда /profit - анализ прибыльности (будущая интеграция)"""

    await message.answer(
        "🔧 Команда /profit в разработке\n"
        "Скоро здесь будет калькулятор прибыльности участия в тендере.\n"
        "Пока используйте /lot для базового финансового анализа."
    )


@router.message(Command("complaint"))
async def complaint_command(message: Message):
    """Команда /complaint - генерация жалоб (будущая интеграция)"""

    await message.answer(
        "🔧 Команда /complaint в разработке\n"
        "Скоро здесь будет генератор жалоб на нарушения в тендерах.\n"
        "Следите за обновлениями!"
    )


@router.message(Command("hot"))
async def hot_command(message: Message):
    """Команда /hot - горячие лоты (будущая интеграция)"""

    await message.answer(
        "🔧 Команда /hot в разработке\n"
        "Скоро здесь будут уведомления о горячих лотах по вашим критериям.\n"
        "Пока используйте /search для поиска интересных тендеров."
    )


# Обработчик неизвестных команд
@router.message(F.text.startswith("/"))
async def unknown_command(message: Message):
    """Обработчик неизвестных команд"""

    await message.answer(
        "❓ Неизвестная команда\n" "Используйте /help для просмотра доступных команд"
    )


# Обработчик обычных текстовых сообщений
@router.message(F.text)
async def text_message_handler(message: Message):
    """Обработчик обычных текстовых сообщений"""

    text = message.text.lower()

    # Простые ответы на частые вопросы
    if any(word in text for word in ["привет", "hello", "здравствуй"]):
        await message.answer(
            "👋 Привет! Я ZakupAI бот.\n"
            "Используйте /start для знакомства или /help для справки"
        )
    elif any(word in text for word in ["помощь", "help", "что умеешь"]):
        await help_command(message)
    elif any(word in text for word in ["поиск", "найди", "search"]):
        await message.answer(
            "🔍 Для поиска используйте команду /search\n" "Пример: /search компьютеры"
        )
    else:
        await message.answer(
            "🤔 Не понимаю. Используйте команды:\n"
            "/search - поиск лотов\n"
            "/lot - анализ лота\n"
            "/help - справка"
        )
