"""
Обновленные обработчики команд Telegram-бота ZakupAI v2
Использует новую поисковую систему с GraphQL v2 и REST v3
"""

import logging
import re

import httpx
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

# Импортируем обновленные сервисы
from analytics_service import analytics_service
from db_simple import get_user_api_key, get_user_stats, save_user_api_key
from error_handler import (
    ValidationException,
    check_user_permissions,
    validate_user_input,
)
from services_v2 import (
    billing_service,
    format_search_results,
    goszakup_service,
    search_lots_for_telegram_v2,
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
            "🔑 Для использования этой команды нужен API ключ.\n"
            "Получите ключ на zakupai.kz и привяжите его командой /key"
        )
        return None

    # Проверяем ключ и логируем использование
    validation_result = await billing_service.validate_key_and_log_usage(
        api_key, user_id, endpoint, cost
    )

    if not validation_result.get("valid", False):
        error_msg = validation_result.get("error", "Недействительный API ключ")
        await message.answer(f"❌ {error_msg}")
        return None

    return api_key


@router.message(CommandStart())
async def start_command(message: Message):
    """Команда /start - приветствие и инструкции"""

    user_id = message.from_user.id
    username = message.from_user.username or "без_имени"

    logger.info(f"User {user_id} ({username}) started the bot")

    welcome_text = """
👋 <b>Добро пожаловать в ZakupAI!</b>

Я помогу вам работать с госзакупками Казахстана:
• 🔍 Интеллектуальный поиск лотов с новой системой
• 📊 Полный анализ тендеров (TL;DR, риски, финансы)
• 💡 Рекомендации по участию
• 📄 Генерация документов и жалоб

<b>🚀 Основные команды:</b>
/search &lt;слово&gt; — умный поиск лотов
/search_advanced — расширенный поиск с фильтрами
/lot &lt;ID&gt; — анализ конкретного лота
/stats — статистика поиска
/key &lt;ключ&gt; — привязка API ключа
/help — справка по командам

<b>🔑 Получение API ключа:</b>
1. Перейдите на zakupai.kz
2. Зарегистрируйтесь и получите ключ
3. Используйте /key для привязки

<b>🆕 Новые возможности v2:</b>
• GraphQL v2 API для более точного поиска
• Автоматический fallback на REST v3
• Улучшенная фильтрация по БИН, сумме, статусу
• Статистика использования API

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
            f"🔢 Использование: {validation_result.get('usage_count', 0)}/{validation_result.get('usage_limit', 100)}\n"
            f"🚀 Теперь вы можете использовать все функции бота!"
        )

        logger.info(f"User {user_id} ({username}) linked API key with plan {user_plan}")

    except ValidationException as e:
        await message.answer(f"❌ {str(e)}")
    except Exception as e:
        logger.error(f"Error in key command for user {user_id}: {type(e).__name__}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже")


@router.message(Command("search"))
async def search_command(message: Message):
    """Команда /search - интеллектуальный поиск лотов по ключевым словам"""
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
            "Примеры:\n"
            "• /search лак\n"
            "• /search компьютеры офисные\n"
            "• /search строительство дорог\n"
            "• /search мебель БИН:123456789012\n"
            "• /search уголь сумма:100000-500000\n\n"
            "💡 Новая система автоматически выбирает лучший API!"
        )
        return

    try:
        # Получаем исходный запрос и логируем его
        raw_query = command_args[1].strip()
        logger.info(f"User {user_id} raw_query='{raw_query}'")

        # Нормализуем запрос
        normalized_query = raw_query.casefold()

        # Валидируем исходный запрос
        query = await validate_user_input(raw_query, max_length=200)
        if len(query) < 2:
            raise ValidationException(
                "Поисковый запрос слишком короткий (минимум 2 символа)"
            )

        # Отправляем уведомление о поиске
        loading_msg = await message.answer(
            "🔍 Ищу лоты через новую систему... Это может занять несколько секунд"
        )

        # Используем новую логику поиска с нормализацией и n8n fallback
        results_text = await search_lots_for_telegram_v2(
            raw_query, limit=10, show_source=True, user_id=user_id
        )
        search_successful = results_text and "❌ Лоты не найдены" not in results_text

        if search_successful:
            logger.info(f"User {user_id} search successful")
        else:
            logger.info(
                f"User {user_id} → no results for raw='{raw_query}', normalized='{normalized_query}'"
            )

        # Удаляем сообщение о загрузке
        await loading_msg.delete()

        # Отправляем результаты
        await message.answer(
            results_text, parse_mode="HTML", disable_web_page_preview=True
        )

        # Показываем статистику API
        stats = goszakup_service.get_search_statistics()
        stats_text = (
            f"\n📊 Статистика API:\n"
            f"GraphQL v2: {stats['v2_requests']} запросов\n"
            f"REST v3: {stats['v3_rest_requests']} запросов\n"
            f"Fallback: {stats['fallback_requests']} случаев"
        )

        await message.answer(stats_text)

        logger.info(
            f"User {user_id} search completed: raw='{raw_query}', normalized='{normalized_query}', success={search_successful}"
        )

    except ValidationException as e:
        await message.answer(f"❌ {str(e)}")
    except Exception as e:
        logger.error(f"Error in search command for user {user_id}: {type(e).__name__}")
        await message.answer("❌ Произошла ошибка поиска. Попробуйте позже")


@router.message(Command("search_advanced"))
async def search_advanced_command(message: Message):
    """Команда /search_advanced - расширенный поиск с фильтрами"""
    user_id = message.from_user.id

    # Проверяем API ключ
    api_key = await require_api_key_and_log_usage(message, "search_advanced", cost=3)
    if not api_key:
        return

    # Парсим параметры расширенного поиска
    command_args = message.text.split(" ", 1)
    if len(command_args) < 2:
        await message.answer(
            "🔍 Расширенный поиск:\n"
            "/search_advanced <параметры>\n\n"
            "Параметры:\n"
            "• keyword=мебель - ключевое слово\n"
            "• bin=123456789012 - БИН заказчика\n"
            "• method=тендер - способ закупки\n"
            "• status=прием - статус лота\n"
            "• min=100000 - минимальная сумма\n"
            "• max=500000 - максимальная сумма\n\n"
            "Пример:\n"
            "/search_advanced keyword=компьютеры min=50000 max=200000 method=тендер"
        )
        return

    try:
        # Получаем исходные параметры и логируем их
        raw_params_str = command_args[1].strip()
        logger.info(f"User {user_id} raw_query='{raw_params_str}'")

        params_str = await validate_user_input(raw_params_str, max_length=300)

        # Парсим параметры
        params = {}
        for param in params_str.split():
            if "=" in param:
                key, value = param.split("=", 1)
                params[key.strip()] = value.strip()

        # Извлекаем параметры поиска
        raw_keyword = params.get("keyword")

        customer_bin = params.get("bin")
        trade_methods = [params.get("method")] if params.get("method") else None
        statuses = [params.get("status")] if params.get("status") else None
        min_amount = float(params["min"]) if params.get("min", "").isdigit() else None
        max_amount = float(params["max"]) if params.get("max", "").isdigit() else None

        # Валидация
        if not any(
            [raw_keyword, customer_bin, trade_methods, statuses, min_amount, max_amount]
        ):
            raise ValidationException("Необходимо указать хотя бы один параметр поиска")

        # Отправляем уведомление о поиске
        loading_msg = await message.answer("🔧 Выполняю расширенный поиск...")

        # Используем новую логику поиска с нормализацией
        lots = await goszakup_service.search_lots_advanced(
            keyword=raw_keyword,  # Новая логика сама обработает нормализацию
            customer_bin=customer_bin,
            trade_methods=trade_methods,
            statuses=statuses,
            min_amount=min_amount,
            max_amount=max_amount,
            limit=15,
            user_id=user_id,
        )

        search_successful = lots and len(lots) > 0

        if search_successful:
            logger.info(
                f"User {user_id} advanced search successful: found {len(lots)} lots"
            )
        else:
            if raw_keyword:
                logger.info(
                    f"User {user_id} → no results for advanced search with keyword='{raw_keyword}'"
                )
            else:
                logger.info(
                    f"User {user_id} → no results for advanced search without keyword"
                )

        # Удаляем сообщение о загрузке
        await loading_msg.delete()

        # Форматируем и отправляем результаты
        results_text = (
            format_search_results(lots)
            if lots
            else "❌ Лоты не найдены по указанным критериям. Попробуйте изменить параметры поиска."
        )
        await message.answer(
            results_text, parse_mode="HTML", disable_web_page_preview=True
        )

        logger.info(
            f"User {user_id} advanced search completed: {len(params)} parameters, success={search_successful}"
        )

    except ValidationException as e:
        await message.answer(f"❌ {str(e)}")
    except ValueError:
        await message.answer("❌ Неверный формат числовых параметров (min/max)")
    except Exception as e:
        logger.error(f"Error in advanced search for user {user_id}: {type(e).__name__}")
        await message.answer("❌ Произошла ошибка расширенного поиска")


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
            "📊 Использование: /lot <номер_лота>\n"
            "Пример: /lot LOT-123456789\n"
            "Пример: /lot ANNO-987654321"
        )
        return

    try:
        lot_identifier = await validate_user_input(command_args[1], max_length=50)

        # Отправляем уведомление о поиске
        loading_msg = await message.answer("🔍 Ищу информацию о лоте...")

        # Ищем лот по номеру
        lot = await goszakup_service.get_lot_by_number(lot_identifier)

        await loading_msg.delete()

        if not lot:
            await message.answer(f"❌ Лот с номером '{lot_identifier}' не найден")
            return

        # Формируем детальную информацию о лоте
        lot_info = f"""
