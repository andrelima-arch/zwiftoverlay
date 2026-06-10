import importlib
import os
import subprocess
import sys
import time
import traceback

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP_DIR = os.path.join(SCRIPT_DIR, "cycling_overlay")
CACHE_FILE = os.path.join(SCRIPT_DIR, ".deps_checked")
CACHE_MAX_AGE_DAYS = 7

REQUIRED_PACKAGES = [
    ("customtkinter", "customtkinter"),
    ("pydantic", "pydantic"),
    ("platformdirs", "platformdirs"),
    ("bleak", "bleak"),
    ("requests", "requests"),
    ("zeroconf", "zeroconf"),
]


def check_python_version(gui=False):
    if sys.version_info < (3, 11):
        msg = (
            f"Python {sys.version_info.major}.{sys.version_info.minor} detectado.\n"
            f"É necessário Python 3.11 ou superior.\n\n"
            f"Baixe em: https://www.python.org/downloads/"
        )
        if gui:
            _show_error("Cycling Overlay — Python desatualizado", msg)
        else:
            print(f"Erro: {msg}")
            input("Pressione Enter para sair...")
        sys.exit(1)
    elif not gui:
        print(f"[Cycling Overlay] Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} OK")


def is_cache_valid():
    if not os.path.exists(CACHE_FILE):
        return False
    try:
        mtime = os.path.getmtime(CACHE_FILE)
        age_days = (time.time() - mtime) / 86400
        return age_days < CACHE_MAX_AGE_DAYS
    except OSError:
        return False


def write_cache():
    try:
        with open(CACHE_FILE, "w") as f:
            f.write(f"{time.time()}\n")
    except OSError:
        pass


def check_dependencies():
    missing = []
    for mod_name, _ in REQUIRED_PACKAGES:
        try:
            importlib.import_module(mod_name)
        except ImportError:
            missing.append(mod_name)
    return missing


def install_deps(app_dir=None, gui=False):
    if app_dir is None:
        app_dir = APP_DIR

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", app_dir],
        capture_output=gui,
        text=gui,
        check=False,
        timeout=300 if gui else None,
    )
    return result


def ensure_dependencies(gui=False):
    if is_cache_valid():
        missing = check_dependencies()
        if not missing:
            if not gui:
                print("[Cycling Overlay] Dependências OK (cache).")
            return True
        if not gui:
            print(f"[Cycling Overlay] Cache ignorado; dependências faltando: {', '.join(missing)}")

    missing = check_dependencies()
    if not missing:
        write_cache()
        if not gui:
            print("[Cycling Overlay] Dependências OK.")
        return True

    if gui:
        _show_info(
            "Cycling Overlay — Instalando dependências",
            "Primeira execução detectada.\n"
            "Instalando dependências, aguarde...\n\n"
            "Isso pode levar 1-2 minutos.",
        )
    else:
        print(f"[Cycling Overlay] Instalando dependências faltando: {', '.join(missing)}")
        print("[Cycling Overlay] Aguarde, isso pode levar 1-2 minutos...")

    try:
        result = install_deps(gui=gui)
        if result.returncode != 0:
            msg = f"Falha ao instalar dependências (código {result.returncode})."
            if gui:
                stderr = getattr(result, 'stderr', '') or ''
                _show_error(
                    "Cycling Overlay — Erro na instalação",
                    f"{msg}\n{stderr[:500]}\n\nTente executar o arquivo setup.py",
                )
            else:
                print(f"[Cycling Overlay] {msg}")
                print("[Cycling Overlay] Tente executar: python setup.py")
                input("Pressione Enter para sair...")
            sys.exit(1)
    except subprocess.TimeoutExpired:
        if gui:
            _show_error(
                "Cycling Overlay — Timeout",
                "A instalação demorou demais.\n"
                "Verifique sua conexão com a internet e tente novamente.",
            )
        else:
            print("[Cycling Overlay] Timeout na instalação. Verifique sua internet.")
            input("Pressione Enter para sair...")
        sys.exit(1)
    except FileNotFoundError:
        if gui:
            _show_error(
                "Cycling Overlay — pip não encontrado",
                "O pip não está disponível.\n"
                "Reinstale Python marcando a opção 'pip'.\n"
                "Baixe em: https://www.python.org/downloads/",
            )
        else:
            print("[Cycling Overlay] pip não encontrado. Reinstale Python com pip.")
            input("Pressione Enter para sair...")
        sys.exit(1)

    still_missing = check_dependencies()
    if still_missing:
        if gui:
            _show_error(
                "Cycling Overlay — Dependências faltando",
                f"Os seguintes pacotes não puderam ser instalados:\n"
                f"{', '.join(still_missing)}\n\n"
                f"Tente executar o arquivo setup.py como administrador.",
            )
        else:
            print(f"[Cycling Overlay] Falha: {', '.join(still_missing)} ainda faltando.")
            input("Pressione Enter para sair...")
        sys.exit(1)

    if not gui:
        print("[Cycling Overlay] Dependências instaladas com sucesso.")
    write_cache()
    return True


