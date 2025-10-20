"""
Global pytest configuration for ZakupAI microservices.

✔ Исправляет импорты сервисов с дефисами (doc-service, calc-service и т.д.)
✔ Поддерживает старые импорты вида tests.*
✔ Мокает внешние зависимости: psycopg2, psycopg2.extras, fitz, pytesseract
✔ Предотвращает зависания и обращения к БД или Vault при тестировании
"""
import sys
import importlib.util
import importlib.abc
import importlib.machinery
import pathlib
from types import ModuleType
from unittest.mock import MagicMock


# === 1. Алиасы для сервисов с дефисами ===
ROOT = pathlib.Path(__file__).resolve().parent / "services"


def _register_alias(service_dir: pathlib.Path) -> None:
    """Позволяет импортировать пакеты services.calc_service вместо services/calc-service"""
    if not service_dir.is_dir():
        return
    name = service_dir.name
    alias = name.replace("-", "_")

    init_file = service_dir / "__init__.py"
    if not init_file.exists():
        init_file.touch()

    spec = importlib.util.spec_from_file_location(
        f"services.{alias}", str(init_file), submodule_search_locations=[str(service_dir)]
    )
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        module.__path__ = [str(service_dir)]
        sys.modules[f"services.{name}"] = module
        sys.modules[f"services.{alias}"] = module


for child in ROOT.iterdir():
    _register_alias(child)


# === 2. Моки внешних зависимостей ===
sys.modules["fitz"] = MagicMock(name="fitz")
sys.modules["pytesseract"] = MagicMock(name="pytesseract")

psycopg2_mock = MagicMock(name="psycopg2")
psycopg2_conn = MagicMock(name="MockPsycopg2Conn")
psycopg2_mock.connect.return_value = psycopg2_conn

psycopg2_extras_mock = MagicMock(name="psycopg2.extras")
psycopg2_mock.extras = psycopg2_extras_mock

sys.modules["psycopg2"] = psycopg2_mock
sys.modules["psycopg2.extras"] = psycopg2_extras_mock


# === 3. Исправляем pytest import hook для "tests.*" ===
class _TestAliasFinder(importlib.abc.MetaPathFinder):
    """Позволяет pytest импортировать tests.* даже при дефисах в пути."""
    def find_spec(self, fullname: str, path=None, target=None):
        if not fullname.startswith("tests."):
            return None
        module_name = fullname.split(".", 1)[1]
        for service_dir in ROOT.iterdir():
            if not service_dir.is_dir():
                continue
            tests_dir = service_dir / "tests"
            if not tests_dir.is_dir():
                continue
            for candidate in (
                f"services.{service_dir.name}.tests.{module_name}",
                f"services.{service_dir.name.replace('-', '_')}.tests.{module_name}",
            ):
                spec = importlib.util.find_spec(candidate)
                if spec and spec.origin:
                    loader = importlib.machinery.SourceFileLoader(fullname, str(spec.origin))
                    return importlib.util.spec_from_loader(fullname, loader)
        return None


sys.meta_path.insert(0, _TestAliasFinder())
