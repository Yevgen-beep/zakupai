from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.enums import ChatType
from aiogram.types import Chat, Message, User

# Импортируем функции из main.py для тестирования
from bot.main import (
    analyze_lot_pipeline,
    command_help_handler,
    command_key_handler,
    command_lot_handler,
    command_start_handler,
    extract_lot_id,
    format_lot_analysis,
)


class TestCommandHandlers:
    """Тесты обработчиков команд бота"""

    @pytest.fixture
    def mock_message(self):
        """Фикстура для создания mock сообщения"""
        user = User(
            id=123456789,
            is_bot=False,
            first_name="Test",
            last_name="User",
            username="testuser",
        )
        chat = Chat(id=123456789, type=ChatType.PRIVATE)

        message = MagicMock(spec=Message)
        message.from_user = user
        message.chat = chat
        message.answer = AsyncMock()

        return message

    @pytest.mark.asyncio
    async def test_command_start_no_api_key(self, mock_message):
        """Тест команды /start без API ключа"""
        with patch("bot.main.get_api_key", return_value=None):
            await command_start_handler(mock_message)

            # Проверяем, что отправлено сообщение с просьбой установить API ключ
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "API ключ" in call_args
            assert "/key" in call_args

    @pytest.mark.asyncio
    async def test_command_start_with_api_key(self, mock_message):
        """Тест команды /start с существующим API ключом"""
        with patch("bot.main.get_api_key", return_value="existing-api-key"):
            await command_start_handler(mock_message)

            # Проверяем, что отправлено приветственное сообщение
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "Добро пожаловать" in call_args
            assert "/lot" in call_args

    @pytest.mark.asyncio
    async def test_command_key_invalid_format(self, mock_message):
        """Тест команды /key с неправильным форматом"""
        mock_message.text = "/key"  # Без параметров

        await command_key_handler(mock_message)

        # Проверяем сообщение об ошибке
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Неверный формат" in call_args

    @pytest.mark.asyncio
    async def test_command_key_too_short(self, mock_message):
        """Тест команды /key со слишком коротким ключом"""
        mock_message.text = "/key abc"  # Слишком короткий ключ

        await command_key_handler(mock_message)

        # Проверяем сообщение об ошибке
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "слишком короткий" in call_args

    @pytest.mark.asyncio
    async def test_command_key_success(self, mock_message):
        """Тест успешного сохранения API ключа"""
        mock_message.text = "/key valid-api-key-12345"

        mock_client = AsyncMock()
        mock_client.health_check.return_value = {"status": "ok"}

        with (
            patch("bot.main.save_api_key", return_value=True),
            patch("bot.main.ZakupaiAPIClient", return_value=mock_client),
        ):
            await command_key_handler(mock_message)

            # Проверяем сообщение об успехе
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "сохранён и проверен" in call_args

    @pytest.mark.asyncio
    async def test_command_lot_no_api_key(self, mock_message):
        """Тест команды /lot без API ключа"""
        mock_message.text = "/lot 12345"

        with patch("bot.main.get_api_key", return_value=None):
            await command_lot_handler(mock_message)

            # Проверяем сообщение о необходимости API ключа
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "API ключ" in call_args

    @pytest.mark.asyncio
    async def test_command_lot_no_id(self, mock_message):
        """Тест команды /lot без ID лота"""
        mock_message.text = "/lot"

        with patch("bot.main.get_api_key", return_value="api-key"):
            await command_lot_handler(mock_message)

            # Проверяем сообщение об ошибке
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "Укажи ID" in call_args

    @pytest.mark.asyncio
    async def test_command_lot_success(self, mock_message):
        """Тест успешного анализа лота"""
        mock_message.text = "/lot 12345"

        mock_analysis_result = {
            "lot_id": "12345",
            "tldr": {"title": "Тест", "price": 1000000},
            "risk": {"score": 0.3, "level": "low"},
            "finance": {"vat_amount": 120000},
            "error": None,
        }

        with (
            patch("bot.main.get_api_key", return_value="api-key"),
            patch("bot.main.analyze_lot_pipeline", return_value=mock_analysis_result),
            patch("bot.main.ZakupaiAPIClient"),
        ):
            await command_lot_handler(mock_message)

            # Проверяем, что было два вызова answer: "Анализирую..." и результат
            assert mock_message.answer.call_count == 2

    @pytest.mark.asyncio
    async def test_command_help(self, mock_message):
        """Тест команды /help"""
        await command_help_handler(mock_message)

        # Проверяем справочное сообщение
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "ZakupAI Telegram Bot" in call_args
        assert "/start" in call_args
        assert "/lot" in call_args


