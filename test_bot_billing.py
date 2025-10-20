#!/usr/bin/env python3
"""
Тест интеграции Telegram Bot с Billing Service
Проверяет, что все команды правильно передают endpoint в Billing
"""

import asyncio

from bot.client import ZakupaiAPIClient


async def test_billing_integration():
    """
    Тестирует основные функции Billing Service
    """
    # Создаем клиент для тестирования
    client = ZakupaiAPIClient(
        base_url="http://localhost:8080", api_key="test-key-12345"
    )

    print("🧪 Тестирование интеграции Bot ↔ Billing Service\n")

    # Тест 1: Создание API ключа
    print("1️⃣ Тестируем создание API ключа...")
    try:
        api_key = await client.create_billing_key(tg_id=12345, email="test@example.com")
        if api_key:
            print(f"   ✅ Ключ создан: {api_key[:12]}...")
        else:
            print("   ❌ Ключ не создан")
    except Exception as e:
        print(f"   ❌ Ошибка создания ключа: {e}")

    # Тест 2: Валидация ключа для разных endpoints
    endpoints_to_test = ["start", "key", "lot", "help", "stats", "unknown"]
    print(f"\n2️⃣ Тестируем валидацию для endpoints: {', '.join(endpoints_to_test)}")

    test_key = "test-api-key-123456789"

    for endpoint in endpoints_to_test:
        try:
            is_valid = await client.validate_key(test_key, endpoint)
            status = "✅ valid" if is_valid else "❌ invalid"
            print(f"   endpoint='{endpoint}' → {status}")
        except Exception as e:
            print(f"   endpoint='{endpoint}' → ❌ error: {e}")

    # Тест 3: Логирование использования
    print("\n3️⃣ Тестируем логирование использования...")
    for endpoint in ["start", "lot", "help"]:
        try:
            logged = await client.log_usage(test_key, endpoint, requests=1)
            status = "✅ logged" if logged else "❌ not logged"
            print(f"   usage '{endpoint}' → {status}")
        except Exception as e:
            print(f"   usage '{endpoint}' → ❌ error: {e}")

    print("\n🎯 Тест завершен!")


def test_command_endpoint_extraction():
    """
    Тестирует функцию извлечения endpoint из команд
    """
    from bot.main import get_command_endpoint

    test_cases = [
        ("/start", "start"),
        ("/key abc123", "key"),
        ("/lot 12345", "lot"),
        ("/help", "help"),
        ("/stats", "stats"),
        ("/unknown_command", "unknown_command"),
        ("не команда", "unknown"),
    ]

    print("\n🧪 Тестирование извлечения endpoint из команд:")

    for input_text, expected in test_cases:
        result = get_command_endpoint(input_text)
        status = "✅" if result == expected else "❌"
        print(f"   '{input_text}' → '{result}' {status}")


if __name__ == "__main__":
    print("=" * 50)
    print("🤖 ZakupAI Bot - Billing Integration Test")
    print("=" * 50)

    # Тест извлечения endpoint (синхронный)
    test_command_endpoint_extraction()

    # Тест интеграции с Billing Service (асинхронный)
    try:
        asyncio.run(test_billing_integration())
    except KeyboardInterrupt:
        print("\n⚠️ Тест прерван пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка теста: {e}")

    print("\n" + "=" * 50)
