from __future__ import annotations

import ast
import compileall
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "web" / "templates"
IGNORED_NAMES = {
    ".git",
    ".idea",
    ".agents",
    ".emergent",
    ".pnpm-store",
    ".pydeps",
    ".tmp",
    ".venv",
    ".venv-local",
    ".vscode",
    "__pycache__",
    "frontend",
    "node_modules",
    "venv",
}
REQUIRED_PATHS = [
    ROOT / "app.py",
    ROOT / "config.py",
    ROOT / "requirements.txt",
    ROOT / "models",
    ROOT / "services",
    ROOT / "stores",
    ROOT / "web" / "templates",
    ROOT / "web" / "static",
]


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    raise SystemExit(1)


def ok(message: str) -> None:
    print(f"[ OK ] {message}")


def iter_python_files():
    for base, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [name for name in dirnames if name not in IGNORED_NAMES]
        for filename in filenames:
            if filename.endswith(".py"):
                yield Path(base) / filename


def check_required_paths() -> None:
    missing = [path.relative_to(ROOT) for path in REQUIRED_PATHS if not path.exists()]
    if missing:
        fail("Eksik proje yolu: " + ", ".join(str(path) for path in missing))
    ok("Kritik proje dosyalari mevcut")


def check_python_syntax() -> None:
    success = True
    for path in iter_python_files():
        success = compileall.compile_file(path, quiet=1) and success

    if not success:
        fail("Python soz dizimi kontrolu basarisiz")
    ok("Python soz dizimi temiz")


def iter_template_names() -> set[str]:
    names: set[str] = set()
    for py_file in iter_python_files():
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_render_template = (
                isinstance(func, ast.Name)
                and func.id == "render_template"
            ) or (
                isinstance(func, ast.Attribute)
                and func.attr == "render_template"
            )
            if not is_render_template or not node.args:
                continue
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                names.add(first_arg.value)
    return names


def check_templates() -> None:
    missing = sorted(
        name for name in iter_template_names()
        if not (TEMPLATE_ROOT / name).exists()
    )
    if missing:
        fail("Eksik template: " + ", ".join(missing))
    ok("Template referanslari mevcut")


def main() -> int:
    check_required_paths()
    check_python_syntax()
    check_templates()
    ok("Proje kontrolu tamamlandi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
