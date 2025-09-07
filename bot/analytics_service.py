"""
Сервис аналитики для ZakupAI
Предоставляет простой интерфейс для получения статистики использования
"""

import logging
from datetime import datetime

from user_metrics import metrics_service

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Сервис для получения аналитики использования бота"""

    def __init__(self):
        """Инициализация сервиса аналитики"""
        self.metrics = metrics_service

    def get_dashboard_summary(self, days: int = 7) -> str:
        """
        Получение сводки для админской панели

        Args:
            days: Количество дней для анализа

        Returns:
            Форматированная строка с основной статистикой
        """
        try:
            stats = self.metrics.get_system_stats(days=days)

            if not stats:
                return "📊 **Аналитика недоступна**\nНет данных для отображения."

            # Основная статистика
            total_searches = stats.get("total_searches", 0)
            active_users = stats.get("active_users", 0)
            success_rate = stats.get("success_rate", 0)
            avg_results = stats.get("avg_results_per_search", 0)
            avg_time = stats.get("avg_execution_time_ms", 0)
            error_count = stats.get("error_count", 0)

            # Статистика по API
            api_usage = stats.get("api_usage", {})

            # Форматирование
            summary = f"""📊 **Аналитика за {days} дней**

🔍 **Основные метрики:**
├─ Всего поисков: **{total_searches:,}**
├─ Активных пользователей: **{active_users}**
├─ Успешность: **{success_rate:.1f}%**
├─ Среднее время ответа: **{avg_time:.0f}мс**
├─ Средние результаты: **{avg_results:.1f} лотов**
└─ Ошибок: **{error_count}**

🚀 **Использование API:**"""

            for api_name, count in api_usage.items():
                percentage = (count / total_searches * 100) if total_searches > 0 else 0
                api_display = {
                    "v2": "GraphQL v2",
                    "v3_rest": "REST v3",
                    "v3_gql": "GraphQL v3",
                    "rest_v3_fallback": "Fallback REST",
                    "unknown": "Неизвестно",
                }.get(api_name, api_name)

                summary += f"\n├─ {api_display}: **{count}** ({percentage:.1f}%)"

            return summary

        except Exception as e:
            logger.error(f"Failed to get dashboard summary: {e}")
            return f"❌ Ошибка получения статистики: {str(e)}"

    def get_popular_searches_text(self, days: int = 7, limit: int = 10) -> str:
        """
        Получение популярных поисковых запросов в виде текста

        Args:
            days: Количество дней для анализа
            limit: Максимальное количество результатов

        Returns:
            Форматированная строка с популярными запросами
        """
        try:
            popular_searches = self.metrics.get_popular_searches(days=days, limit=limit)

            if not popular_searches:
                return f"🔍 **Популярные запросы за {days} дней**\n\nНет данных для отображения."

            text = f"🔍 **Популярные запросы за {days} дней**\n"

            for i, search in enumerate(popular_searches, 1):
                # Ограничиваем длину запроса для читаемости
                query_display = (
                    search.query[:50] + "..."
                    if len(search.query) > 50
                    else search.query
                )

                # Форматируем время последнего поиска
                time_ago = datetime.now() - search.last_searched

                if time_ago.days > 0:
                    time_str = f"{time_ago.days}д назад"
                elif time_ago.seconds > 3600:
                    hours = time_ago.seconds // 3600
                    time_str = f"{hours}ч назад"
                else:
                    minutes = time_ago.seconds // 60
                    time_str = f"{minutes}м назад"

                text += f"\n{i}. **{query_display}**"
                text += f"\n   └─ {search.count} раз, {time_str}"

            return text

        except Exception as e:
            logger.error(f"Failed to get popular searches: {e}")
            return f"❌ Ошибка получения популярных запросов: {str(e)}"

    def get_user_stats_text(self, user_id: int, days: int = 30) -> str:
        """
        Получение статистики конкретного пользователя

        Args:
            user_id: ID пользователя
            days: Количество дней для анализа

        Returns:
            Форматированная строка со статистикой пользователя
        """
        try:
            user_analytics = self.metrics.get_user_analytics(user_id, days=days)

            if not user_analytics:
                return f"📊 **Ваша статистика за {days} дней**\n\n🤷‍♂️ Данных пока нет.\nНачните пользоваться поиском!"

            # Форматируем время последней активности
            time_ago = datetime.now() - user_analytics.last_activity

            if time_ago.days > 0:
                activity_str = f"{time_ago.days} дн. назад"
            elif time_ago.seconds > 3600:
                hours = time_ago.seconds // 3600
                activity_str = f"{hours} ч. назад"
            else:
                minutes = time_ago.seconds // 60
                activity_str = f"{minutes} мин. назад"

            # Ограничиваем длину самого популярного запроса
            top_query = user_analytics.most_searched_query
            if len(top_query) > 50:
                top_query = top_query[:50] + "..."

            text = f"""📊 **Ваша статистика за {days} дней**

