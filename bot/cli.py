"""Persistent CLI manager for arxiv-explainer-bot. Entry: `arxiv-bot`"""
import os
import subprocess
import sys
import time
from pathlib import Path

WORKDIR = Path(__file__).parent.parent
SERVICE_NAME = "arxiv-bot"
PID_FILE = WORKDIR / ".bot.pid"

# ANSI
GREEN  = "\033[1;32m"
RED    = "\033[1;31m"
YELLOW = "\033[1;33m"
CYAN   = "\033[1;36m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"


# ── bot control ───────────────────────────────────────────────────────────────

def _systemd_available() -> bool:
    return Path(f"/etc/systemd/system/{SERVICE_NAME}.service").exists()


def get_bot_status() -> tuple[bool, str]:
    if _systemd_available():
        r = subprocess.run(
            ["systemctl", "is-active", SERVICE_NAME],
            capture_output=True, text=True,
        )
        return r.stdout.strip() == "active", "systemd"
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return True, f"PID {pid}"
        except (ValueError, ProcessLookupError, OSError):
            PID_FILE.unlink(missing_ok=True)
    return False, ""


def start_bot() -> str:
    if _systemd_available():
        r = subprocess.run(["systemctl", "start", SERVICE_NAME], capture_output=True, text=True)
        return "Бот запущен (systemd)" if r.returncode == 0 else f"Ошибка: {r.stderr.strip()}"
    proc = subprocess.Popen(
        [sys.executable, "-m", "bot.main"],
        cwd=WORKDIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    PID_FILE.write_text(str(proc.pid))
    return f"Бот запущен (PID {proc.pid})"


def stop_bot() -> str:
    if _systemd_available():
        r = subprocess.run(["systemctl", "stop", SERVICE_NAME], capture_output=True, text=True)
        return "Бот остановлен" if r.returncode == 0 else f"Ошибка: {r.stderr.strip()}"
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 15)
            PID_FILE.unlink(missing_ok=True)
            return "Бот остановлен"
        except Exception as e:
            return f"Ошибка: {e}"
    return "Бот не был запущен"


# ── updates ───────────────────────────────────────────────────────────────────

def fetch_updates() -> tuple[bool | None, str]:
    """Returns (has_updates, message). None = check failed."""
    try:
        subprocess.run(
            ["git", "fetch", "origin", "--quiet"],
            cwd=WORKDIR, capture_output=True, timeout=15,
        )
        local = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=WORKDIR, capture_output=True, text=True,
        ).stdout.strip()
        remote = subprocess.run(
            ["git", "rev-parse", "origin/main"],
            cwd=WORKDIR, capture_output=True, text=True,
        ).stdout.strip()
        if local == remote:
            return False, f"Уже последняя версия ({local[:7]})"
        count = subprocess.run(
            ["git", "rev-list", "--count", f"{local}..{remote}"],
            cwd=WORKDIR, capture_output=True, text=True,
        ).stdout.strip()
        return True, f"Доступно {count} новых коммит(а)  {local[:7]} → {remote[:7]}"
    except Exception as e:
        return None, f"Не удалось проверить: {e}"


def do_install_updates() -> None:
    _clear()
    print(f"{BOLD}╔══════════════════════════════════════╗{RESET}")
    print(f"{BOLD}║        Установка обновлений         ║{RESET}")
    print(f"{BOLD}╚══════════════════════════════════════╝{RESET}\n")

    print(f"{BOLD}→ Скачиваю обновления (git pull)...{RESET}")
    subprocess.run(["git", "pull", "origin", "main"], cwd=WORKDIR)

    pip = WORKDIR / ".venv" / "bin" / "pip"
    if pip.exists():
        print(f"\n{BOLD}→ Обновляю зависимости...{RESET}")
        subprocess.run([str(pip), "install", "-q", "-r", str(WORKDIR / "requirements.txt")])

    # Restart bot service so it picks up new code
    was_running, _ = get_bot_status()
    if was_running:
        print(f"\n{BOLD}→ Перезапускаю сервис бота...{RESET}")
        if _systemd_available():
            subprocess.run(["systemctl", "restart", SERVICE_NAME])
        elif PID_FILE.exists():
            stop_bot()
            time.sleep(1)
            start_bot()
        print(f"{GREEN}✓ Бот перезапущен с новым кодом.{RESET}")

    print(f"\n{GREEN}✅ Обновление завершено. Перезапускаю утилиту...{RESET}\n")
    time.sleep(1.5)
    os.chdir(str(WORKDIR))
    os.execv(sys.executable, [sys.executable, "-m", "bot.cli"])


