"""
Справочники и маппинги для API Госзакупок
Содержит соответствия ID -> Название для различных справочников
"""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass

logger = logging.getLogger(__name__)


@dataclass
class TradeMethod:
    """Способ закупки"""

    id: int
    name_ru: str
    name_kz: str
    code: str
    description: str | None = None


@dataclass
class LotStatus:
    """Статус лота"""

    id: int
    name_ru: str
    name_kz: str
    code: str
    description: str | None = None


@dataclass
class RefMapping:
    """Базовый класс для справочника"""

    id: int
    name_ru: str
    name_kz: str
    code: str


class GoszakupMappings:
    """Класс для работы со справочниками Госзакупок"""

    def __init__(self):
        """Инициализация справочников с базовыми данными"""

        # Справочник способов закупки (ref_trade_methods)
        # Данные основаны на реальных значениях из API
        self.trade_methods: dict[int, TradeMethod] = {
            1: TradeMethod(
                1, "Открытый тендер", "Ашық тендер", "OT", "Открытый способ закупки"
            ),
            2: TradeMethod(
                2,
                "Конкурс по заявкам",
                "Өтінімдер бойынша конкурс",
                "KZ",
                "Конкурс заявок",
            ),
            3: TradeMethod(
                3,
                "Из одного источника",
                "Бір көзден",
                "OS",
                "Закупка у единственного источника",
            ),
            4: TradeMethod(
                4,
                "Запрос ценовых предложений",
                "Бағалық ұсыныстарды сұрату",
                "ZCP",
                "Запрос цен",
            ),
            5: TradeMethod(
                5, "На товарной бирже", "Тауарлық биржада", "TB", "Закупка на бирже"
            ),
            6: TradeMethod(
                6,
                "Аукцион на понижение",
                "Төмендету аукционы",
                "AP",
                "Аукцион с понижением цены",
            ),
            7: TradeMethod(
                7, "Открытый конкурс", "Ашық конкурс", "OK", "Открытый конкурс"
            ),
            8: TradeMethod(
                8,
                "Двухэтапный тендер",
                "Екі кезеңді тендер",
                "DT",
                "Тендер в два этапа",
            ),
            9: TradeMethod(
                9,
                "Предварительный квалификационный отбор",
                "Алдын ала білікті іріктеу",
                "PKO",
                "Предквалификация",
            ),
            10: TradeMethod(
                10,
                "Электронный магазин",
                "Электрондық дүкен",
                "EM",
                "Покупка в электронном магазине",
            ),
            11: TradeMethod(
                11,
                "Аукцион на повышение",
                "Өсіру аукционы",
                "AUP",
                "Аукцион с повышением цены",
            ),
            12: TradeMethod(
                12,
                "Конкурс проектов",
                "Жобалар конкурсы",
                "KP",
                "Конкурс архитектурных проектов",
            ),
        }

        # Справочник статусов лотов (ref_lot_status)
        # Данные основаны на реальных значениях из API
        self.lot_statuses: dict[int, LotStatus] = {
            1: LotStatus(
                1, "Опубликован", "Жарияланған", "PUB", "Объявление опубликовано"
            ),
            2: LotStatus(
                2, "Прием заявок", "Өтінімдерді қабылдау", "APP", "Идет прием заявок"
            ),
            3: LotStatus(
                3,
                "Рассмотрение заявок",
                "Өтінімдерді қарау",
                "REV",
                "Рассматриваются заявки",
            ),
            4: LotStatus(
                4,
                "Определение победителя",
                "Жеңімпазды анықтау",
                "WIN",
                "Определяется победитель",
            ),
            5: LotStatus(5, "Завершен", "Аяқталды", "FIN", "Закупка завершена"),
            6: LotStatus(6, "Отменен", "Болдырылмады", "CAN", "Закупка отменена"),
            7: LotStatus(
                7, "Приостановлен", "Тоқтатылды", "SUS", "Закупка приостановлена"
            ),
            8: LotStatus(8, "Не состоялся", "Болмады", "FAL", "Закупка не состоялась"),
            9: LotStatus(9, "Ожидание", "Күту", "WAI", "Ожидание решения"),
            10: LotStatus(
                10, "Подача заявок", "Өтінімдер беру", "SUB", "Период подачи заявок"
            ),
            11: LotStatus(
                11, "Подписание договора", "Шарт жасасу", "CON", "Заключается договор"
            ),
            12: LotStatus(
                12,
                "Исполнение договора",
                "Шартты орындау",
                "EXE",
                "Договор исполняется",
            ),
        }

        # Дополнительные справочники для расширенного поиска
        self.regions: dict[str, str] = {
            "71": "г. Нур-Султан",
            "75": "г. Алматы",
            "79": "г. Шымкент",
            "10": "Акмолинская область",
            "11": "Актюбинская область",
            "19": "Алматинская область",
            "23": "Атырауская область",
            "27": "Восточно-Казахстанская область",
            "31": "Жамбылская область",
            "35": "Западно-Казахстанская область",
            "39": "Карагандинская область",
            "43": "Костанайская область",
            "47": "Кызылординская область",
            "51": "Мангистауская область",
            "55": "Павлодарская область",
            "59": "Северо-Казахстанская область",
            "63": "Туркестанская область",
        }

    def get_trade_method_name(self, method_id: int) -> str:
        """
        Получение названия способа закупки по ID

        Args:
            method_id: ID способа закупки

        Returns:
            Название способа закупки или 'Не указан'
        """
        if method_id in self.trade_methods:
            return self.trade_methods[method_id].name_ru

        logger.warning(f"Unknown trade method ID: {method_id}")
        return f"Неизвестный способ ({method_id})"

    def get_lot_status_name(self, status_id: int) -> str:
        """
        Получение названия статуса лота по ID

        Args:
            status_id: ID статуса лота

        Returns:
            Название статуса лота или 'Не указан'
        """
        if status_id in self.lot_statuses:
            return self.lot_statuses[status_id].name_ru

        logger.warning(f"Unknown lot status ID: {status_id}")
        return f"Неизвестный статус ({status_id})"

    def get_region_name(self, region_code: str) -> str:
        """
        Получение названия региона по коду

        Args:
            region_code: Код региона (КАТО)

        Returns:
            Название региона или исходный код
        """
        return self.regions.get(region_code, region_code)

    def search_trade_methods(self, query: str) -> list[TradeMethod]:
        """
        Поиск способов закупки по названию

        Args:
            query: Поисковый запрос

        Returns:
            Список найденных способов закупки
        """
        query_lower = query.lower()
        results = []

        for method in self.trade_methods.values():
            if (
                query_lower in method.name_ru.lower()
                or query_lower in method.name_kz.lower()
                or query_lower in method.code.lower()
            ):
                results.append(method)

        return results

    def search_lot_statuses(self, query: str) -> list[LotStatus]:
        """
        Поиск статусов лотов по названию

        Args:
            query: Поисковый запрос

        Returns:
            Список найденных статусов
        """
        query_lower = query.lower()
        results = []

        for status in self.lot_statuses.values():
            if (
                query_lower in status.name_ru.lower()
                or query_lower in status.name_kz.lower()
                or query_lower in status.code.lower()
            ):
                results.append(status)

        return results

    def get_popular_trade_methods(self) -> list[TradeMethod]:
        """
        Получение популярных способов закупки

        Returns:
            Список популярных способов закупки
        """
        popular_ids = [
            1,
            3,
            4,
            7,
            10,
        ]  # Открытый тендер, из одного источника, ЗЦП, открытый конкурс, электронный магазин
        return [
            self.trade_methods[method_id]
            for method_id in popular_ids
            if method_id in self.trade_methods
        ]

    def get_active_lot_statuses(self) -> list[LotStatus]:
        """
        Получение активных статусов лотов

        Returns:
            Список активных статусов лотов
        """
        active_ids = [
            1,
            2,
            3,
            4,
            10,
            11,
        ]  # Опубликован, прием заявок, рассмотрение, определение победителя, подача заявок, подписание договора
        return [
            self.lot_statuses[status_id]
            for status_id in active_ids
            if status_id in self.lot_statuses
        ]

    def get_completed_lot_statuses(self) -> list[LotStatus]:
        """
        Получение завершенных статусов лотов

        Returns:
            Список завершенных статусов лотов
        """
        completed_ids = [
            5,
            6,
            8,
            12,
        ]  # Завершен, отменен, не состоялся, исполнение договора
        return [
            self.lot_statuses[status_id]
            for status_id in completed_ids
            if status_id in self.lot_statuses
        ]

    def export_mappings_to_json(self, file_path: str):
        """
        Экспорт справочников в JSON файл

        Args:
            file_path: Путь к файлу для экспорта
        """
        data = {
            "trade_methods": {str(k): asdict(v) for k, v in self.trade_methods.items()},
            "lot_statuses": {str(k): asdict(v) for k, v in self.lot_statuses.items()},
            "regions": self.regions,
            "export_date": datetime.now().isoformat(),
        }

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Mappings exported to {file_path}")
        except Exception as e:
            logger.error(f"Failed to export mappings: {e}")

    def import_mappings_from_json(self, file_path: str):
        """
        Импорт справочников из JSON файла

        Args:
            file_path: Путь к файлу для импорта
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # Импорт способов закупки
            if "trade_methods" in data:
                for k, v in data["trade_methods"].items():
                    method = TradeMethod(**v)
                    self.trade_methods[int(k)] = method

            # Импорт статусов лотов
            if "lot_statuses" in data:
                for k, v in data["lot_statuses"].items():
                    status = LotStatus(**v)
                    self.lot_statuses[int(k)] = status

            # Импорт регионов
            if "regions" in data:
                self.regions.update(data["regions"])

            logger.info(f"Mappings imported from {file_path}")

        except Exception as e:
            logger.error(f"Failed to import mappings: {e}")

    def get_mapping_statistics(self) -> dict[str, int]:
        """
        Получение статистики по справочникам

        Returns:
            Словарь со статистикой
        """
        return {
            "trade_methods_count": len(self.trade_methods),
            "lot_statuses_count": len(self.lot_statuses),
            "regions_count": len(self.regions),
        }

    def validate_ids(
        self, trade_method_ids: list[int], status_ids: list[int]
    ) -> dict[str, list[int]]:
        """
        Валидация списков ID

        Args:
            trade_method_ids: Список ID способов закупки
            status_ids: Список ID статусов лотов

        Returns:
            Словарь с валидными и невалидными ID
        """
        result = {
            "valid_trade_methods": [],
            "invalid_trade_methods": [],
            "valid_statuses": [],
            "invalid_statuses": [],
        }

        for method_id in trade_method_ids:
            if method_id in self.trade_methods:
                result["valid_trade_methods"].append(method_id)
            else:
                result["invalid_trade_methods"].append(method_id)

        for status_id in status_ids:
            if status_id in self.lot_statuses:
                result["valid_statuses"].append(status_id)
            else:
                result["invalid_statuses"].append(status_id)

        return result


# Глобальный экземпляр справочников
mappings = GoszakupMappings()


def get_trade_method_name(method_id: int) -> str:
    """Быстрый доступ к названию способа закупки"""
    return mappings.get_trade_method_name(method_id)


def get_lot_status_name(status_id: int) -> str:
    """Быстрый доступ к названию статуса лота"""
    return mappings.get_lot_status_name(status_id)


def get_region_name(region_code: str) -> str:
    """Быстрый доступ к названию региона"""
    return mappings.get_region_name(region_code)


# Функция для тестирования
async def test_mappings():
    """Тестовая функция для справочников"""

    print("🗂️ Testing Goszakup Mappings")
    print("=" * 50)

    # Тест способов закупки
    print("\n📋 Trade Methods:")
    for method_id in [1, 3, 4, 7, 10]:
        name = get_trade_method_name(method_id)
        print(f"  {method_id}: {name}")

    # Тест статусов лотов
    print("\n📊 Lot Statuses:")
    for status_id in [1, 2, 5, 6, 8]:
        name = get_lot_status_name(status_id)
        print(f"  {status_id}: {name}")

    # Поиск
    print("\n🔍 Search Results:")
    tender_methods = mappings.search_trade_methods("тендер")
    print(f"  Trade methods with 'тендер': {len(tender_methods)}")
    for method in tender_methods:
        print(f"    - {method.name_ru}")

    # Статистика
    stats = mappings.get_mapping_statistics()
    print(f"\n📈 Statistics: {stats}")

    # Популярные способы
    popular = mappings.get_popular_trade_methods()
    print(f"\n⭐ Popular trade methods: {len(popular)}")
    for method in popular:
        print(f"  - {method.name_ru}")


if __name__ == "__main__":
    # Импорт datetime для экспорта
    from datetime import datetime

    asyncio.run(test_mappings())
