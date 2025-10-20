"""
Примеры использования универсального клиента API госзакупок v3

Этот файл содержит практические примеры использования всех основных функций клиента
"""

import asyncio
import json
from datetime import datetime, timedelta

from bot.goszakup_client_extensions import (
    ExportFormat,
    GoszakupClientFull,
    create_monitoring_callback,
)

# Импортируем клиент и все необходимые компоненты
from bot.goszakup_client_v3 import (
    ContractStatus,
    GoszakupClient,
    LotStatus,
    SubjectType,
    TradeMethod,
)

# Токен для API (замените на ваш реальный токен)
TOKEN = "cc9ae7eb4025aca71e2e445823d88b86"


async def basic_search_examples():
    """Базовые примеры поиска"""
    print("=== БАЗОВЫЕ ПРИМЕРЫ ПОИСКА ===\n")

    async with GoszakupClient(token=TOKEN) as client:
        # Пример 1: Простой поиск по ключевому слову
        print("1. Поиск лотов по ключевому слову 'компьютер':")
        lots = await client.search_lots(keyword="компьютер", limit=5)
        for lot in lots:
            print(f"  - {lot.lotNumber}: {lot.nameRu} ({lot.amount:,.0f} тг)")
        print()

        # Пример 2: Поиск с фильтрами
        print("2. Поиск лотов с расширенными фильтрами:")
        lots = await client.search_lots(
            keyword="строительство",
            trade_methods=[TradeMethod.OPEN_TENDER],
            status=[LotStatus.PUBLISHED, LotStatus.ACCEPTING_APPLICATIONS],
            amount_range=(1000000, 10000000),
            limit=3,
        )
        for lot in lots:
            print(f"  - {lot.nameRu}")
            print(f"    Сумма: {lot.amount:,.0f} тг")
            print(f"    Статус: {lot.status}")
            print(f"    Способ: {lot.tradeMethod}")
        print()

        # Пример 3: Поиск по БИН заказчика
        print("3. Поиск лотов по БИН заказчика:")
        lots = await client.search_lots(customer_bin=["050140008196"], limit=3)
        for lot in lots:
            print(f"  - {lot.nameRu}")
            print(f"    Заказчик: {lot.customerNameRu} (БИН: {lot.customerBin})")
        print()


async def advanced_search_examples():
    """Продвинутые примеры поиска"""
    print("=== ПРОДВИНУТЫЕ ПРИМЕРЫ ПОИСКА ===\n")

    async with GoszakupClient(token=TOKEN) as client:
        # Пример 4: Поиск контрактов
        print("4. Поиск контрактов:")
        contracts = await client.search_contracts(
            sign_date_from="2024-01-01",
            status=[ContractStatus.ACTIVE],
            contract_sum_range=(500000, 5000000),
            include_acts=True,
            limit=3,
        )
        for contract in contracts:
            print(f"  - {contract.contractNumber}")
            print(f"    Поставщик: {contract.supplierNameRu}")
            print(f"    Сумма: {contract.contractSum:,.0f} тг")
            if contract.acts:
                print(f"    Актов: {len(contract.acts)}")
        print()

        # Пример 5: Поиск участников
        print("5. Поиск участников:")
        subjects = await client.search_subjects(
            name_keyword="строительство",
            subject_type=[SubjectType.LEGAL_ENTITY],
            is_active=True,
            limit=3,
        )
        for subject in subjects:
            print(f"  - {subject.nameRu}")
            print(f"    БИН: {subject.bin}")
            print(f"    Тип: {subject.subjectType}")
        print()

        # Пример 6: Поиск объявлений
        print("6. Поиск объявлений:")
        announcements = await client.search_trd_buy(
            name_keyword="оборудование",
            trade_methods=[TradeMethod.OPEN_TENDER],
            start_date_from="2024-01-01",
            limit=3,
        )
        for announcement in announcements:
            print(f"  - {announcement.get('nameRu', 'Без названия')}")
            print(f"    Номер: {announcement.get('numberAnno', 'N/A')}")
            print(f"    Организатор: {announcement.get('orgNameRu', 'N/A')}")
        print()