📋 <b>Информация о лоте</b>

🔢 <b>Номер лота:</b> {lot["id"]}
📦 <b>Наименование:</b> {lot["name"]}
💰 <b>Сумма:</b> {lot["price"]:,.0f} {lot.get("currency", "тг")}
🏢 <b>Заказчик:</b> {lot["customer"]}
"""

        if lot.get("customer_bin"):
            lot_info += f"🏛️ <b>БИН заказчика:</b> <code>{lot['customer_bin']}</code>\n"

        if lot.get("trade_method"):
            lot_info += f"🛒 <b>Способ закупки:</b> {lot['trade_method']}\n"

        lot_info += f"📊 <b>Статус:</b> {lot['status']}\n"

        if lot.get("quantity", 0) > 0:
            lot_info += f"🔢 <b>Количество:</b> {lot['quantity']}\n"

        if lot.get("description"):
            description = (
                lot["description"][:300] + "..."
                if len(lot["description"]) > 300
                else lot["description"]
            )
            lot_info += f"📋 <b>Описание:</b> {description}\n"

        if lot.get("deadline"):
            lot_info += f"⏰ <b>Срок:</b> {lot['deadline'][:16]}\n"

        if lot.get("url"):
            lot_info += f"🔗 <a href='{lot['url']}'>Открыть на сайте</a>\n"

        if lot.get("source"):
            source_name = {
                "graphql_v2": "GraphQL v2",
                "graphql_v3": "GraphQL v3",
                "rest_v3": "REST v3",
            }.get(lot["source"], lot["source"])
            lot_info += f"📡 <b>Источник данных:</b> {source_name}\n"

        await message.answer(lot_info, parse_mode="HTML", disable_web_page_preview=True)

        logger.info(f"User {user_id} analyzed lot '{lot_identifier}'")

    except ValidationException as e:
        await message.answer(f"❌ {str(e)}")
    except Exception as e:
        logger.error(f"Error in lot command for user {user_id}: {type(e).__name__}")
        await message.answer("❌ Произошла ошибка анализа лота")


@router.message(Command("stats"))
async def stats_command(message: Message):
    """Команда /stats - статистика пользователя и системы"""

    user_id = message.from_user.id

    try:
        # Получаем статистику пользователя
        user_stats = await get_user_stats(user_id)

        # Получаем статистику поиска
        search_stats = goszakup_service.get_search_statistics()

        stats_text = f"""
