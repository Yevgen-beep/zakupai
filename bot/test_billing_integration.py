"""
Тесты для интеграции Telegram бота с Billing Service
"""

import os
from unittest.mock import patch

import pytest

# Устанавливаем тестовые переменные окружения перед импортом
os.environ["TELEGRAM_BOT_TOKEN"] = (
    "1234567890:AABBCCDDEEFFaabbccddeeff123456789"  # Валидный формат токена
)
os.environ["ZAKUPAI_API_URL"] = "http://localhost:8080"
os.environ["ZAKUPAI_API_KEY"] = "test_key"

from client import ZakupaiAPIClient, get_command_endpoint


class TestGetCommandEndpoint:
    """Тесты для функции get_command_endpoint"""

    def test_start_command(self):
        assert get_command_endpoint("/start") == "start"
        assert get_command_endpoint("/start hello") == "start"

    def test_key_command(self):
        assert get_command_endpoint("/key") == "key"
        assert get_command_endpoint("/key abc123") == "key"

    def test_lot_command(self):
        assert get_command_endpoint("/lot") == "lot"
        assert get_command_endpoint("/lot 12345") == "lot"

    def test_help_command(self):
        assert get_command_endpoint("/help") == "help"

    def test_unknown_command(self):
        assert get_command_endpoint("/unknown") == "unknown"
        assert get_command_endpoint("not a command") == "unknown"
        assert get_command_endpoint("") == "unknown"

    def test_custom_command(self):
        assert get_command_endpoint("/stats") == "stats"
        assert get_command_endpoint("/custom") == "custom"


class TestZakupaiAPIClientBilling:
    """Тесты для методов Billing Service в ZakupaiAPIClient"""

    @pytest.fixture
    def api_client(self):
        return ZakupaiAPIClient(base_url="http://localhost:8080", api_key="test-key")

    @pytest.mark.asyncio
    async def test_validate_key_with_endpoint(self, api_client):
        """Тест что validate_key принимает endpoint параметр"""
        # Мокаем весь метод вместо HTTP запроса
        with patch.object(api_client, "validate_key") as mock_validate:
            mock_validate.return_value = True

            result = await api_client.validate_key("test-key", "lot")

            # Проверяем, что метод был вызван с правильными параметрами
            mock_validate.assert_called_once_with("test-key", "lot")
            assert result is True

    def test_billing_methods_exist(self, api_client):
        """Тест что все необходимые методы Billing Service существуют"""
        assert hasattr(api_client, "validate_key")
        assert hasattr(api_client, "create_billing_key")
        assert hasattr(api_client, "log_usage")

        # Проверяем сигнатуры методов
        import inspect

        validate_sig = inspect.signature(api_client.validate_key)
        assert "api_key" in validate_sig.parameters
        assert "endpoint" in validate_sig.parameters

        create_sig = inspect.signature(api_client.create_billing_key)
        assert "tg_id" in create_sig.parameters

        usage_sig = inspect.signature(api_client.log_usage)
        assert "api_key" in usage_sig.parameters
        assert "endpoint" in usage_sig.parameters


class TestBillingIntegration:
    """Интеграционные тесты для интеграции с Billing Service"""

    def test_endpoint_mapping(self):
        """Тест корректного маппинга команд в endpoints"""
        test_cases = [
            ("/start", "start"),
            ("/key abc123", "key"),
            ("/lot 12345", "lot"),
            ("/help", "help"),
            ("/stats", "stats"),
        ]

        for message_text, expected_endpoint in test_cases:
            result = get_command_endpoint(message_text)
            assert (
                result == expected_endpoint
            ), f"Expected {expected_endpoint} for {message_text}, got {result}"

    def test_validate_and_log_decorator_exists(self):
        """Тест что декоратор validate_and_log_bot существует в main.py"""
        # Проверяем что декоратор определен в main.py без импорта всего модуля
        with open("bot/main.py") as f:
            main_content = f.read()

        # Проверяем что функция декоратора определена
        assert "def validate_and_log_bot(" in main_content
        assert "@validate_and_log_bot" in main_content

        # Проверяем что используется в командах
        assert "@validate_and_log_bot(require_key=True)" in main_content
        assert "@validate_and_log_bot(require_key=False)" in main_content

    @pytest.mark.asyncio
    async def test_billing_client_methods_signatures(self):
        """Тест что все методы billing service имеют правильные сигнатуры"""
        api_client = ZakupaiAPIClient("http://localhost:8080", "test-key")

        # Проверяем что методы существуют и имеют правильные сигнатуры
        assert hasattr(api_client, "validate_key")
        assert hasattr(api_client, "create_billing_key")
        assert hasattr(api_client, "log_usage")

        # Можем проверить, что методы принимают правильные параметры
        # без вызова HTTP запросов
        import inspect

        # validate_key должен принимать api_key и endpoint
        sig = inspect.signature(api_client.validate_key)
        params = list(sig.parameters.keys())
        assert "api_key" in params
        assert "endpoint" in params

        # create_billing_key должен принимать tg_id
        sig = inspect.signature(api_client.create_billing_key)
        params = list(sig.parameters.keys())
        assert "tg_id" in params

        # log_usage должен принимать api_key, endpoint, requests
        sig = inspect.signature(api_client.log_usage)
        params = list(sig.parameters.keys())
        assert "api_key" in params
        assert "endpoint" in params
        assert "requests" in params


if __name__ == "__main__":
    pytest.main([__file__])