async def export_examples():
    """Примеры экспорта данных"""
    print("=== ПРИМЕРЫ ЭКСПОРТА ДАННЫХ ===\n")

    async with GoszakupClientFull(token=TOKEN) as client:
        # Получаем данные для экспорта
        lots = await client.search_lots(keyword="компьютер", limit=5)

        if not lots:
            print("Нет данных для экспорта")
            return

        # Пример 7: Экспорт в JSON
        print("7. Экспорт в JSON:")
        json_data = await client.export_search_results(lots, ExportFormat.JSON)

        # Сохранение в файл
        with open("export_lots.json", "w", encoding="utf-8") as f:
            f.write(json_data)
        print("  Данные экспортированы в export_lots.json")

        # Вывод части данных
        data = json.loads(json_data)
        print(f"  Экспортировано записей: {data['count']}")
        print(f"  Время экспорта: {data['metadata']['export_time']}")
        print()

        # Пример 8: Экспорт в CSV
        print("8. Экспорт в CSV:")
        csv_data = await client.export_search_results(lots, ExportFormat.CSV)

        with open("export_lots.csv", "w", encoding="utf-8") as f:
            f.write(csv_data)
        print("  Данные экспортированы в export_lots.csv")
        print(f"  Строк в файле: {len(csv_data.splitlines())}")
        print()

        # Пример 9: Экспорт в Excel (если доступен openpyxl)
        try:
            print("9. Экспорт в Excel:")
            excel_data = await client.export_search_results(lots, ExportFormat.EXCEL)

            with open("export_lots.xlsx", "wb") as f:
                f.write(excel_data)
            print("  Данные экспортированы в export_lots.xlsx")
            print(f"  Размер файла: {len(excel_data)} байт")
            print()
        except ImportError:
            print("9. Excel экспорт недоступен (установите openpyxl)")
            print()


async def caching_and_stats_examples():
    """Примеры кеширования и статистики"""
    print("=== КЕШИРОВАНИЕ И СТАТИСТИКА ===\n")

    async with GoszakupClientFull(token=TOKEN, cache_ttl=600) as client:
        # Пример 10: Использование кеша
        print("10. Демонстрация кеширования:")

        # Первый запрос - будет кеширован
        start_time = datetime.now()
        lots1 = await client.search_lots(keyword="медицинск", limit=3)
        time1 = (datetime.now() - start_time).total_seconds()
        print(f"  Первый запрос: {time1:.2f} сек")

        # Второй такой же запрос - из кеша
        start_time = datetime.now()
        lots2 = await client.search_lots(keyword="медицинск", limit=3)
        time2 = (datetime.now() - start_time).total_seconds()
        print(f"  Второй запрос (кеш): {time2:.2f} сек")

        # Статистика
        stats = await client.get_stats()
        print(f"  Всего запросов: {stats['stats']['requests_total']}")
        print(f"  Попаданий в кеш: {stats['stats']['cache_hits']}")
        print(f"  Промахов кеша: {stats['stats']['cache_misses']}")
        print()

        # Пример 11: Статистика по лотам
        if lots1:
            print("11. Статистика по результатам:")
            lot_stats = await client.get_lots_stats(lots1, group_by="tradeMethod")
            print(f"  Всего лотов: {lot_stats['total']}")
            print(f"  Общая сумма: {lot_stats['total_amount']:,.0f} тг")
            print(f"  Средняя сумма: {lot_stats['avg_amount']:,.0f} тг")
            print("  Группировка по способу закупки:")
            for method, data in lot_stats["groups"].items():
                print(
                    f"    {method}: {data['count']} лотов на {data['amount']:,.0f} тг"
                )
        print()


async def telegram_formatting_examples():
    """Примеры форматирования для Telegram"""
    print("=== ФОРМАТИРОВАНИЕ ДЛЯ TELEGRAM ===\n")

    async with GoszakupClientFull(token=TOKEN) as client:
        # Пример 12: Поиск с форматированием для Telegram
        print("12. Поиск с форматированием для Telegram:")
        telegram_response = await client.search_lots_for_telegram(
            keyword="компьютер", limit=2
        )
        print(telegram_response)
        print()

        # Пример 13: Индивидуальное форматирование
        print("13. Индивидуальное форматирование лота:")
        lots = await client.search_lots(keyword="оборудование", limit=1)
        if lots:
            formatted = client.format_lot_for_telegram(lots[0])
            print(formatted)
        print()


async def preset_and_batch_examples():
    """Примеры предустановок и батчинга"""
    print("=== ПРЕДУСТАНОВКИ И БАТЧИНГ ===\n")

    async with GoszakupClientFull(token=TOKEN) as client:
        # Пример 14: Использование предустановленных фильтров
        print("14. Поиск с предустановкой 'construction_almaty':")
        lots = await client.search_with_preset(
            "construction_almaty", additional_filters={"limit": 3}
        )
        for lot in lots:
            print(f"  - {lot.nameRu}")
        print()

        # Пример 15: Батчевый поиск по БИН
        print("15. Батчевый поиск по списку БИН:")
        test_bins = ["050140008196", "123456789012", "987654321098"]
        batch_results = await client.batch_search_by_bins(
            bins=test_bins, entity_type="lots", batch_size=2, limit=2
        )

        for bin_code, lots in batch_results.items():
            print(f"  БИН {bin_code}: найдено {len(lots)} лотов")
        print()


