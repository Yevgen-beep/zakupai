#!/usr/bin/env python3
"""
Тестовый скрипт для проверки GraphQL поиска по слову "лак"
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Добавляем путь к модулю бота
sys.path.append(str(Path(__file__).parent / "bot"))

from goszakup_graphql import GoszakupGraphQLClient, format_search_results


async def test_graphql_search():
    """Тестирование GraphQL поиска"""

    # Получаем токен из переменной окружения
    token = os.getenv("GOSZAKUP_TOKEN")
    if not token:
        print("❌ Ошибка: Не найден токен GOSZAKUP_TOKEN в переменных окружения")
        print("Установите токен: export GOSZAKUP_TOKEN='ваш_токен'")
        return

    print("🔍 Тестируем поиск по GraphQL API")
    print("=" * 60)

    client = GoszakupGraphQLClient(token)

    # Тестовые запросы
    test_keywords = ["лак", "уголь", "мебель", "бумага", "молоко"]

    for keyword in test_keywords:
        print(f"\n🔍 Поиск по ключевому слову: '{keyword}'")
        print("-" * 40)

        try:
            # Тест GraphQL поиска
            results = await client.search_lots(keyword, limit=3, use_graphql=True)

            if results:
                print(f"✅ GraphQL: Найдено {len(results)} результатов")
                formatted = format_search_results(results)
                print(formatted[:500] + "..." if len(formatted) > 500 else formatted)
            else:
                print("⚠️ GraphQL: Результаты не найдены")

                # Попробуем REST fallback
                print("\n🔄 Пробуем REST fallback...")
                try:
                    rest_results = await client.search_lots(
                        keyword, limit=3, use_graphql=False
                    )
                    if rest_results:
                        print(f"✅ REST: Найдено {len(rest_results)} результатов")
                        formatted = format_search_results(rest_results)
                        print(
                            formatted[:500] + "..."
                            if len(formatted) > 500
                            else formatted
                        )
                    else:
                        print("⚠️ REST: Результаты тоже не найдены")
                except Exception as e:
                    print(f"❌ REST fallback ошибка: {e}")

        except Exception as e:
            print(f"❌ Ошибка поиска: {e}")

        print("\n" + "=" * 60)


def test_query_structure():
    """Тестирование структуры GraphQL запроса"""
    print("\n📋 Тестовая структура GraphQL запроса:")
    print("-" * 50)

    query = """
    query SearchLots($filter: LotsFiltersInput) {
      Lots(filter: $filter) {
        id
        lotNumber
        nameRu
        descriptionRu
        amount
        count
        customerNameRu
        customerBin
        trdBuyNumberAnno
        TrdBuy {
          id
          nameRu
          numberAnno
          orgNameRu
          orgBin
          RefTradeMethods {
            nameRu
          }
        }
        RefLotsStatus {
          nameRu
        }
      }
    }
    """

    variables = {"filter": {"nameRu": "лак", "nameDescriptionRu": "лак"}}

    payload = {"query": query, "variables": variables}

    print("GraphQL Query:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    print("\n🔗 URL: https://ows.goszakup.gov.kz/v2/graphql")
    print("🔑 Headers:")
    print("  - Authorization: Bearer <YOUR_TOKEN>")
    print("  - Content-Type: application/json")
    print("  - User-Agent: ZakupAI-Bot/1.0")


def show_comparison():
    """Сравнение GraphQL vs REST подходов"""
    print("\n📊 Сравнение GraphQL v2 vs REST v3:")
    print("=" * 60)

    print("🚀 GraphQL v2 API (Приоритет):")
    print("  ✅ Гибкая фильтрация через LotsFiltersInput")
    print("  ✅ Точные поля из схемы: nameRu, nameDescriptionRu")
    print("  ✅ Связанные данные: TrdBuy, RefLotsStatus, RefTradeMethods")
    print("  ✅ Минимальный трафик - только нужные поля")
    print("  ✅ Типизированные запросы")

    print("\n🔄 REST v3 API (Fallback):")
    print("  ⚠️ Менее гибкая фильтрация")
    print("  ⚠️ Больше ненужных данных")
    print("  ⚠️ Ограниченные возможности поиска")
    print("  ✅ Простота использования")
    print("  ✅ Стабильность как fallback")


def integration_guide():
    """Руководство по интеграции"""
    print("\n🔧 Руководство по интеграции:")
    print("=" * 60)

    print("1. Установка зависимостей:")
    print("   pip install aiohttp")

    print("\n2. Импорт модуля:")
    print(
        "   from bot.goszakup_graphql import GoszakupGraphQLClient, format_search_results"
    )

    print("\n3. Инициализация клиента:")
    print("   client = GoszakupGraphQLClient(token='your_token')")

    print("\n4. Поиск лотов:")
    print("   results = await client.search_lots('лак', limit=10)")
    print("   formatted_text = format_search_results(results)")

    print("\n5. Для Telegram бота:")
    print("   await bot.send_message(chat_id, formatted_text, parse_mode='Markdown')")

    print("\n6. Переменные окружения:")
    print("   export GOSZAKUP_TOKEN='ваш_токен_api'")


async def main():
    """Основная функция для тестирования"""
    print("🤖 ZakupAI - GraphQL Search Тестирование")
    print("=" * 60)

    show_comparison()
    test_query_structure()
    integration_guide()

    if os.getenv("GOSZAKUP_TOKEN"):
        print("\n🔍 Запуск тестов поиска...")
        await test_graphql_search()
    else:
        print("\n⚠️ Токен не установлен - пропускаем живые тесты")
        print("Для тестирования установите: export GOSZAKUP_TOKEN='ваш_токен'")


if __name__ == "__main__":
    asyncio.run(main())