📊 <b>Ваша статистика</b>

👤 <b>Пользователь:</b> {user_id}
📅 <b>Дата регистрации:</b> {user_stats.get("created_at", "Неизвестно")[:10] if user_stats.get("created_at") else "Неизвестно"}
🔑 <b>API ключ:</b> {"✅ Привязан" if user_stats.get("api_key") else "❌ Не привязан"}
🔢 <b>Всего запросов:</b> {user_stats.get("total_requests", 0)}

📈 <b>Статистика поиска</b>

🚀 <b>GraphQL v2:</b> {search_stats.get("v2_requests", 0)} запросов
🔄 <b>GraphQL v3:</b> {search_stats.get("v3_graphql_requests", 0)} запросов
📡 <b>REST v3:</b> {search_stats.get("v3_rest_requests", 0)} запросов
🆘 <b>Fallback:</b> {search_stats.get("fallback_requests", 0)} случаев
❌ <b>Ошибки:</b> {search_stats.get("failed_requests", 0)} запросов

🎯 <b>Успешность:</b> {search_stats.get("success_rate", 0) * 100:.1f}%

🔧 <b>Доступность API</b>
GraphQL v2: {"✅" if goszakup_service.is_v2_available() else "❌"}
REST v3: {"✅" if goszakup_service.is_v3_available() else "❌"}
"""

        await message.answer(stats_text, parse_mode="HTML")

        logger.info(f"User {user_id} requested stats")

    except Exception as e:
        logger.error(f"Error in stats command for user {user_id}: {type(e).__name__}")
        await message.answer("❌ Произошла ошибка получения статистики")


@router.message(Command("help"))
async def help_command(message: Message):
    """Команда /help - справка по командам"""

    help_text = """