class TestUtilityFunctions:
    """Тесты вспомогательных функций"""

    def test_extract_lot_id_digit(self):
        """Тест извлечения ID из числа"""
        assert extract_lot_id("12345") == "12345"
        assert extract_lot_id("999") == "999"

    def test_extract_lot_id_from_url(self):
        """Тест извлечения ID из URL"""
        test_cases = [
            ("https://goszakup.gov.kz/ru/announce/index/12345", "12345"),
            ("http://example.com/lot/67890", "67890"),
            ("https://site.com?lot_id=11111", "11111"),
            ("https://site.com?id=22222", "22222"),
            ("invalid-string", ""),
        ]

        for input_str, expected in test_cases:
            assert extract_lot_id(input_str) == expected

    @pytest.mark.asyncio
    async def test_analyze_lot_pipeline_success(self):
        """Тест успешного пайплайна анализа"""
        mock_client = AsyncMock()
        mock_client.get_tldr.return_value = {
            "lot_id": "12345",
            "title": "Тест",
            "price": 1000000,
        }
        mock_client.get_risk_score.return_value = {"lot_id": "12345", "score": 0.3}
        mock_client.calculate_vat.return_value = {"vat_amount": 120000}

        result = await analyze_lot_pipeline(mock_client, "12345")

        assert result["lot_id"] == "12345"
        assert result["tldr"]["title"] == "Тест"
        assert result["risk"]["score"] == 0.3
        assert result["finance"]["vat_amount"] == 120000
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_analyze_lot_pipeline_error(self):
        """Тест пайплайна анализа с ошибкой"""
        mock_client = AsyncMock()
        mock_client.get_tldr.side_effect = Exception("TL;DR error")
        mock_client.get_risk_score.return_value = {"score": 0.5}

        result = await analyze_lot_pipeline(mock_client, "12345")

        assert result["lot_id"] == "12345"
        assert result["error"] is not None
        assert "TL;DR error" in result["error"]

    def test_format_lot_analysis_with_error(self):
        """Тест форматирования результата с ошибкой"""
        result = {"lot_id": "12345", "error": "Test error"}

        formatted = format_lot_analysis(result)

        assert "12345" in formatted
        assert "Test error" in formatted
        assert "Ошибка анализа" in formatted

    def test_format_lot_analysis_success(self):
        """Тест форматирования успешного результата"""
        result = {
            "lot_id": "12345",
            "tldr": {"title": "Тестовый лот", "price": 1000000, "customer": "ТОО Тест"},
            "risk": {"score": 0.3, "explanation": "Низкий риск"},
            "finance": {
                "amount_without_vat": 892857,
                "vat_amount": 107143,
                "total_with_vat": 1000000,
            },
            "error": None,
        }

        formatted = format_lot_analysis(result)

        assert "12345" in formatted
        assert "Тестовый лот" in formatted
        assert "1000000" in formatted
        assert "ТОО Тест" in formatted
        assert "🟢 Низкий" in formatted  # Low risk emoji
        assert "Низкий риск" in formatted
        assert "892857" in formatted


class TestBotIntegration:
    """Интеграционные тесты бота"""

    @pytest.mark.asyncio
    async def test_full_lot_analysis_workflow(self):
        """Тест полного workflow анализа лота"""
        # Создаём mock сообщения
        user = User(id=123456789, is_bot=False, first_name="Test", username="testuser")
        chat = Chat(id=123456789, type=ChatType.PRIVATE)

        message = MagicMock(spec=Message)
        message.from_user = user
        message.chat = chat
        message.text = "/lot 12345"
        message.answer = AsyncMock()

        # Mock API клиента и его методы
        mock_client = AsyncMock()
        mock_client.get_tldr.return_value = {
            "lot_id": "12345",
            "title": "Интеграционный тест",
            "price": 500000,
        }
        mock_client.get_risk_score.return_value = {
            "lot_id": "12345",
            "score": 0.5,
            "explanation": "Средний риск",
        }
        mock_client.calculate_vat.return_value = {
            "vat_amount": 60000,
            "total_with_vat": 500000,
        }

        # Mock функций БД
        with (
            patch("bot.main.get_api_key", return_value="test-api-key"),
            patch("bot.main.ZakupaiAPIClient", return_value=mock_client),
        ):
            await command_lot_handler(message)

            # Проверяем вызовы
            assert message.answer.call_count == 2  # "Анализирую..." + результат

            # Проверяем, что API методы были вызваны
            mock_client.get_tldr.assert_called_once_with("12345")
            mock_client.get_risk_score.assert_called_once_with("12345")
            mock_client.calculate_vat.assert_called_once_with(500000)

            # Проверяем содержимое последнего ответа
            final_response = message.answer.call_args_list[-1][0][0]
            assert "12345" in final_response
            assert "Интеграционный тест" in final_response
            assert "🟡 Средний" in final_response  # Medium risk emoji


class TestErrorHandling:
    """Тесты обработки ошибок"""

    @pytest.fixture
    def mock_message(self):
        """Фикстура для mock сообщения"""
        user = User(id=123456789, is_bot=False, first_name="Test", username="testuser")
        chat = Chat(id=123456789, type=ChatType.PRIVATE)

        message = MagicMock(spec=Message)
        message.from_user = user
        message.chat = chat
        message.answer = AsyncMock()

        return message

    @pytest.mark.asyncio
    async def test_database_error_handling(self, mock_message):
        """Тест обработки ошибок БД"""
        mock_message.text = "/key valid-api-key-12345"

        with patch("bot.main.save_api_key", side_effect=Exception("DB Error")):
            await command_key_handler(mock_message)

            # Проверяем сообщение об ошибке
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "Ошибка сохранения" in call_args

    @pytest.mark.asyncio
    async def test_api_error_handling(self, mock_message):
        """Тест обработки ошибок API"""
        mock_message.text = "/lot 12345"

        with (
            patch("bot.main.get_api_key", return_value="api-key"),
            patch("bot.main.analyze_lot_pipeline", side_effect=Exception("API Error")),
        ):
            await command_lot_handler(mock_message)

            # Проверяем, что было два вызова (включая сообщение об ошибке)
            assert mock_message.answer.call_count == 2

            # Последний вызов должен содержать сообщение об ошибке
            final_response = mock_message.answer.call_args_list[-1][0][0]
            assert "Ошибка анализа" in final_response


@pytest.mark.asyncio
async def test_lifespan_context():
    """Тест контекста жизненного цикла приложения"""
    from bot.main import lifespan_context

    with patch("bot.main.init_db") as mock_init_db:
        async with lifespan_context():
            # Проверяем, что БД была инициализирована
            mock_init_db.assert_called_once()

        # После выхода из контекста должно быть логирование завершения
        # (проверяем через mock логгера если нужно)
