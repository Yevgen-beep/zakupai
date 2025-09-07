"""
Морфологический анализатор для расширения поисковых запросов
Использует pymorphy2 для генерации всех форм слов
"""

import logging
import re
from dataclasses import dataclass

try:
    import pymorphy3 as pymorphy2

    PYMORPHY_AVAILABLE = True
except ImportError:
    try:
        import pymorphy2

        PYMORPHY_AVAILABLE = True
    except ImportError:
        PYMORPHY_AVAILABLE = False
        pymorphy2 = None

logger = logging.getLogger(__name__)


@dataclass
class MorphAnalysisResult:
    """Результат морфологического анализа"""

    original_query: str
    normalized_words: list[str]
    morphological_variants: dict[str, set[str]]
    expanded_queries: list[str]
    word_count: int
    variants_count: int


class MorphologyAnalyzer:
    """Морфологический анализатор для поисковых запросов"""

    def __init__(self):
        """Инициализация анализатора"""
        self.morph = None
        self.is_available = PYMORPHY_AVAILABLE

        if PYMORPHY_AVAILABLE:
            try:
                self.morph = pymorphy2.MorphAnalyzer()
                logger.info("Morphology analyzer initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize pymorphy2: {e}")
                self.is_available = False
        else:
            logger.warning("pymorphy2 not available - morphological expansion disabled")

    def is_enabled(self) -> bool:
        """Проверка доступности морфологического анализа"""
        return self.is_available and self.morph is not None

    def clean_word(self, word: str) -> str | None:
        """
        Очистка слова от лишних символов

        Args:
            word: Исходное слово

        Returns:
            Очищенное слово или None если слово нерелевантно
        """
        # Убираем пунктуацию и приводим к нижнему регистру
        cleaned = re.sub(r"[^\w\-]", "", word.strip().lower())

        # Фильтруем слишком короткие слова и служебные части речи
        if len(cleaned) < 2:
            return None

        # Исключаем числа
        if cleaned.isdigit():
            return None

        # Исключаем английские слова (базовая проверка)
        if re.match(r"^[a-z]+$", cleaned):
            return None

        return cleaned

    def get_word_forms(self, word: str, max_forms: int = 10) -> set[str]:
        """
        Получение всех форм слова

        Args:
            word: Исходное слово
            max_forms: Максимальное количество форм

        Returns:
            Множество форм слова
        """
        if not self.is_enabled():
            return {word}

        forms = set()

        try:
            # Получаем все возможные разборы слова
            parses = self.morph.parse(word)

            for parse in parses[:3]:  # Берём только первые 3 разбора
                # Добавляем нормальную форму
                forms.add(parse.normal_form)

                # Генерируем различные формы
                # Именительный и винительный падежи
                for case in ["nomn", "accs"]:
                    try:
                        inflected = parse.inflect({case})
                        if inflected:
                            forms.add(inflected.word)
                    except Exception:
                        continue

                # Множественное число
                try:
                    plural = parse.inflect({"plur"})
                    if plural:
                        forms.add(plural.word)
                except Exception:
                    pass

                # Прилагательные: мужской, женский, средний род
                if "ADJF" in parse.tag or "ADJS" in parse.tag:
                    for gender in ["masc", "femn", "neut"]:
                        try:
                            gendered = parse.inflect({gender})
                            if gendered:
                                forms.add(gendered.word)
                        except Exception:
                            continue

            # Ограничиваем количество форм
            if len(forms) > max_forms:
                # Оставляем самые важные формы
                important_forms = {word, parses[0].normal_form if parses else word}
                remaining_forms = list(forms - important_forms)[
                    : max_forms - len(important_forms)
                ]
                forms = important_forms | set(remaining_forms)

        except Exception as e:
            logger.error(f"Error getting word forms for '{word}': {e}")
            forms = {word}

        # Убираем слишком короткие и одинаковые формы
        forms = {f for f in forms if len(f) >= 2}

        return forms

    def expand_query(self, query: str) -> MorphAnalysisResult:
        """
        Расширение поискового запроса морфологическими формами

        Args:
            query: Исходный поисковый запрос

        Returns:
            Результат морфологического анализа
        """
        logger.info(f"Expanding query: '{query}'")

        # Разбиваем запрос на слова
        words = query.split()
        normalized_words = []
        morphological_variants = {}

        for word in words:
            cleaned_word = self.clean_word(word)
            if cleaned_word:
                normalized_words.append(cleaned_word)

                # Получаем морфологические варианты
                variants = self.get_word_forms(cleaned_word)
                morphological_variants[cleaned_word] = variants

        # Создаём расширенные запросы
        expanded_queries = self._create_expanded_queries(
            normalized_words, morphological_variants
        )

        # Подсчитываем статистику
        total_variants = sum(
            len(variants) for variants in morphological_variants.values()
        )

        result = MorphAnalysisResult(
            original_query=query,
            normalized_words=normalized_words,
            morphological_variants=morphological_variants,
            expanded_queries=expanded_queries,
            word_count=len(normalized_words),
            variants_count=total_variants,
        )

        logger.info(
            f"Query expansion: {len(normalized_words)} words → {total_variants} variants → {len(expanded_queries)} queries"
        )

        return result

    def _create_expanded_queries(
        self, words: list[str], variants: dict[str, set[str]]
    ) -> list[str]:
        """
        Создание расширенных поисковых запросов

        Args:
            words: Нормализованные слова
            variants: Морфологические варианты для каждого слова

        Returns:
            Список расширенных запросов
        """
        if not words:
            return []

        expanded_queries = set()

        # Базовые запросы с исходными словами
        expanded_queries.add(" ".join(words))

        # Запросы с морфологическими вариантами
        for word in words:
            word_variants = variants.get(word, {word})

            # Создаём запросы, заменяя одно слово его вариантами
            for variant in word_variants:
                if variant != word:  # Пропускаем исходное слово
                    query_with_variant = " ".join(
                        variant if w == word else w for w in words
                    )
                    expanded_queries.add(query_with_variant)

        # Если слов больше одного, создаём комбинации
        if len(words) > 1:
            # Запросы с отдельными словами
            for word in words:
                expanded_queries.add(word)
                # И их варианты
                word_variants = variants.get(word, {word})
                for variant in word_variants:
                    expanded_queries.add(variant)

        # Сортируем по длине (сначала более точные запросы)
        sorted_queries = sorted(expanded_queries, key=lambda q: (-len(q.split()), q))

        # Ограничиваем количество запросов
        max_queries = 15
        return sorted_queries[:max_queries]

    def get_search_variations(
        self, query: str, include_partial: bool = True
    ) -> list[str]:
        """
        Получение вариаций запроса для поиска

        Args:
            query: Исходный запрос
            include_partial: Включить ли частичные совпадения

        Returns:
            Список вариаций для поиска
        """
        if not self.is_enabled():
            # Если морфология недоступна, возвращаем базовые варианты
            variations = [query.strip()]

            if include_partial:
                words = query.split()
                variations.extend(words)

            return list(set(variations))

        # Используем морфологический анализ
        analysis = self.expand_query(query)
        variations = analysis.expanded_queries.copy()

        # Добавляем исходный запрос если его нет
        if query.strip() not in variations:
            variations.insert(0, query.strip())

        return variations

    def is_relevant_result(self, result_text: str, original_query: str) -> bool:
        """
        Проверка релевантности результата поиска

        Args:
            result_text: Текст результата (название + описание)
            original_query: Исходный поисковый запрос

        Returns:
            True если результат релевантен
        """
        if not result_text:
            return False

        result_text_lower = result_text.lower()

        # Анализируем исходный запрос
        analysis = self.expand_query(original_query)

        # Проверяем наличие морфологических вариантов
        for word, variants in analysis.morphological_variants.items():
            # Ищем любую форму слова в тексте результата
            for variant in variants:
                if variant in result_text_lower:
                    logger.debug(
                        f"Found relevant variant '{variant}' for word '{word}' in result"
                    )
                    return True

        # Дополнительная проверка для случаев, когда морфология не сработала
        for word in analysis.normalized_words:
            if word in result_text_lower:
                return True

        return False

    def get_statistics(self) -> dict[str, any]:
        """Получение статистики работы анализатора"""
        return {
            "enabled": self.is_enabled(),
            "pymorphy_available": PYMORPHY_AVAILABLE,
            "analyzer_loaded": self.morph is not None,
        }


