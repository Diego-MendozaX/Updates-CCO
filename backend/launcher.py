"""Standard-library entry point, usable before project packages are installed."""
import builtins
from importlib import import_module
from pathlib import Path, PureWindowsPath
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE_PACKAGES = ("httpx", "openpyxl")
ANNEX_PACKAGES = ("pypdf", "xlrd")


def missing_dependencies(include_annexes=True):
    packages = BASE_PACKAGES + (ANNEX_PACKAGES if include_annexes else ())
    missing = []
    for package in packages:
        try:
            import_module(package)
        except ImportError:
            missing.append(package)
    return missing


def install_command(executable=None, requirements=None, windows=None):
    windows = sys.platform == "win32" if windows is None else windows
    path_type = PureWindowsPath if windows else Path
    python = path_type(executable or sys.executable)
    # A pythonw interpreter has no visible terminal for pip output on Windows.
    if windows and python.name.lower() == "pythonw.exe":
        python = python.with_name("python.exe")
    args = [str(python), "-m", "pip", "install", "-r",
            str(requirements or ROOT / "requirements-base.txt")]
    return subprocess.list2cmdline(args) if windows else shlex.join(args)


def launch(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    include_annexes = not any(flag in args for flag in ("--sin-descargar", "--solo-despacho"))
    missing = missing_dependencies(include_annexes)
    if missing:
        terminal = "Anaconda Prompt o CMD" if sys.platform == "win32" else "una terminal del sistema"
        print(
            "No se inició la actualización: no se pueden importar estos paquetes: "
            + ", ".join(missing)
            + f".\nPython utilizado: {sys.executable}\n"
            + f"Copia este comando en {terminal}, fuera de la consola de Spyder:\n\n"
            + install_command()
            + "\n\nDespués reinicia el kernel de Spyder y vuelve a ejecutar actualizar_base.py.",
            file=sys.stderr, flush=True,
        )
        return 2
    from .pipeline import run
    result = run(args)
    if result:
        print("Actualización incompleta (código 2). Revisa los errores indicados arriba.",
              file=sys.stderr, flush=True)
    return result


def cli():
    result = launch()
    get_shell = getattr(builtins, "get_ipython", None)
    interactive = callable(get_shell) and get_shell() is not None
    # Keep the terminal exit status, while avoiding Spyder's SystemExit traceback.
    if result and not interactive:
        raise SystemExit(result)
    return result
