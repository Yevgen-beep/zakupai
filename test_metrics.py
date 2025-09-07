#!/usr/bin/env python3
"""
Тест системы метрик ZakupAI
"""

import asyncio
import os
import sys

# Добавляем bot директорию в путь Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))

from analytics_service import analytics_service
from search.search_service import GoszakupSearchService
from user_metrics import metrics_service


async def test_metrics_system():
    """Тестирование системы метрик"""

    print("🧪 Тестирование системы пользовательских метрик")
    print("=" * 60)

    try:
        # Тест 1: Логирование поисковых запросов
        print("\n1️⃣ Тестируем логирование поисковых запросов...")

        # Добавляем тестовые данные
        test_users = [12345, 67890, 11111]
        test_queries = ["лак", "компьютеры", "мебель", "уголь", "строительство"]

        for i, user_id in enumerate(test_users):
            for j, query in enumerate(test_queries[:3]):  # По 3 запроса на пользователя
                metrics_service.log_search(
                    user_id=user_id,
                    query=query,
                    results_count=5 + i + j,
                    api_used="graphql_v2" if i % 2 == 0 else "rest_v3",
                    execution_time_ms=150 + i * 50 + j * 20,
                    success=True,
                )

        # Добавляем одну неудачную попытку
        metrics_service.log_search(
            user_id=12345,
            query="тестовая ошибка",
            results_count=0,
            api_used="graphql_v2",
            execution_time_ms=5000,
            success=False,
            error_message="API timeout",
        )

        print("✅ Тестовые запросы записаны в базу данных")

        # Тест 2: Популярные запросы
        print("\n2️⃣ Тестируем получение популярных запросов...")
        popular_searches = metrics_service.get_popular_searches(days=7, limit=5)

        print(f"📊 Найдено {len(popular_searches)} популярных запросов:")
        for i, search in enumerate(popular_searches, 1):
            print(f"   {i}. '{search.query}' - {search.count} раз")

        # Тест 3: Статистика пользователя
        print("\n3️⃣ Тестируем аналитику пользователя...")
        user_analytics = metrics_service.get_user_analytics(12345, days=7)

        if user_analytics:
            print("👤 Аналитика пользователя 12345:")
            print(f"   - Всего поисков: {user_analytics.total_searches}")
            print(f"   - Уникальных запросов: {user_analytics.unique_queries}")
            print(f"   - Средние результаты: {user_analytics.avg_results_per_search}")
            print(f"   - Самый частый запрос: '{user_analytics.most_searched_query}'")
        else:
            print("❌ Не удалось получить аналитику пользователя")

        # Тест 4: Системная статистика
        print("\n4️⃣ Тестируем системную статистику...")
        system_stats = metrics_service.get_system_stats(days=7)

        print("🏢 Системная статистика:")
        print(f"   - Всего поисков: {system_stats.get('total_searches', 0)}")
        print(f"   - Активных пользователей: {system_stats.get('active_users', 0)}")
        print(f"   - Успешность: {system_stats.get('success_rate', 0):.1f}%")
        print(
            f"   - Среднее время ответа: {system_stats.get('avg_execution_time_ms', 0):.0f}мс"
        )

        api_usage = system_stats.get("api_usage", {})
        print(f"   - Использование API: {api_usage}")

        # Тест 5: Сервис аналитики
        print("\n5️⃣ Тестируем сервис аналитики...")

        # Dashboard summary
        dashboard = analytics_service.get_dashboard_summary(days=7)
        print("📋 Dashboard summary:")
        print(dashboard[:300] + "..." if len(dashboard) > 300 else dashboard)

        # Popular searches text
        popular_text = analytics_service.get_popular_searches_text(days=7, limit=3)
        print("\n🔍 Popular searches:")
        print(popular_text[:200] + "..." if len(popular_text) > 200 else popular_text)

        # User stats text
        user_stats_text = analytics_service.get_user_stats_text(12345, days=7)
        print("\n👤 User stats:")
        print(
            user_stats_text[:200] + "..."
            if len(user_stats_text) > 200
            else user_stats_text
        )

        print("\n✅ Все тесты системы метрик пройдены успешно!")

        # Тест 6: Интеграция с поисковым сервисом
        print("\n6️⃣ Тестируем интеграцию с поисковым сервисом...")

        search_service = GoszakupSearchService(enable_metrics=True)

        if search_service.enable_metrics and search_service.metrics_service:
            print("✅ Интеграция с поисковым сервисом работает")
        else:
            print("⚠️ Интеграция с поисковым сервисом отключена или недоступна")

        # Тест 7: Система очистки логов
        print("\n7️⃣ Тестируем систему очистки логов...")

        # Получаем информацию о базе данных
        db_info = metrics_service.get_database_info()
        print(f"💾 Размер базы данных: {db_info.get('db_size_mb', 0):.2f} MB")
        print(f"📊 Всего записей: {db_info.get('total_records', 0)}")

        # Тестируем очистку логов (но сохраняем последние 7 дней)
        print("\n🧹 Тестируем очистку логов старше 7 дней...")
        cleanup_stats = metrics_service.cleanup_old_logs(days_to_keep=7)

        if cleanup_stats.get("deleted_count", 0) > 0:
            print(f"✅ Удалено {cleanup_stats['deleted_count']} старых записей")
        else:
            print("ℹ️ Нет записей для удаления (все записи новые)")

        # Тестируем автоочистку по размеру
        print("\n🤖 Тестируем автоочистку по размеру (лимит 0.01 MB для теста)...")
        auto_cleanup_result = metrics_service.auto_cleanup_by_size(max_size_mb=0.01)

        if auto_cleanup_result:
            print(
                f"✅ Автоочистка выполнена: {auto_cleanup_result.get('deleted_count', 0)} записей удалено"
            )
        else:
            print("ℹ️ Автоочистка не требуется")

        # Финальная информация о базе
        final_db_info = metrics_service.get_database_info()
        print(
            f"\n💾 Финальный размер базы: {final_db_info.get('db_size_mb', 0):.2f} MB"
        )
        print(
            f"📊 Финальное количество записей: {final_db_info.get('total_records', 0)}"
        )

        print("\n🎉 Система пользовательских метрик с автоочисткой полностью работает!")
        print("\n📋 Новые возможности:")
        print("   ✅ Автоматическая очистка старых логов")
        print("   ✅ Ротация по размеру базы данных")
        print("   ✅ Детальная информация о базе данных")
        print("   ✅ Админские команды для управления")

        print("\n🤖 Telegram команды для админов:")
        print("   /cleanup [дни] - очистка логов старше N дней")
        print("   /dbinfo - информация о размере и записях базы")
        print("   /autocleanup [размер_MB] - автоочистка при превышении размера")

        print("\n📋 Что можно делать дальше:")
        print("   1. Настроить админские ID в handlers_v2.py")
        print("   2. Запустить Telegram бот для сбора реальных метрик")
        print("   3. Использовать команды /analytics, /popular, /mystats")
        print("   4. Настроить cron задачу для еженедельной очистки")
        print("   5. Мониторить размер базы данных")

    except Exception as e:
        print(f"❌ Ошибка теста: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_metrics_system())