# Глобальный экземпляр анализатора
_morphology_analyzer = None


def get_morphology_analyzer() -> MorphologyAnalyzer:
    """Получение глобального экземпляра морфологического анализатора"""
    global _morphology_analyzer

    if _morphology_analyzer is None:
        _morphology_analyzer = MorphologyAnalyzer()

    return _morphology_analyzer


# Функция для тестирования
async def test_morphology():
    """Тестовая функция морфологического анализатора"""
    analyzer = get_morphology_analyzer()

    print(f"Morphology analyzer available: {analyzer.is_enabled()}")
    print(f"Statistics: {analyzer.get_statistics()}")

    if analyzer.is_enabled():
        # Тест расширения запроса
        test_queries = ["лак", "краска", "компьютер", "строительство дорог"]

        for query in test_queries:
            print(f"\n--- Testing query: '{query}' ---")

            analysis = analyzer.expand_query(query)
            print(f"Original: {analysis.original_query}")
            print(f"Normalized words: {analysis.normalized_words}")
            print(
                f"Word count: {analysis.word_count}, Variants: {analysis.variants_count}"
            )

            print("Morphological variants:")
            for word, variants in analysis.morphological_variants.items():
                print(f"  {word}: {list(variants)[:5]}")  # Первые 5 вариантов

            print(f"Expanded queries ({len(analysis.expanded_queries)}):")
            for i, expanded in enumerate(analysis.expanded_queries[:8], 1):
                print(f"  {i}. {expanded}")

        # Тест релевантности
        print("\n--- Testing relevance ---")
        test_results = [
            "Лакокрасочные материалы для стен",
            "Услуги по строительству",
            "Компьютерное оборудование",
            "Уголь каменный",  # Нерелевантный для "лак"
        ]

        for result in test_results:
            is_relevant = analyzer.is_relevant_result(result, "лак")
            print(f"'{result}' → {'✅ Relevant' if is_relevant else '❌ Not relevant'}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_morphology())