🔍 **Активность:**
├─ Всего поисков: **{user_analytics.total_searches}**
├─ Уникальных запросов: **{user_analytics.unique_queries}**
├─ Среднее результатов: **{user_analytics.avg_results_per_search:.1f} лотов**
└─ Последняя активность: **{activity_str}**

⭐ **Топ запрос:** "{top_query}\""""

            return text

        except Exception as e:
            logger.error(f"Failed to get user stats: {e}")
            return f"❌ Ошибка получения вашей статистики: {str(e)}"

    def get_top_users_text(self, days: int = 7, limit: int = 10) -> str:
        """
        Получение топ активных пользователей

        Args:
            days: Количество дней для анализа
            limit: Максимальное количество результатов

        Returns:
            Форматированная строка с топ пользователями
        """
        try:
            top_users = self.metrics.get_top_users(days=days, limit=limit)

            if not top_users:
                return f"👥 **Топ пользователи за {days} дней**\n\nНет активных пользователей."

            text = f"👥 **Топ пользователи за {days} дней**\n"

            for i, user in enumerate(top_users, 1):
                # Маскируем ID пользователя для приватности
                masked_id = f"***{str(user['user_id'])[-3:]}"

                # Время последней активности
                last_activity = datetime.fromisoformat(user["last_activity"])
                time_ago = datetime.now() - last_activity

                if time_ago.days > 0:
                    time_str = f"{time_ago.days}д"
                elif time_ago.seconds > 3600:
                    hours = time_ago.seconds // 3600
                    time_str = f"{hours}ч"
                else:
                    minutes = time_ago.seconds // 60
                    time_str = f"{minutes}м"

                text += f"\n{i}. User {masked_id}"
                text += f"\n   ├─ Поисков: **{user['search_count']}**"
                text += f"\n   ├─ Уникальных: **{user['unique_queries']}**"
                text += f"\n   └─ Активность: {time_str} назад"

            return text

        except Exception as e:
            logger.error(f"Failed to get top users: {e}")
            return f"❌ Ошибка получения топ пользователей: {str(e)}"

    def cleanup_old_logs(self, days_to_keep: int = 90) -> str:
        """
        Очистка старых логов с форматированным отчетом

        Args:
            days_to_keep: Количество дней для сохранения

        Returns:
            Форматированный отчет об очистке
        """
        try:
            cleanup_stats = self.metrics.cleanup_old_logs(days_to_keep=days_to_keep)

            if "error" in cleanup_stats:
                return f"❌ Ошибка очистки логов: {cleanup_stats['error']}"

            deleted = cleanup_stats.get("deleted_count", 0)
            total_before = cleanup_stats.get("total_before", 0)
            total_after = cleanup_stats.get("total_after", 0)
            days_kept = cleanup_stats.get("days_kept", days_to_keep)

            if deleted == 0:
                return f"✅ **Очистка логов завершена**\n\nНет записей старше {days_kept} дней для удаления.\nВсего записей: **{total_after}**"

            percentage_deleted = (
                (deleted / total_before * 100) if total_before > 0 else 0
            )

            text = f"""🧹 **Очистка логов завершена**

📊 **Статистика:**
├─ Удалено записей: **{deleted:,}**
├─ Было записей: **{total_before:,}**
├─ Осталось записей: **{total_after:,}**
├─ Удалено: **{percentage_deleted:.1f}%**
└─ Сохранены записи за: **{days_kept} дней**

💾 База данных оптимизирована (VACUUM выполнен)
⏰ Дата очистки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

            return text

        except Exception as e:
            logger.error(f"Failed to format cleanup report: {e}")
            return f"❌ Ошибка очистки логов: {str(e)}"

    def get_database_info_text(self) -> str:
        """
        Получение информации о базе данных в виде текста

        Returns:
            Форматированная информация о базе данных
        """
        try:
            db_info = self.metrics.get_database_info()

            if "error" in db_info:
                return f"❌ Ошибка получения информации о базе: {db_info['error']}"

            size_mb = db_info.get("db_size_mb", 0)
            total_records = db_info.get("total_records", 0)
            recent_records = db_info.get("recent_records_30d", 0)
            oldest_record = db_info.get("oldest_record")
            newest_record = db_info.get("newest_record")

            # Рассчитываем возраст базы
            age_text = "Нет данных"
            if oldest_record:
                try:
                    oldest_date = datetime.fromisoformat(oldest_record)
                    age_days = (datetime.now() - oldest_date).days
                    age_text = f"{age_days} дней"
                except Exception:
                    age_text = "Неизвестно"

            # Определяем статус размера
            if size_mb < 10:
                size_status = "🟢 Малый"
            elif size_mb < 50:
                size_status = "🟡 Средний"
            elif size_mb < 100:
                size_status = "🟠 Большой"
            else:
                size_status = "🔴 Очень большой"

            text = f"""💾 **Информация о базе данных**

