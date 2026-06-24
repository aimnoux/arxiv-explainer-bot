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
apt-get install -y -qq python3 python3-venv python3-pip git curl

# ── 3. Detect Python ≥ 3.11 ──────────────────────────────────────────────────
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" -c 'import sys; print(sys.version_info >= (3,11))')
        if [[ "$ver" == "True" ]]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "❌ Python 3.11+ не найден. Установите его вручную и запустите скрипт снова."
    exit 1
fi
echo "   Используется: $PYTHON ($($PYTHON --version))"

# ── 4. Virtual environment ────────────────────────────────────────────────────
echo "→ Создаю виртуальное окружение..."
"$PYTHON" -m venv "$WORKDIR/.venv"

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
fi

# ── 6. Global CLI command ─────────────────────────────────────────────────────
echo "→ Устанавливаю команду 'arxiv-bot'..."
cat > /usr/local/bin/arxiv-bot << EOF
#!/bin/bash
cd "$WORKDIR"
exec "$WORKDIR/.venv/bin/python" -m bot.cli "\$@"
EOF
chmod +x /usr/local/bin/arxiv-bot

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════╗"
echo "║          Установка завершена!        ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "  Запустить панель управления:"
echo "    arxiv-bot"
echo ""
if [[ "$INSTALL_SERVICE" =~ ^[Yy]$ ]]; then
    echo "  Бот уже работает (systemd)."
    echo "  Логи: sudo journalctl -u $SERVICE_NAME -f"
fi
echo ""

# Launch CLI immediately
exec sudo -u "$REAL_USER" /usr/local/bin/arxiv-bot
