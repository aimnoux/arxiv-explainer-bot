#!/bin/bash
set -e

WORKDIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="arxiv-bot"
SERVICE_FILE="$WORKDIR/arxiv_bot.service"
SYSTEM_SERVICE="/etc/systemd/system/${SERVICE_NAME}.service"

# ── 1. Root check ─────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo "Запустите скрипт с sudo: sudo ./setup.sh"
    exit 1
fi

REAL_USER="${SUDO_USER:-$(logname 2>/dev/null || echo root)}"

echo "╔══════════════════════════════════════╗"
echo "║   ArXiv Explainer Bot — Установка   ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 2. System packages ────────────────────────────────────────────────────────
echo "→ Обновляю apt и устанавливаю зависимости..."
apt-get update -qq
apt-get install -y -qq python3.11 python3.11-venv python3-pip git curl

# ── 3. Virtual environment ────────────────────────────────────────────────────
echo "→ Создаю виртуальное окружение..."
python3.11 -m venv "$WORKDIR/.venv"

echo "→ Устанавливаю Python-зависимости..."
"$WORKDIR/.venv/bin/pip" install --quiet --upgrade pip
"$WORKDIR/.venv/bin/pip" install --quiet -r "$WORKDIR/requirements.txt"

# ── 4. Config wizard ──────────────────────────────────────────────────────────
echo ""
echo "→ Запускаю мастер настройки..."
echo ""
sudo -u "$REAL_USER" "$WORKDIR/.venv/bin/python" -m bot.wizard

# ── 5. Systemd service (optional) ─────────────────────────────────────────────
echo ""
read -r -p "Установить systemd-сервис для автозапуска? [y/N]: " INSTALL_SERVICE
if [[ "$INSTALL_SERVICE" =~ ^[Yy]$ ]]; then
    echo "→ Устанавливаю systemd-сервис..."

    sed \
        -e "s|REPLACE_USER|$REAL_USER|g" \
        -e "s|REPLACE_WORKDIR|$WORKDIR|g" \
        "$SERVICE_FILE" > "$SYSTEM_SERVICE"

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    systemctl restart "$SERVICE_NAME"

    echo ""
    echo "✅ Сервис установлен и запущен."
    echo "   Статус:    sudo systemctl status $SERVICE_NAME"
    echo "   Логи:      sudo journalctl -u $SERVICE_NAME -f"
    echo "   Перезапуск: sudo systemctl restart $SERVICE_NAME"
else
    echo ""
    echo "✅ Установка завершена."
    echo "   Запуск бота: $WORKDIR/.venv/bin/python -m bot.main"
fi