📊 **Размер и записи:**
├─ Размер файла: **{size_mb:.1f} MB** {size_status}
├─ Всего записей: **{total_records:,}**
├─ За последние 30 дней: **{recent_records:,}**
└─ Возраст базы: **{age_text}**

📅 **Временной диапазон:**
├─ Самая старая запись: {oldest_record[:19] if oldest_record else 'Нет данных'}
└─ Самая новая запись: {newest_record[:19] if newest_record else 'Нет данных'}

💡 **Рекомендации:**"""

            if size_mb > 100:
                text += "\n🔴 База данных большая, рекомендуется очистка"
            elif size_mb > 50:
                text += "\n🟠 Размер базы умеренный, мониторим рост"
            else:
                text += "\n🟢 Размер базы нормальный"

            return text

        except Exception as e:
            logger.error(f"Failed to get database info text: {e}")
            return f"❌ Ошибка получения информации о базе: {str(e)}"

    def auto_cleanup_by_size(self, max_size_mb: float = 100) -> str:
        """
        Автоматическая очистка по размеру базы с отчетом

        Args:
            max_size_mb: Максимальный размер базы в MB

        Returns:
            Форматированный отчет об автоочистке
        """
        try:
            cleanup_result = self.metrics.auto_cleanup_by_size(max_size_mb=max_size_mb)

            if cleanup_result is None:
                db_info = self.metrics.get_database_info()
                current_size = db_info.get("db_size_mb", 0)
                return f"✅ **Автоочистка не требуется**\n\nТекущий размер базы: **{current_size:.1f} MB**\nЛимит: **{max_size_mb} MB**"

            if "error" in cleanup_result:
                return f"❌ Ошибка автоочистки: {cleanup_result['error']}"

            deleted = cleanup_result.get("deleted_count", 0)
            size_before = cleanup_result.get("size_before_mb", 0)
            size_after = cleanup_result.get("size_after_mb", 0)
            size_saved = size_before - size_after

            text = f"""🤖 **Автоматическая очистка выполнена**

📊 **Результат:**
├─ Удалено записей: **{deleted:,}**
├─ Размер до очистки: **{size_before:.1f} MB**
├─ Размер после очистки: **{size_after:.1f} MB**
├─ Освобождено места: **{size_saved:.1f} MB**
└─ Лимит размера: **{max_size_mb} MB**

✅ База данных оптимизирована автоматически"""

            return text

        except Exception as e:
            logger.error(f"Failed auto cleanup by size: {e}")
            return f"❌ Ошибка автоочистки: {str(e)}"

    def export_stats_csv(self, days: int = 30) -> str:
        """
        Экспорт статистики в CSV формат (для администраторов)

        Args:
            days: Количество дней для экспорта

        Returns:
            CSV строка с данными или сообщение об ошибке
        """
        # Это можно реализовать позже при необходимости
        return "🚧 CSV экспорт пока не реализован."

    def get_error_summary(self, days: int = 7) -> str:
        """
        Получение сводки по ошибкам

        Args:
            days: Количество дней для анализа

        Returns:
            Форматированная строка с информацией об ошибках
        """
        try:
            # Получаем общую статистику
            stats = self.metrics.get_system_stats(days=days)
            error_count = stats.get("error_count", 0)
            total_searches = stats.get("total_searches", 0)

            if error_count == 0:
                return f"✅ **Отчет по ошибкам за {days} дней**\n\nОшибок не обнаружено! 🎉"

            error_rate = (
                (error_count / total_searches * 100) if total_searches > 0 else 0
            )

            text = f"""⚠️ **Отчет по ошибкам за {days} дней**

📊 **Статистика:**
├─ Всего ошибок: **{error_count}**
├─ Процент ошибок: **{error_rate:.1f}%**
└─ Успешных запросов: **{total_searches - error_count}**

💡 **Рекомендация:**
{"🔴 Высокий уровень ошибок!" if error_rate > 10 else "🟡 Уровень ошибок в норме." if error_rate > 5 else "🟢 Низкий уровень ошибок."}"""

            return text

        except Exception as e:
            logger.error(f"Failed to get error summary: {e}")
            return f"❌ Ошибка получения отчета об ошибках: {str(e)}"


# Глобальный экземпляр сервиса аналитики
analytics_service = AnalyticsService()