🤖 <b>ZakupAI v2 - Помощник по госзакупкам</b>

<b>🔍 Команды поиска:</b>
/start — приветствие и инструкции
/search &lt;слова&gt; — умный поиск лотов
/search_advanced — расширенный поиск с фильтрами
/lot &lt;номер&gt; — детальная информация о лоте

<b>🔧 Управление:</b>
/key &lt;ключ&gt; — привязка API ключа
/stats — ваша статистика использования
/mystats — ваша персональная статистика поиска
/help — эта справка

<b>📊 Аналитика (только админы):</b>
/analytics — общая статистика системы
/popular — популярные поисковые запросы
/top_users — самые активные пользователи
/errors — отчет по ошибкам

<b>🧹 Управление данными (только админы):</b>
/dbinfo — информация о базе данных
/cleanup [дни] — очистка логов старше N дней (по умолчанию 90)
/autocleanup [размер_MB] — автоочистка при превышении размера (по умолчанию 100MB)

<b>💡 Примеры поиска:</b>
• <code>/search лак</code>
• <code>/search компьютеры офисные</code>
• <code>/search мебель БИН:123456789012</code>
• <code>/search уголь сумма:100000-500000</code>

<b>🔧 Расширенный поиск:</b>
• <code>/search_advanced keyword=компьютеры min=50000 max=200000</code>
• <code>/search_advanced bin=123456789012 method=тендер</code>

<b>🆕 Новшества v2:</b>
• Автоматический выбор лучшего API (GraphQL v2/v3, REST v3)
• Умная фильтрация по БИН, суммам, статусам
• Fallback система для надежности
• Статистика использования API

<b>🔑 Получение API ключа:</b>
1. Зарегистрируйтесь на zakupai.kz
2. Получите API ключ в личном кабинете
3. Привяжите его командой /key

<b>🎯 Планы подписки:</b>
• FREE: 100 запросов/день, 20/час
• PREMIUM: 5000 запросов/день, 500/час