def verify_installation(gui=False):
    if not gui:
        print("\nVerificando instalação...")
    all_ok = True
    for mod_name, _ in REQUIRED_PACKAGES:
        try:
            importlib.import_module(mod_name)
            if not gui:
                print(f"  {mod_name} OK")
        except ImportError:
            if not gui:
                print(f"  {mod_name} FALTANDO")
            all_ok = False

    if not all_ok:
        if not gui:
            print("\nAlgumas dependências ainda estão faltando.")
            print("Tente executar este arquivo como administrador.")
    elif not gui:
        print("\nTodas as dependências estão instaladas!")
    return all_ok


def create_desktop_shortcut():
    if sys.platform != "win32":
        print("\nAtalho no desktop só é criado no Windows.")
        print(f"No Linux/macOS, execute: python3 {os.path.join(SCRIPT_DIR, 'run.pyw')}")
        return

    try:
        import ctypes
        import ctypes.wintypes
    except ImportError:
        print("Não foi possível criar atalho (ctypes indisponível).")
        return

    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    shortcut_path = os.path.join(desktop, "Cycling Overlay.lnk")
    run_pyw = os.path.join(SCRIPT_DIR, "run.pyw")

    try:
        shortcut_content = (
            f'[InternetShortcut]\n'
            f'URL=file:///{run_pyw}\n'
            f'IconIndex=0\n'
        )
        with open(shortcut_path, "w", encoding="utf-8") as f:
            f.write(shortcut_content)
        print("\nAtalho criado no Desktop: Cycling Overlay.lnk")
    except Exception as e:
        print(f"\nNão foi possível criar atalho: {e}")
        print(f"Para abrir o app, execute: pythonw {run_pyw}")


def save_error_log(error_traceback):
    log_path = os.path.join(os.path.expanduser("~"), "cycling-overlay-error.log")
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"Cycling Overlay — Erro em {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(error_traceback)
    except OSError:
        pass
    return log_path


def setup_path():
    os.chdir(APP_DIR)
    if APP_DIR not in sys.path:
        sys.path.insert(0, APP_DIR)


def run_app():
    from main import main as app_main
    app_main()


def ensure_and_run(gui=False):
    check_python_version(gui=gui)
    ensure_dependencies(gui=gui)
    setup_path()

    if gui:
        try:
            run_app()
        except Exception:
            error_tb = traceback.format_exc()
            log_path = save_error_log(error_tb)
            _show_error(
                "Cycling Overlay — Erro",
                f"Ocorreu um erro ao abrir o app.\n\n"
                f"Detalhes salvos em:\n{log_path}\n\n"
                f"Envie este arquivo ao suporte.",
            )
            sys.exit(1)
    else:
        print("[Cycling Overlay] Iniciando app...")
        try:
            run_app()
        except Exception:
            print("\n[Cycling Overlay] Erro ao iniciar o app:")
            traceback.print_exc()
            input("Pressione Enter para sair...")
            sys.exit(1)


def install_and_verify(gui=False):
    check_python_version(gui=gui)

    if not gui:
        print("=" * 50)
        print("  Cycling Overlay — Instalador")
        print("=" * 50)
        print()

    if not gui:
        import subprocess as _sp
        try:
            _sp.run(
                [sys.executable, "-m", "pip", "--version"],
                capture_output=True,
                check=True,
            )
            print("pip OK")
        except (_sp.CalledProcessError, FileNotFoundError):
            print("Erro: pip não encontrado.")
            print("Reinstale Python marcando a opção 'pip'.")
            print("Baixe em: https://www.python.org/downloads/")
            input("Pressione Enter para sair...")
            sys.exit(1)

    ensure_dependencies(gui=gui)

    if verify_installation(gui=gui):
        create_desktop_shortcut()
        if not gui:
            print("\n" + "=" * 50)
            print("  Instalação concluída!")
            print("  Para abrir o app, dê duplo-clique em run.pyw")
            print("=" * 50)

    if not gui:
        print()
        input("Pressione Enter para sair...")


def _show_error(title, message):
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message)
        root.destroy()
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
        except Exception:
            print(f"{title}: {message}", file=sys.stderr)


def _show_info(title, message):
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(title, message)
        root.destroy()
    except Exception:
        pass
