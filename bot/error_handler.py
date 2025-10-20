"""
Централизованная система обработки ошибок для бота ZakupAI
"""

import logging
import traceback
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from config import config

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseMiddleware):
    """Middleware для централизованной обработки ошибок"""

    async def __call__(
        self, handler, event: TelegramObject, data: dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as e:
            await self.handle_error(event, e)
            # Не перебрасываем исключение, чтобы бот продолжал работать
            return None

    async def handle_error(self, event: TelegramObject, error: Exception):
        """Централизованная обработка ошибок"""

        # Извлекаем информацию о пользователе если возможно
        user_id = None
        username = "unknown"

        if hasattr(event, "from_user") and event.from_user:
            user_id = event.from_user.id
            username = event.from_user.username or "no_username"

        # Безопасное логирование ошибки
        error_type = type(error).__name__
        error_msg = str(error)[:200]  # Ограничиваем длину сообщения об ошибке

        logger.error(
            f"Unhandled error for user {user_id} (@{username}): {error_type}: {error_msg}"
        )

        # В dev режиме логируем полный traceback
        if config.security.environment == "development":
            logger.error(f"Full traceback: {traceback.format_exc()}")

        # Отправляем пользователю дружелюбное сообщение об ошибке
        if hasattr(event, "answer"):
            try:
                await event.answer(
                    "❌ Произошла техническая ошибка. Попробуйте позже или обратитесь в поддержку.\n"
                    f"Код ошибки: {error_type}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to send error message to user: {type(e).__name__}"
                )


class SecurityException(Exception):
    """Исключение для нарушений безопасности"""

    pass


class RateLimitException(Exception):
    """Исключение для превышения rate limit"""

    pass


class ValidationException(Exception):
    """Исключение для ошибок валидации входных данных"""

    pass


def log_security_event(event_type: str, user_id: int, details: dict = None):
    """Логирование событий безопасности"""
    details_str = ""
    if details:
        # Безопасное логирование деталей без секретов
        safe_details = {}
        for key, value in details.items():
            if key.lower() in ["api_key", "password", "token", "secret"]:
                safe_details[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > 100:
                safe_details[key] = value[:100] + "..."
            else:
                safe_details[key] = value
        details_str = f" - {safe_details}"

    logger.warning(f"SECURITY_EVENT: {event_type} by user {user_id}{details_str}")


def handle_api_error(error: Exception, context: str = "") -> str:
    """Безопасная обработка ошибок API с возвратом пользовательского сообщения"""
    error_type = type(error).__name__

    # Логируем техническую информацию
    logger.error(f"API error in {context}: {error_type}")

    # Возвращаем пользователю понятное сообщение в зависимости от типа ошибки
    if "timeout" in str(error).lower() or "TimeoutError" in error_type:
        return "⏱️ Превышено время ожидания. Попробуйте позже."
    elif "connection" in str(error).lower() or "ConnectionError" in error_type:
        return "🌐 Проблемы с подключением. Проверьте интернет соединение."
    elif "unauthorized" in str(error).lower() or error_type == "Unauthorized":
        return "🔑 Проблема с авторизацией. Проверьте API ключ."
    elif "rate limit" in str(error).lower():
        return "⏱️ Превышен лимит запросов. Подождите немного."
    else:
        return f"❌ Техническая ошибка. Код: {error_type}"


async def validate_user_input(
    text: str, max_length: int = 1000, required: bool = True
) -> str | None:
    """Централизованная валидация пользовательского ввода"""

    if not text:
        if required:
            raise ValidationException("Требуется ввод текста")
        return None

    if not isinstance(text, str):
        raise ValidationException("Ввод должен быть текстом")

    if len(text) > max_length:
        raise ValidationException(
            f"Текст слишком длинный (максимум {max_length} символов)"
        )

    # Проверка на потенциально опасные символы
    dangerous_chars = ["<script", "javascript:", "data:", "vbscript:"]
    text_lower = text.lower()

    for char in dangerous_chars:
        if char in text_lower:
            log_security_event("SUSPICIOUS_INPUT", 0, {"input": text[:50]})
            raise SecurityException("Обнаружен потенциально опасный ввод")

    return text.strip()


async def check_user_permissions(user_id: int, action: str) -> bool:
    """Проверка разрешений пользователя (расширяемая функция)"""

    # Базовые проверки
    if user_id <= 0:
        log_security_event("INVALID_USER_ID", user_id, {"action": action})
        return False

    # Здесь можно добавить дополнительные проверки:
    # - блокировка пользователей
    # - проверка премиум статуса
    # - региональные ограничения

    return True