<b>📞 Поддержка:</b>
По вопросам работы бота обращайтесь в техподдержку zakupai.kz
"""

    await message.answer(help_text, parse_mode="HTML")


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
        "❓ Неизвестная команда\n"
        "Используйте /help для просмотра доступных команд\n\n"
        "🆕 Доступны новые команды v2:\n"
        "• /search_advanced - расширенный поиск\n"
        "• /stats - статистика API"
    )


# Обработчик обычных текстовых сообщений
@router.message(F.text)
async def text_message_handler(message: Message):
    """Обработчик обычных текстовых сообщений"""
    text = message.text.lower()

    if any(word in text for word in ["привет", "hello", "старт", "начать"]):
        await message.answer(
            "👋 Привет! Я ZakupAI бот v2.\n"
            "Используйте /start для знакомства или /help для справки\n"
            "🆕 Теперь с улучшенным поиском через GraphQL v2!"
        )
    elif any(word in text for word in ["помощь", "help", "что умеешь"]):
        await help_command(message)
    elif any(word in text for word in ["поиск", "найди", "search"]):
        await message.answer(
            "🔍 Для поиска используйте команду /search\n"
            "Пример: /search компьютеры\n"
            "🆕 Попробуйте /search_advanced для расширенного поиска!"
        )
    else:
        await message.answer(
            "🤔 Не понимаю. Используйте команды:\n"
            "/search - поиск лотов\n"
            "/search_advanced - расширенный поиск\n"
            "/lot - анализ лота\n"
            "/stats - статистика\n"
            "/help - справка"
        )


@router.message(Command("analytics"))
async def analytics_command(message: Message):
    """Команда аналитики (только для админов)"""

    # Список ID администраторов (замените на реальные ID)
    admin_ids = {123456789, 987654321}  # Добавьте реальные ID админов

    if message.from_user.id not in admin_ids:
        await message.answer("⛔ Эта команда доступна только администраторам.")
        return

    try:
        # Получаем общую статистику за неделю
        dashboard = analytics_service.get_dashboard_summary(days=7)
        await message.answer(dashboard, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Analytics command error: {e}")
        await message.answer(f"❌ Ошибка получения аналитики: {str(e)}")


@router.message(Command("popular"))
async def popular_searches_command(message: Message):
    """Команда популярных поисков (только для админов)"""

    # Список ID администраторов (замените на реальные ID)
    admin_ids = {123456789, 987654321}  # Добавьте реальные ID админов

    if message.from_user.id not in admin_ids:
        await message.answer("⛔ Эта команда доступна только администраторам.")
        return

    try:
        # Получаем популярные запросы за неделю
        popular = analytics_service.get_popular_searches_text(days=7, limit=15)
        await message.answer(popular, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Popular searches command error: {e}")
        await message.answer(f"❌ Ошибка получения популярных запросов: {str(e)}")


@router.message(Command("top_users"))
async def top_users_command(message: Message):
    """Команда топ пользователей (только для админов)"""

    # Список ID администраторов (замените на реальные ID)
    admin_ids = {123456789, 987654321}  # Добавьте реальные ID админов

    if message.from_user.id not in admin_ids:
        await message.answer("⛔ Эта команда доступна только администраторам.")
        return

    try:
        # Получаем топ пользователей за неделю
        top_users = analytics_service.get_top_users_text(days=7, limit=15)
        await message.answer(top_users, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Top users command error: {e}")
        await message.answer(f"❌ Ошибка получения топ пользователей: {str(e)}")


@router.message(Command("errors"))
async def errors_summary_command(message: Message):
    """Команда отчета об ошибках (только для админов)"""

    # Список ID администраторов (замените на реальные ID)
    admin_ids = {123456789, 987654321}  # Добавьте реальные ID админов

    if message.from_user.id not in admin_ids:
        await message.answer("⛔ Эта команда доступна только администраторам.")
        return

    try:
        # Получаем отчет об ошибках за неделю
        errors_report = analytics_service.get_error_summary(days=7)
        await message.answer(errors_report, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Errors summary command error: {e}")
        await message.answer(f"❌ Ошибка получения отчета об ошибках: {str(e)}")


@router.message(Command("mystats"))
async def my_stats_command(message: Message):
    """Команда персональной статистики пользователя"""

    try:
        user_id = message.from_user.id

        # Получаем статистику пользователя за месяц
        user_stats = analytics_service.get_user_stats_text(user_id=user_id, days=30)
        await message.answer(user_stats, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"My stats command error: {e}")
        await message.answer(f"❌ Ошибка получения вашей статистики: {str(e)}")


@router.message(Command("cleanup"))
async def cleanup_logs_command(message: Message):
    """Команда очистки старых логов (только для админов)"""

    # Список ID администраторов (замените на реальные ID)
    admin_ids = {123456789, 987654321}  # Добавьте реальные ID админов

    if message.from_user.id not in admin_ids:
        await message.answer("⛔ Эта команда доступна только администраторам.")
        return

    try:
        # Проверяем аргументы команды
        command_args = message.text.split()
        days_to_keep = 90  # По умолчанию 90 дней

        if len(command_args) > 1:
            try:
                days_to_keep = int(command_args[1])
                if days_to_keep < 7:
                    await message.answer("❌ Минимальный период сохранения: 7 дней")
                    return
                if days_to_keep > 365:
                    await message.answer("❌ Максимальный период сохранения: 365 дней")
                    return
            except ValueError:
                await message.answer(
                    "❌ Неверный формат дней. Используйте: /cleanup [дни]"
                )
                return

        # Показываем предупреждение
        loading_msg = await message.answer(
            f"🧹 Очистка логов старше {days_to_keep} дней...\n"
            "⏳ Это может занять несколько секунд"
        )

        # Выполняем очистку
        cleanup_report = analytics_service.cleanup_old_logs(days_to_keep=days_to_keep)

        # Удаляем сообщение о загрузке
        await loading_msg.delete()

        # Отправляем отчет
        await message.answer(cleanup_report, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Cleanup command error: {e}")
        await message.answer(f"❌ Ошибка очистки логов: {str(e)}")


@router.message(Command("dbinfo"))
async def database_info_command(message: Message):
    """Команда информации о базе данных (только для админов)"""

    # Список ID администраторов (замените на реальные ID)
    admin_ids = {123456789, 987654321}  # Добавьте реальные ID админов

    if message.from_user.id not in admin_ids:
        await message.answer("⛔ Эта команда доступна только администраторам.")
        return

    try:
        # Получаем информацию о базе данных
        db_info = analytics_service.get_database_info_text()
        await message.answer(db_info, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Database info command error: {e}")
        await message.answer(f"❌ Ошибка получения информации о базе: {str(e)}")


@router.message(Command("autocleanup"))
async def auto_cleanup_command(message: Message):
    """Команда автоматической очистки по размеру (только для админов)"""

    # Список ID администраторов (замените на реальные ID)
    admin_ids = {123456789, 987654321}  # Добавьте реальные ID админов

    if message.from_user.id not in admin_ids:
        await message.answer("⛔ Эта команда доступна только администраторам.")
        return

    try:
        # Проверяем аргументы команды
        command_args = message.text.split()
        max_size_mb = 100  # По умолчанию 100 MB

        if len(command_args) > 1:
            try:
                max_size_mb = float(command_args[1])
                if max_size_mb < 10:
                    await message.answer("❌ Минимальный размер: 10 MB")
                    return
                if max_size_mb > 1000:
                    await message.answer("❌ Максимальный размер: 1000 MB")
                    return
            except ValueError:
                await message.answer(
                    "❌ Неверный формат размера. Используйте: /autocleanup [размер_MB]"
                )
                return

        # Показываем статус
        loading_msg = await message.answer(
            "🤖 Проверяем размер базы и выполняем автоочистку..."
        )

        # Выполняем автоочистку
        cleanup_report = analytics_service.auto_cleanup_by_size(max_size_mb=max_size_mb)

        # Удаляем сообщение о загрузке
        await loading_msg.delete()

        # Отправляем отчет
        await message.answer(cleanup_report, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Auto cleanup command error: {e}")
        await message.answer(f"❌ Ошибка автоочистки: {str(e)}")


# ---------- RNU Validation Command ----------
@router.message(Command("rnu"))
async def cmd_rnu_validation(message: Message):
    """
    Команда /rnu для валидации поставщика через RNU реестр

    Использование:
    /rnu <БИН>

    Где БИН - 12-значный номер поставщика
    """
    user_id = message.from_user.id

    try:
        # Проверяем API ключ и права доступа
        api_key = await require_api_key_and_log_usage(message, "rnu", cost=1)
        if not api_key:
            return

        # Парсим аргументы команды
        command_args = message.text.split()

        if len(command_args) != 2:
            await message.answer(
                "❌ Неверный формат команды!\n\n"
                "📋 Использование: `/rnu <БИН>`\n"
                "📝 Пример: `/rnu 123456789012`\n\n"
                "БИН должен содержать ровно 12 цифр.",
                parse_mode="Markdown",
            )
            return

        supplier_bin = command_args[1].strip()

        # Валидация БИН формата
        if not re.match(r"^\d{12}$", supplier_bin):
            await message.answer(
                "❌ Некорректный формат БИН!\n\n"
                "БИН должен содержать ровно 12 цифр без пробелов и других символов.\n"
                "📝 Пример: `123456789012`",
                parse_mode="Markdown",
            )
            return

        # Показываем индикатор загрузки
        loading_msg = await message.answer("🔍 Проверяем БИН в реестре RNU...")

        # Вызываем RNU API через risk-engine
        risk_engine_url = "http://risk-engine:8000"  # Docker service name
        rnu_url = f"{risk_engine_url}/validate_rnu/{supplier_bin}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(rnu_url)

                # Удаляем индикатор загрузки
                await loading_msg.delete()

                if response.status_code == 200:
                    result = response.json()

                    # Форматируем результат
                    status_icon = "🔴" if result["is_blocked"] else "🟢"
                    status_text = (
                        "Заблокирован" if result["is_blocked"] else "Не заблокирован"
                    )
                    source_text = "кэш" if result["source"] == "cache" else "API"

                    # Парсим дату валидации
                    from datetime import datetime

                    try:
                        validated_dt = datetime.fromisoformat(
                            result["validated_at"].replace("Z", "+00:00")
                        )
                        validated_str = validated_dt.strftime("%d.%m.%Y %H:%M")
                    except Exception:
                        validated_str = result["validated_at"]

                    response_text = (
                        f"📊 **Результат проверки RNU**\n\n"
                        f"🏢 **БИН:** `{supplier_bin}`\n"
                        f"{status_icon} **Статус:** {status_text}\n"
                        f"📅 **Проверено:** {validated_str}\n"
                        f"💾 **Источник:** {source_text}\n\n"
                    )

                    if result["is_blocked"]:
                        response_text += (
                            "⚠️ **Внимание!** Поставщик находится в реестре недобросовестных участников (RNU).\n"
                            "Рекомендуется проявить осторожность при работе с данным контрагентом."
                        )
                    else:
                        response_text += (
                            "✅ Поставщик не найден в реестре недобросовестных участников.\n"
                            "Это не гарантирует отсутствие рисков, но является положительным фактором."
                        )

                    await message.answer(response_text, parse_mode="Markdown")

                    # Логируем использование биллинга
                    await billing_service.log_usage(
                        user_id=user_id, service="rnu_validation", requests=1, cost=1
                    )

                elif response.status_code == 400:
                    error_detail = response.json().get("detail", "Неизвестная ошибка")
                    await message.answer(f"❌ Ошибка валидации: {error_detail}")

                elif response.status_code == 429:
                    await message.answer(
                        "⏳ Превышен лимит запросов к RNU API.\n"
                        "Попробуйте повторить запрос через несколько минут."
                    )

                elif response.status_code == 503:
                    await message.answer(
                        "🔧 Сервис RNU временно недоступен.\n"
                        "Попробуйте повторить запрос позже."
                    )

                else:
                    logger.error(
                        f"RNU API returned unexpected status: {response.status_code}"
                    )
                    await message.answer(
                        "❌ Ошибка при обращении к сервису RNU.\n"
                        "Попробуйте повторить запрос позже."
                    )

            except httpx.TimeoutException:
                await loading_msg.delete()
                await message.answer(
                    "⏰ Время ожидания ответа от сервиса истекло.\n"
                    "Попробуйте повторить запрос позже."
                )

            except httpx.RequestError as e:
                logger.error(f"RNU request error: {e}")
                await loading_msg.delete()
                await message.answer(
                    "❌ Ошибка подключения к сервису RNU.\n"
                    "Проверьте подключение к интернету и повторите попытку."
                )

    except Exception as e:
        logger.error(f"RNU command error for user {user_id}: {e}")
        await message.answer(
            "❌ Произошла внутренняя ошибка.\n"
            "Обратитесь в службу поддержки или повторите попытку позже."
        )
