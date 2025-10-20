"""Helper aliases for services with hyphenated package names."""

import importlib.util
import pathlib
import sys
from types import ModuleType

_ROOT = pathlib.Path(__file__).resolve().parent


def _register_alias(directory: pathlib.Path) -> None:
    name = directory.name
    if name == "__pycache__":
        return
    alias = name.replace("-", "_")
    init_file = directory / "__init__.py"
    if not init_file.exists():
        return
    hyphen_name = f"{__name__}.{name}"
    if hyphen_name in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(
        hyphen_name, init_file, submodule_search_locations=[str(directory)]
    )
    if spec is None or spec.loader is None:
        return
    module: ModuleType = importlib.util.module_from_spec(spec)
    module.__package__ = hyphen_name
    module.__path__ = [str(directory)]
    sys.modules[hyphen_name] = module
    if alias != name:
        sys.modules[f"{__name__}.{alias}"] = module
        globals()[alias] = module
    spec.loader.exec_module(module)
    if alias == name:
        globals()[name] = module


for _child in _ROOT.iterdir():
    if _child.is_dir():
        _register_alias(_child)
