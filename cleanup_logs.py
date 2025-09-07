#!/usr/bin/env python3
"""
Скрипт автоматической очистки логов для ZakupAI
Можно запускать через cron для периодической очистки
"""

import os
import sys
from datetime import datetime

# Добавляем bot директорию в путь Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))

from user_metrics import metrics_service


def main():
    """Основная функция очистки логов"""

    print(f"🧹 ZakupAI Log Cleanup - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    try:
        # Получаем текущую информацию о базе данных
        db_info = metrics_service.get_database_info()

        print(f"💾 Текущий размер базы: {db_info.get('db_size_mb', 0):.2f} MB")
        print(f"📊 Всего записей: {db_info.get('total_records', 0):,}")
        print(
            f"📅 Записей за последние 30 дней: {db_info.get('recent_records_30d', 0):,}"
        )

        # Проверяем, нужна ли очистка
        size_mb = db_info.get("db_size_mb", 0)
        total_records = db_info.get("total_records", 0)

        cleanup_needed = False
        days_to_keep = 90  # По умолчанию

        # Определяем стратегию очистки
        if size_mb > 100:  # Если больше 100MB
            days_to_keep = 30
            cleanup_needed = True
            print("🔴 База данных очень большая - агрессивная очистка (30 дней)")
        elif size_mb > 50:  # Если больше 50MB
            days_to_keep = 60
            cleanup_needed = True
            print("🟠 База данных большая - умеренная очистка (60 дней)")
        elif total_records > 50000:  # Если больше 50k записей
            days_to_keep = 90
            cleanup_needed = True
            print("🟡 Много записей - стандартная очистка (90 дней)")
        else:
            print("🟢 База данных в норме - очистка не требуется")

        if cleanup_needed:
            print(f"\n🧹 Начинаем очистку логов старше {days_to_keep} дней...")

            # Выполняем очистку
            cleanup_stats = metrics_service.cleanup_old_logs(days_to_keep=days_to_keep)

            deleted_count = cleanup_stats.get("deleted_count", 0)
            total_after = cleanup_stats.get("total_after", 0)

            if deleted_count > 0:
                print("✅ Очистка завершена успешно!")
                print(f"   - Удалено записей: {deleted_count:,}")
                print(f"   - Осталось записей: {total_after:,}")

                # Получаем финальную информацию
                final_db_info = metrics_service.get_database_info()
                final_size = final_db_info.get("db_size_mb", 0)
                size_saved = size_mb - final_size

                print(f"   - Размер базы: {final_size:.2f} MB")
                print(f"   - Освобождено места: {size_saved:.2f} MB")

                # Запись в лог
                log_message = f"{datetime.now().isoformat()}: Cleaned {deleted_count} records, saved {size_saved:.2f} MB"
                with open("data/cleanup.log", "a") as log_file:
                    log_file.write(log_message + "\n")

            else:
                print("ℹ️ Нет записей для удаления")

        print(f"\n✅ Очистка логов завершена - {datetime.now().strftime('%H:%M:%S')}")

        # Дополнительно: автоочистка по размеру (если всё ещё большая)
        final_size = (
            size_mb
            if not cleanup_needed
            else metrics_service.get_database_info().get("db_size_mb", 0)
        )

        if final_size > 150:  # Если всё ещё больше 150MB
            print(
                f"\n🤖 База всё ещё большая ({final_size:.2f} MB) - запускаем автоочистку..."
            )
            auto_cleanup_result = metrics_service.auto_cleanup_by_size(max_size_mb=100)

            if auto_cleanup_result and auto_cleanup_result.get("deleted_count", 0) > 0:
                print(
                    f"✅ Автоочистка: удалено {auto_cleanup_result['deleted_count']} записей"
                )

        return 0  # Успех

    except Exception as e:
        error_message = f"❌ Ошибка очистки логов: {e}"
        print(error_message)

        # Запись ошибки в лог
        try:
            os.makedirs("data", exist_ok=True)
            with open("data/cleanup.log", "a") as log_file:
                log_file.write(f"{datetime.now().isoformat()}: ERROR - {e}\n")
        except:
            pass

        return 1  # Ошибка


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