async def monitoring_example():
    """Пример мониторинга новых лотов"""
    print("=== МОНИТОРИНГ НОВЫХ ЛОТОВ ===\n")

    async with GoszakupClientFull(token=TOKEN) as client:
        # Создание callback функции
        def process_new_lot(lot):
            print(f"🆕 Новый лот: {lot.nameRu}")
            print(f"   Сумма: {lot.amount:,.0f} тг")
            print(f"   Заказчик: {lot.customerNameRu}")
            return lot

        callback = create_monitoring_callback(process_new_lot)

        # Пример 16: Настройка мониторинга
        print("16. Настройка мониторинга (демонстрация):")

        subscription_id = await client.monitor_lots(
            filters={"keyword": "тест", "limit": 5},
            callback=callback,
            interval=60,  # проверка каждые 60 секунд
        )
        print(f"  Создана подписка: {subscription_id}")

        # Список подписок
        subscriptions = await client.list_subscriptions()
        print(f"  Активных подписок: {len(subscriptions)}")

        # Остановка мониторинга (для демонстрации)
        await client.stop_monitoring(subscription_id)
        print("  Мониторинг остановлен")
        print()


async def error_handling_example():
    """Примеры обработки ошибок"""
    print("=== ОБРАБОТКА ОШИБОК ===\n")

    try:
        # Пример с неправильным токеном
        async with GoszakupClient(token="invalid_token") as client:
            await client.search_lots(keyword="тест", limit=1)
    except Exception as e:
        print(f"17. Ошибка авторизации: {e}")

    try:
        # Пример с некорректными параметрами
        async with GoszakupClient(token=TOKEN) as client:
            await client.search_lots(keyword="", limit=0)
    except Exception as e:
        print(f"18. Ошибка параметров: {e}")

    print()


async def comprehensive_example():
    """Комплексный пример использования всех возможностей"""
    print("=== КОМПЛЕКСНЫЙ ПРИМЕР ===\n")

    async with GoszakupClientFull(token=TOKEN) as client:
        print("19. Комплексный анализ лотов по компьютерному оборудованию:")

        # Шаг 1: Поиск лотов
        lots = await client.search_lots(
            keyword="компьютер",
            trade_methods=[TradeMethod.OPEN_TENDER, TradeMethod.REQUEST_QUOTATIONS],
            status=[LotStatus.PUBLISHED, LotStatus.ACCEPTING_APPLICATIONS],
            amount_range=(100000, 10000000),
            publish_date_from=(datetime.now() - timedelta(days=30)).strftime(
                "%Y-%m-%d"
            ),
            limit=10,
        )

        print(f"  Найдено лотов: {len(lots)}")

        if lots:
            # Шаг 2: Статистический анализ
            stats = await client.get_lots_stats(lots, group_by="tradeMethod")
            print(f"  Общая сумма: {stats['total_amount']:,.0f} тг")
            print(f"  Средняя сумма лота: {stats['avg_amount']:,.0f} тг")

            # Шаг 3: Экспорт результатов
            json_export = await client.export_search_results(lots, ExportFormat.JSON)
            with open("comprehensive_analysis.json", "w", encoding="utf-8") as f:
                f.write(json_export)
            print("  Результаты экспортированы в comprehensive_analysis.json")

            # Шаг 4: Поиск связанных контрактов
            unique_customer_bins = list(
                set(lot.customerBin for lot in lots if lot.customerBin)
            )[:5]
            if unique_customer_bins:
                contracts = await client.search_contracts(
                    customer_bin=unique_customer_bins,
                    sign_date_from="2024-01-01",
                    limit=5,
                )
                print(f"  Найдено связанных контрактов: {len(contracts)}")

            # Шаг 5: Форматирование для Telegram (первые 3 лота)
            print("\n  Форматирование для отправки в Telegram:")
            for i, lot in enumerate(lots[:3], 1):
                print(f"    Лот {i}:")
                formatted = client.format_lot_for_telegram(lot)
                # Выводим только первые строки для краткости
                lines = formatted.split("\n")
                for line in lines[:4]:
                    print(f"      {line}")
                print("      ...")
        print()


async def main():
    """Главная функция с запуском всех примеров"""
    print("УНИВЕРСАЛЬНЫЙ КЛИЕНТ API ГОСЗАКУПОК КАЗАХСТАНА v3")
    print("=" * 60)
    print(f"Токен: {TOKEN[:10]}...")
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    try:
        # Базовые примеры
        await basic_search_examples()

        # Продвинутые примеры
        await advanced_search_examples()

        # Экспорт данных
        await export_examples()

        # Кеширование и статистика
        await caching_and_stats_examples()

        # Форматирование для Telegram
        await telegram_formatting_examples()

        # Предустановки и батчинг
        await preset_and_batch_examples()

        # Мониторинг
        await monitoring_example()

        # Обработка ошибок
        await error_handling_example()

        # Комплексный пример
        await comprehensive_example()

    except KeyboardInterrupt:
        print("\nВыполнение прервано пользователем")
    except Exception as e:
        print(f"\nОшибка выполнения: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Все примеры выполнены!")


if __name__ == "__main__":
    # Запуск всех примеров
    asyncio.run(main())