# ── misc actions ──────────────────────────────────────────────────────────────

def show_logs() -> None:
    _clear()
    print(f"{BOLD}Логи бота{RESET} {DIM}(Ctrl+C для возврата){RESET}\n")
    if _systemd_available():
        try:
            subprocess.run(
                ["journalctl", "-u", SERVICE_NAME, "-n", "80", "--no-pager"],
                cwd=WORKDIR,
            )
        except KeyboardInterrupt:
            pass
    else:
        running, info = get_bot_status()
        if running:
            print(f"Бот запущен ({info}). Логи выводятся в stdout процесса.")
        else:
            print("Бот не запущен.")
    input(f"\n{DIM}Нажмите Enter для возврата...{RESET}")


def run_wizard() -> None:
    _clear()
    subprocess.run([sys.executable, "-m", "bot.wizard"], cwd=WORKDIR)
    input(f"\n{DIM}Нажмите Enter для возврата в меню...{RESET}")


# ── drawing ───────────────────────────────────────────────────────────────────

def _clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _draw(
    bot_running: bool,
    updates_checked: bool,
    updates_available: bool | None,
    update_msg: str,
    last_action: str,
) -> None:
    _clear()
    print(f"{BOLD}╔══════════════════════════════════════╗{RESET}")
    print(f"{BOLD}║     ArXiv Explainer Bot — CLI       ║{RESET}")
    print(f"{BOLD}╚══════════════════════════════════════╝{RESET}")
    print()

    if bot_running:
        dot, label = f"{GREEN}●{RESET}", f"{GREEN}работает{RESET}"
    else:
        dot, label = f"{RED}○{RESET}", f"{RED}остановлен{RESET}"
    print(f"  Статус бота: {dot} {label}")
    print()

    toggle = f"{RED}Остановить бота{RESET}" if bot_running else f"{GREEN}Запустить бота{RESET}"
    print(f"  {BOLD}[1]{RESET} {toggle}")
    print(f"  {BOLD}[2]{RESET} Настроить (wizard)")
    print(f"  {BOLD}[3]{RESET} Показать логи")
    print(f"  {BOLD}[4]{RESET} Проверить обновления")

    if updates_checked and updates_available:
        print(f"  {YELLOW}{BOLD}[5] ✨ Установить обновления        ← ДОСТУПНО{RESET}")
    elif updates_checked and updates_available is False:
        print(f"  {DIM}[5] Установить обновления  (нет обновлений){RESET}")
    else:
        print(f"  {DIM}[5] Установить обновления  (сначала [4]){RESET}")

    print()
    print(f"  {BOLD}[0]{RESET} Выход")
    print()

    if updates_checked and update_msg:
        color = GREEN if updates_available is False else (YELLOW if updates_available else RED)
        print(f"  {color}ℹ  {update_msg}{RESET}")
        print()

    if last_action:
        print(f"  {CYAN}»  {last_action}{RESET}")
        print()


# ── main loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    os.chdir(str(WORKDIR))

    updates_checked = False
    updates_available: bool | None = None
    update_msg = ""
    last_action = ""

    while True:
        bot_running, _ = get_bot_status()
        _draw(bot_running, updates_checked, updates_available, update_msg, last_action)

        try:
            choice = input("  Выберите действие: ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{DIM}Bye!{RESET}\n")
            sys.exit(0)

        if choice == "1":
            last_action = stop_bot() if bot_running else start_bot()

        elif choice == "2":
            run_wizard()
            last_action = "Настройка завершена."

        elif choice == "3":
            show_logs()
            last_action = ""

        elif choice == "4":
            last_action = "Проверяю обновления..."
            _draw(bot_running, updates_checked, updates_available, update_msg, last_action)
            updates_available, update_msg = fetch_updates()
            updates_checked = True
            last_action = update_msg

        elif choice == "5":
            if not updates_checked:
                last_action = "Сначала проверьте обновления — [4]."
            elif not updates_available:
                last_action = "Обновлений нет."
            else:
                do_install_updates()  # os.execv — не возвращается

        elif choice == "0":
            print(f"\n{DIM}Bye!{RESET}\n")
            sys.exit(0)

        else:
            last_action = f"Неизвестная команда: {choice!r}"


if __name__ == "__main__":
    main()
