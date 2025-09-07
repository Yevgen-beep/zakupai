"""
Модуль для логирования и анализа пользовательских метрик поиска
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SearchMetric:
    """Метрика поискового запроса"""

    user_id: int
    query: str
    results_count: int
    api_used: str
    execution_time_ms: int
    timestamp: datetime
    success: bool
    error_message: str | None = None


@dataclass
class PopularSearch:
    """Популярный поисковый запрос"""

    query: str
    count: int
    last_searched: datetime


@dataclass
class UserAnalytics:
    """Аналитика по пользователю"""

    user_id: int
    total_searches: int
    unique_queries: int
    most_searched_query: str
    last_activity: datetime
    avg_results_per_search: float


class UserMetricsService:
    """Сервис для работы с пользовательскими метриками"""

    def __init__(self, db_path: str = "data/user_metrics.db"):
        """
        Инициализация сервиса метрик

        Args:
            db_path: Путь к файлу базы данных SQLite
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Инициализация базы данных"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS search_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        query TEXT NOT NULL,
                        results_count INTEGER NOT NULL,
                        api_used TEXT NOT NULL,
                        execution_time_ms INTEGER NOT NULL,
                        success BOOLEAN NOT NULL,
                        error_message TEXT,
                        timestamp DATETIME NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # Индексы для быстрых запросов
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_user_id
                    ON search_metrics(user_id)
                """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_timestamp
                    ON search_metrics(timestamp)
                """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_query
                    ON search_metrics(query)
                """
                )

                conn.commit()
                logger.info(f"Metrics database initialized at {self.db_path}")

        except Exception as e:
            logger.error(f"Failed to initialize metrics database: {e}")
            raise

    def log_search(
        self,
        user_id: int,
        query: str,
        results_count: int,
        api_used: str,
        execution_time_ms: int,
        success: bool = True,
        error_message: str | None = None,
        auto_cleanup: bool = True,
    ):
        """
        Логирование поискового запроса

        Args:
            user_id: ID пользователя
            query: Поисковый запрос
            results_count: Количество найденных результатов
            api_used: Используемый API (graphql_v2, rest_v3, etc.)
            execution_time_ms: Время выполнения в миллисекундах
            success: Успешность запроса
            error_message: Сообщение об ошибке (если есть)
            auto_cleanup: Выполнять автоматическую очистку при необходимости
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO search_metrics
                    (user_id, query, results_count, api_used, execution_time_ms,
                     success, error_message, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        user_id,
                        query,
                        results_count,
                        api_used,
                        execution_time_ms,
                        success,
                        error_message,
                        datetime.now(),
                    ),
                )
                conn.commit()

            # Проверяем необходимость автоочистки каждые 100 запросов
            if auto_cleanup and user_id % 100 == 0:  # Проверяем не слишком часто
                try:
                    cleanup_result = self.auto_cleanup_by_size(
                        max_size_mb=150
                    )  # Более мягкий лимит
                    if cleanup_result:
                        logger.info(
                            f"Auto cleanup triggered for user {user_id}: {cleanup_result['deleted_count']} records removed"
                        )
                except Exception as cleanup_error:
                    logger.error(f"Auto cleanup failed: {cleanup_error}")

        except Exception as e:
            logger.error(f"Failed to log search metric: {e}")

    def get_popular_searches(
        self, days: int = 7, limit: int = 10
    ) -> list[PopularSearch]:
        """
        Получение популярных поисковых запросов

        Args:
            days: Количество дней для анализа
            limit: Максимальное количество результатов

        Returns:
            Список популярных запросов
        """
        try:
            since_date = datetime.now() - timedelta(days=days)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT query, COUNT(*) as count, MAX(timestamp) as last_searched
                    FROM search_metrics
                    WHERE timestamp >= ? AND success = 1 AND query != ''
                    GROUP BY query
                    ORDER BY count DESC, last_searched DESC
                    LIMIT ?
                """,
                    (since_date, limit),
                )

                results = []
                for row in cursor.fetchall():
                    results.append(
                        PopularSearch(
                            query=row[0],
                            count=row[1],
                            last_searched=datetime.fromisoformat(row[2]),
                        )
                    )

                return results

        except Exception as e:
            logger.error(f"Failed to get popular searches: {e}")
            return []

    def get_user_analytics(self, user_id: int, days: int = 30) -> UserAnalytics | None:
        """
        Получение аналитики по конкретному пользователю

        Args:
            user_id: ID пользователя
            days: Количество дней для анализа

        Returns:
            Аналитика пользователя или None
        """
        try:
            since_date = datetime.now() - timedelta(days=days)

            with sqlite3.connect(self.db_path) as conn:
                # Основная статистика
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total_searches,
                        COUNT(DISTINCT query) as unique_queries,
                        AVG(CAST(results_count AS FLOAT)) as avg_results,
                        MAX(timestamp) as last_activity
                    FROM search_metrics
                    WHERE user_id = ? AND timestamp >= ? AND success = 1
                """,
                    (user_id, since_date),
                )

                row = cursor.fetchone()
                if not row or row[0] == 0:
                    return None

                total_searches, unique_queries, avg_results, last_activity = row

                # Самый популярный запрос пользователя
                cursor = conn.execute(
                    """
                    SELECT query, COUNT(*) as count
                    FROM search_metrics
                    WHERE user_id = ? AND timestamp >= ? AND success = 1 AND query != ''
                    GROUP BY query
                    ORDER BY count DESC
                    LIMIT 1
                """,
                    (user_id, since_date),
                )

                most_searched_row = cursor.fetchone()
                most_searched_query = (
                    most_searched_row[0] if most_searched_row else "N/A"
                )

                return UserAnalytics(
                    user_id=user_id,
                    total_searches=total_searches,
                    unique_queries=unique_queries,
                    most_searched_query=most_searched_query,
                    last_activity=datetime.fromisoformat(last_activity),
                    avg_results_per_search=round(avg_results or 0, 1),
                )

        except Exception as e:
            logger.error(f"Failed to get user analytics: {e}")
            return None

    def get_system_stats(self, days: int = 7) -> dict[str, Any]:
        """
        Получение общей статистики системы

        Args:
            days: Количество дней для анализа

        Returns:
            Словарь с системной статистикой
        """
        try:
            since_date = datetime.now() - timedelta(days=days)

            with sqlite3.connect(self.db_path) as conn:
                stats = {}

                # Общие метрики
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total_searches,
                        COUNT(DISTINCT user_id) as active_users,
                        AVG(CAST(results_count AS FLOAT)) as avg_results_per_search,
                        AVG(CAST(execution_time_ms AS FLOAT)) as avg_execution_time,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate
                    FROM search_metrics
                    WHERE timestamp >= ?
                """,
                    (since_date,),
                )

                row = cursor.fetchone()
                if row:
                    stats.update(
                        {
                            "total_searches": row[0] or 0,
                            "active_users": row[1] or 0,
                            "avg_results_per_search": round(row[2] or 0, 1),
                            "avg_execution_time_ms": round(row[3] or 0, 1),
                            "success_rate": round(row[4] or 0, 1),
                        }
                    )

                # Статистика по API
                cursor = conn.execute(
                    """
                    SELECT api_used, COUNT(*) as count
                    FROM search_metrics
                    WHERE timestamp >= ?
                    GROUP BY api_used
                    ORDER BY count DESC
                """,
                    (since_date,),
                )

                api_stats = {}
                for row in cursor.fetchall():
                    api_stats[row[0]] = row[1]

                stats["api_usage"] = api_stats

                # Ошибки
                cursor = conn.execute(
                    """
                    SELECT COUNT(*) as error_count
                    FROM search_metrics
                    WHERE timestamp >= ? AND success = 0
                """,
                    (since_date,),
                )

                error_count = cursor.fetchone()[0] or 0
                stats["error_count"] = error_count

                return stats

        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
            return {}

    def get_top_users(self, days: int = 7, limit: int = 10) -> list[dict[str, Any]]:
        """
        Получение топ активных пользователей

        Args:
            days: Количество дней для анализа
            limit: Максимальное количество результатов

        Returns:
            Список топ пользователей
        """
        try:
            since_date = datetime.now() - timedelta(days=days)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT
                        user_id,
                        COUNT(*) as search_count,
                        COUNT(DISTINCT query) as unique_queries,
                        MAX(timestamp) as last_activity
                    FROM search_metrics
                    WHERE timestamp >= ? AND success = 1
                    GROUP BY user_id
                    ORDER BY search_count DESC
                    LIMIT ?
                """,
                    (since_date, limit),
                )

                results = []
                for row in cursor.fetchall():
                    results.append(
                        {
                            "user_id": row[0],
                            "search_count": row[1],
                            "unique_queries": row[2],
                            "last_activity": row[3],
                        }
                    )

                return results

        except Exception as e:
            logger.error(f"Failed to get top users: {e}")
            return []

    def cleanup_old_logs(self, days_to_keep: int = 90) -> dict[str, Any]:
        """
        Удаление старых логов для освобождения места

        Args:
            days_to_keep: Количество дней для сохранения (по умолчанию 90)

        Returns:
            Статистика очистки
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)

            with sqlite3.connect(self.db_path) as conn:
                # Сначала получаем статистику до очистки
                cursor = conn.execute("SELECT COUNT(*) FROM search_metrics")
                total_before = cursor.fetchone()[0]

                cursor = conn.execute(
                    "SELECT COUNT(*) FROM search_metrics WHERE timestamp < ?",
                    (cutoff_date,),
                )
                cursor.fetchone()[0]  # We don't need to store this count

                # Удаляем старые записи
                cursor = conn.execute(
                    "DELETE FROM search_metrics WHERE timestamp < ?", (cutoff_date,)
                )
                deleted_count = cursor.rowcount
                conn.commit()

                # Получаем статистику после очистки
                cursor = conn.execute("SELECT COUNT(*) FROM search_metrics")
                total_after = cursor.fetchone()[0]

                # Выполняем VACUUM для освобождения места
                conn.execute("VACUUM")

                cleanup_stats = {
                    "deleted_count": deleted_count,
                    "total_before": total_before,
                    "total_after": total_after,
                    "days_kept": days_to_keep,
                    "cutoff_date": cutoff_date.isoformat(),
                    "cleanup_date": datetime.now().isoformat(),
                }

                logger.info(
                    f"Cleaned up {deleted_count} old log entries (kept {days_to_keep} days)"
                )
                return cleanup_stats

        except Exception as e:
            logger.error(f"Failed to cleanup old logs: {e}")
            return {
                "error": str(e),
                "deleted_count": 0,
                "cleanup_date": datetime.now().isoformat(),
            }

    def get_database_info(self) -> dict[str, Any]:
        """
        Получение информации о базе данных

        Returns:
            Информация о размере базы и количестве записей
        """
        try:
            import os

            # Размер файла базы данных
            db_size_bytes = (
                os.path.getsize(self.db_path) if self.db_path.exists() else 0
            )
            db_size_mb = round(db_size_bytes / (1024 * 1024), 2)

            with sqlite3.connect(self.db_path) as conn:
                # Общее количество записей
                cursor = conn.execute("SELECT COUNT(*) FROM search_metrics")
                total_records = cursor.fetchone()[0]

                # Записи за последние 30 дней
                recent_date = datetime.now() - timedelta(days=30)
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM search_metrics WHERE timestamp >= ?",
                    (recent_date,),
                )
                recent_records = cursor.fetchone()[0]

                # Самая старая и новая записи
                cursor = conn.execute(
                    "SELECT MIN(timestamp), MAX(timestamp) FROM search_metrics"
                )
                date_range = cursor.fetchone()
                oldest_record = date_range[0] if date_range[0] else None
                newest_record = date_range[1] if date_range[1] else None

                return {
                    "db_size_mb": db_size_mb,
                    "db_size_bytes": db_size_bytes,
                    "total_records": total_records,
                    "recent_records_30d": recent_records,
                    "oldest_record": oldest_record,
                    "newest_record": newest_record,
                    "db_path": str(self.db_path),
                }

        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {"error": str(e)}

    def auto_cleanup_by_size(self, max_size_mb: float = 100) -> dict[str, Any] | None:
        """
        Автоматическая очистка если база данных превышает указанный размер

        Args:
            max_size_mb: Максимальный размер базы в MB

        Returns:
            Статистика очистки или None если очистка не нужна
        """
        try:
            db_info = self.get_database_info()
            current_size = db_info.get("db_size_mb", 0)

            if current_size > max_size_mb:
                logger.info(
                    f"Database size ({current_size}MB) exceeds limit ({max_size_mb}MB), starting cleanup"
                )

                # Сначала пробуем удалить записи старше 60 дней
                cleanup_stats = self.cleanup_old_logs(days_to_keep=60)

                # Проверяем размер после очистки
                new_db_info = self.get_database_info()
                new_size = new_db_info.get("db_size_mb", 0)

                # Если всё ещё большая, удаляем записи старше 30 дней
                if new_size > max_size_mb:
                    logger.info(
                        f"Still too large ({new_size}MB), cleaning up to 30 days"
                    )
                    cleanup_stats = self.cleanup_old_logs(days_to_keep=30)

                cleanup_stats["triggered_by_size"] = True
                cleanup_stats["size_limit_mb"] = max_size_mb
                cleanup_stats["size_before_mb"] = current_size
                cleanup_stats["size_after_mb"] = new_size

                return cleanup_stats

            return None  # Очистка не нужна

        except Exception as e:
            logger.error(f"Failed auto cleanup by size: {e}")
            return {"error": str(e)}


# Глобальный экземпляр сервиса метрик
metrics_service = UserMetricsService()
