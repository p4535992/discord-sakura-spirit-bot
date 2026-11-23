"""Import every project module so syntax and annotation errors surface early."""
import importlib
import pkgutil

import pytest

PROJECT_PACKAGES = ["core", "commands", "models", "systems", "utils"]


def _iter_module_names(package_name: str):
    package = importlib.import_module(package_name)
    yield package_name
    for module in pkgutil.walk_packages(package.__path__, prefix=f"{package_name}."):
        yield module.name


MODULE_NAMES = [
    module_name
    for package_name in PROJECT_PACKAGES
    for module_name in _iter_module_names(package_name)
]


@pytest.mark.parametrize("module_name", MODULE_NAMES)
def test_module_imports(module_name: str):
    """Every module must import without NameError or missing dependencies."""
    assert importlib.import_module(module_name) is not None
