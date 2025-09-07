#!/usr/bin/env python3
"""
Основной runner для всех тестов поиска лотов
"""

import os
import sys
import time
from pathlib import Path

# Добавляем путь к корню проекта
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "bot"))

# Импортируем тестовые модули
from test_fallback import run_fallback_tests
from test_rest_search import run_rest_tests

from test_graphql_search import run_graphql_tests


def print_environment_info():
    """Вывод информации об окружении тестирования"""
    print("🔬 ZakupAI Search Tests Environment")
    print("=" * 60)
    print(f"Python version: {sys.version}")
    print(f"Project root: {project_root}")
    print(f"Current working directory: {os.getcwd()}")

    # Проверяем наличие токенов для интеграционных тестов
    v2_token = os.getenv("GOSZAKUP_V2_TOKEN")
    v3_token = os.getenv("GOSZAKUP_V3_TOKEN")

    print("\n🔑 API Tokens:")
    print(f"  GraphQL v2 token: {'✅ Available' if v2_token else '❌ Not set'}")
    print(f"  REST v3 token: {'✅ Available' if v3_token else '❌ Not set'}")

    if not v2_token:
        print("     Set GOSZAKUP_V2_TOKEN=your_token for GraphQL v2 integration tests")
    if not v3_token:
        print("     Set GOSZAKUP_V3_TOKEN=your_token for REST v3 integration tests")

    print("\n📦 Test Modules:")
    test_files = ["test_graphql_search.py", "test_rest_search.py", "test_fallback.py"]

    for test_file in test_files:
        test_path = project_root / "tests" / test_file
        status = "✅ Found" if test_path.exists() else "❌ Missing"
        print(f"  {test_file}: {status}")

    print("=" * 60)


def run_tests_with_timing(test_name: str, test_function):
    """Запуск тестов с замером времени"""
    print(f"\n🚀 Starting {test_name}")
    print("-" * 40)

    start_time = time.time()
    success = test_function()
    end_time = time.time()

    duration = end_time - start_time
    status = "✅ PASSED" if success else "❌ FAILED"

    print(f"\n{status} - {test_name} completed in {duration:.2f}s")

    return success


def main():
    """Основная функция запуска всех тестов"""
    print_environment_info()

    # Результаты тестирования
    results = {}

    # Запускаем все наборы тестов
    test_suites = [
        ("GraphQL v2 Tests", run_graphql_tests),
        ("REST v3 Tests", run_rest_tests),
        ("Fallback Logic Tests", run_fallback_tests),
    ]

    for test_name, test_function in test_suites:
        try:
            success = run_tests_with_timing(test_name, test_function)
            results[test_name] = success
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results[test_name] = False

    # Финальный отчет
    print("\n" + "=" * 60)
    print("📋 FINAL TEST RESULTS")
    print("=" * 60)

    total_suites = len(results)
    passed_suites = sum(1 for success in results.values() if success)
    failed_suites = total_suites - passed_suites

    for test_name, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"  {status} - {test_name}")

    print("\n📊 Summary:")
    print(f"  Total test suites: {total_suites}")
    print(f"  Passed: {passed_suites}")
    print(f"  Failed: {failed_suites}")
    print(f"  Success rate: {passed_suites/total_suites*100:.1f}%")

    if failed_suites == 0:
        print("\n🎉 ALL TESTS PASSED! 🎉")
        print("The search system is ready for production use.")
    else:
        print("\n⚠️  Some tests failed. Please review the output above.")
        print("The search system may have issues that need to be addressed.")

    # Рекомендации
    print("\n💡 Recommendations:")

    if not os.getenv("GOSZAKUP_V2_TOKEN"):
        print("  - Set GOSZAKUP_V2_TOKEN for full GraphQL v2 testing")

    if not os.getenv("GOSZAKUP_V3_TOKEN"):
        print("  - Set GOSZAKUP_V3_TOKEN for authenticated REST v3 testing")

    if failed_suites > 0:
        print("  - Run individual test files for detailed error information")
        print("  - Check network connectivity and API availability")
        print("  - Verify token validity if using authenticated endpoints")

    print("\n🔧 Usage:")
    print("  - Run all tests: python tests/run_all_tests.py")
    print("  - Run specific tests: python tests/test_graphql_search.py")
    print("  - Set tokens: export GOSZAKUP_V2_TOKEN=your_token")

    print("=" * 60)

    return failed_suites == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
