"""Admin panel — inline keyboard interface for bot owner only."""
import asyncio
import subprocess
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .config import PROVIDERS, load_config, save_config
from .model_fetcher import fetch_models

WORKDIR = Path(__file__).parent.parent
MODELS_PAGE_SIZE = 8


# ── Auth ──────────────────────────────────────────────────────────────────────

def is_admin(update: Update) -> bool:
    try:
        return update.effective_user.id == load_config().get("admin_user_id")
    except Exception:
        return False


# ── Keyboard builders ─────────────────────────────────────────────────────────

def _kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=cb) for label, cb in row]
        for row in rows
    ])


def main_menu_kb() -> InlineKeyboardMarkup:
    return _kb([
        [("⚙️ Провайдер / Модель", "adm:provider")],
        [("🔑 API-ключ", "adm:key"), ("🌍 Язык", "adm:lang")],
        [("📊 Статус", "adm:status"), ("📋 Логи", "adm:logs")],
        [("🔄 Обновления", "adm:updates"), ("♻️ Перезапуск", "adm:restart")],
    ])


def provider_kb() -> InlineKeyboardMarkup:
    rows = []
    keys = list(PROVIDERS.keys())
    for i in range(0, len(keys), 2):
        row = []
        for key in keys[i:i + 2]:
            p = PROVIDERS[key]
            badge = "✅" if p["free"] else "💰"
            row.append((f"{badge} {p['name']}", f"adm:prov:{key}"))
        rows.append(row)
    rows.append([("⬅️ Назад", "adm:menu")])
    return _kb(rows)


def model_kb(models: list[dict], page: int = 0) -> InlineKeyboardMarkup:
    free = [m for m in models if m["free"]]
    paid = [m for m in models if not m["free"]]
    flat = free + paid

    start = page * MODELS_PAGE_SIZE
    end = min(start + MODELS_PAGE_SIZE, len(flat))

    rows = []
    for m in flat[start:end]:
        badge = "✅" if m["free"] else "💰"
        label = f"{badge} {m['name'][:38]}"
        rows.append([(label, f"adm:model:{m['id']}")])

    nav = []
    if page > 0:
        nav.append(("◀️", f"adm:mpage:{page - 1}"))
    if end < len(flat):
        nav.append((f"▶️ ({end}/{len(flat)})", f"adm:mpage:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([("❌ Отмена", "adm:menu")])
    return _kb(rows)


def lang_kb() -> InlineKeyboardMarkup:
    return _kb([
        [("🇷🇺 Русский", "adm:setlang:ru"), ("🇬🇧 English", "adm:setlang:en")],
        [("⬅️ Назад", "adm:menu")],
    ])


def back_kb() -> InlineKeyboardMarkup:
    return _kb([[("⬅️ Назад", "adm:menu")]])


# ── Menu text ─────────────────────────────────────────────────────────────────

def menu_text() -> str:
    cfg = load_config()
    pkey = cfg.get("llm_provider", "?")
    pname = PROVIDERS.get(pkey, {}).get("name", pkey)
    model = cfg.get("llm_model", "?")
    lang = "Русский 🇷🇺" if cfg.get("language", "ru") == "ru" else "English 🇬🇧"
    return (
        "<b>🛠 Панель администратора</b>\n\n"
        f"Провайдер: <code>{pname}</code>\n"
        f"Модель: <code>{model}</code>\n"
        f"Язык: {lang}"
    )


# ── Entry point ───────────────────────────────────────────────────────────────

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        uid = update.effective_user.id
        try:
            stored = load_config().get("admin_user_id", "не задан")
        except Exception:
            stored = "ошибка загрузки конфига"
        await update.message.reply_text(
            f"⛔ Нет доступа.\n\n"
            f"Ваш Telegram ID: <code>{uid}</code>\n"
            f"ID администратора в конфиге: <code>{stored}</code>\n\n"
            f"Если это вы, обновите конфиг:\n"
            f"<code>python3 -m bot.wizard</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    context.user_data.clear()
    await update.message.reply_text(menu_text(), reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    await update.message.reply_text(
        f"🪪 Ваш Telegram ID: <code>{uid}</code>",
        parse_mode=ParseMode.HTML,
    )


# ── Callback router ───────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return

    q = update.callback_query
    await q.answer()
    data: str = q.data

    # ── Back to menu ──────────────────────────────────────────────────────────
    if data == "adm:menu":
        context.user_data.clear()
        await q.edit_message_text(menu_text(), reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)

    # ── Provider selection ────────────────────────────────────────────────────
    elif data == "adm:provider":
        await q.edit_message_text("Выберите провайдера LLM:", reply_markup=provider_kb())

    elif data.startswith("adm:prov:"):
        pkey = data[len("adm:prov:"):]
        pcfg = PROVIDERS[pkey]
        context.user_data["awaiting"] = "key"
        context.user_data["temp_provider"] = pkey
        await q.edit_message_text(
            f"Провайдер: <b>{pcfg['name']}</b>\n\n"
            f"Получить ключ: {pcfg['docs']}\n\n"
            "Введите API-ключ (сообщение удалится автоматически):",
            parse_mode=ParseMode.HTML,
        )

    # ── Key only (keep provider) ──────────────────────────────────────────────
    elif data == "adm:key":
        context.user_data["awaiting"] = "key_only"
        cfg = load_config()
        pname = PROVIDERS.get(cfg.get("llm_provider", ""), {}).get("name", "?")
        await q.edit_message_text(
            f"Текущий провайдер: <b>{pname}</b>\n\n"
            "Введите новый API-ключ (сообщение удалится автоматически):",
            parse_mode=ParseMode.HTML,
        )

    # ── Model page navigation ─────────────────────────────────────────────────
    elif data.startswith("adm:mpage:"):
        page = int(data[len("adm:mpage:"):])
        models = context.user_data.get("models", [])
        await q.edit_message_text("Выберите модель:", reply_markup=model_kb(models, page))

    # ── Model selected ────────────────────────────────────────────────────────
    elif data.startswith("adm:model:"):
        model_id = data[len("adm:model:"):]
        cfg = load_config()
        if "temp_provider" in context.user_data:
            cfg["llm_provider"] = context.user_data["temp_provider"]
        if "temp_key" in context.user_data:
            cfg["llm_api_key"] = context.user_data["temp_key"]
        cfg["llm_model"] = model_id
        save_config(cfg)
        context.user_data.clear()
        await q.edit_message_text(
            f"✅ Сохранено: <code>{model_id}</code>",
            parse_mode=ParseMode.HTML,
        )
        await asyncio.sleep(1.5)
        await q.edit_message_text(menu_text(), reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)

    # ── Language ──────────────────────────────────────────────────────────────
    elif data == "adm:lang":
        await q.edit_message_text("Выберите язык ответов:", reply_markup=lang_kb())

    elif data.startswith("adm:setlang:"):
        lang = data[len("adm:setlang:"):]
        cfg = load_config()
        cfg["language"] = lang
        save_config(cfg)
        label = "Русский 🇷🇺" if lang == "ru" else "English 🇬🇧"
        await q.edit_message_text(f"✅ Язык: <b>{label}</b>", parse_mode=ParseMode.HTML)
        await asyncio.sleep(1.5)
        await q.edit_message_text(menu_text(), reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)

    # ── Status ────────────────────────────────────────────────────────────────
    elif data == "adm:status":
        cfg = load_config()
        pkey = cfg.get("llm_provider", "?")
        pname = PROVIDERS.get(pkey, {}).get("name", pkey)
        text = (
            "<b>📊 Статус</b>\n\n"
            f"Провайдер: <code>{pname}</code>\n"
            f"Модель: <code>{cfg.get('llm_model', '?')}</code>\n"
            f"Язык: {'Русский 🇷🇺' if cfg.get('language','ru') == 'ru' else 'English 🇬🇧'}\n"
            f"Макс. страниц PDF: <code>{cfg.get('max_paper_pages', 20)}</code>"
        )
        await q.edit_message_text(text, reply_markup=back_kb(), parse_mode=ParseMode.HTML)

    # ── Logs ──────────────────────────────────────────────────────────────────
    elif data == "adm:logs":
        logs = _get_logs()
        await q.edit_message_text(
            f"<b>📋 Логи</b>\n\n<pre>{logs}</pre>",
            reply_markup=back_kb(),
            parse_mode=ParseMode.HTML,
        )

    # ── Updates ───────────────────────────────────────────────────────────────
    elif data == "adm:updates":
        await q.edit_message_text("🔄 Проверяю обновления...")
        has_upd, msg = _check_updates()
        if has_upd:
            kb = _kb([
                [("⬇️ Установить", "adm:do_update")],
                [("⬅️ Назад", "adm:menu")],
            ])
            await q.edit_message_text(f"🆕 {msg}", reply_markup=kb)
        else:
            await q.edit_message_text(f"✅ {msg}", reply_markup=back_kb())

    elif data == "adm:do_update":
        await q.edit_message_text("⏳ Устанавливаю обновления...")
        ok, err = _do_update()
        if ok:
            await q.edit_message_text("✅ Обновлено! Перезапускаюсь через 3 секунды...")
            await asyncio.sleep(3)
            subprocess.Popen(["systemctl", "restart", "arxiv-bot"])
        else:
            await q.edit_message_text(f"❌ Ошибка: <code>{err}</code>", reply_markup=back_kb(), parse_mode=ParseMode.HTML)

    # ── Restart ───────────────────────────────────────────────────────────────
    elif data == "adm:restart":
        kb = _kb([
            [("✅ Да", "adm:do_restart"), ("❌ Отмена", "adm:menu")],
        ])
        await q.edit_message_text("♻️ Перезапустить бота?", reply_markup=kb)

    elif data == "adm:do_restart":
        await q.edit_message_text("♻️ Перезапускаюсь...")
        await asyncio.sleep(2)
        subprocess.Popen(["systemctl", "restart", "arxiv-bot"])


# ── Text handler (called from handlers.py) ────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Handle text input during multi-step admin flows.
    Returns True if message was consumed, False otherwise.
    """
    if not is_admin(update):
        return False

    awaiting = context.user_data.get("awaiting")
    if not awaiting:
        return False

    api_key = update.message.text.strip()

    # Delete message containing the key for security
    try:
        await update.message.delete()
    except Exception:
        pass

    if awaiting == "key_only":
        cfg = load_config()
        cfg["llm_api_key"] = api_key
        save_config(cfg)
        context.user_data.clear()
        msg = await update.message.reply_text("✅ API-ключ обновлён.")
        await asyncio.sleep(2)
        await msg.edit_text(menu_text(), reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)
        return True

    if awaiting == "key":
        pkey = context.user_data.get("temp_provider")
        pcfg = PROVIDERS[pkey]
        context.user_data["temp_key"] = api_key

        status = await update.message.reply_text(f"⏳ Загружаю модели {pcfg['name']}...")
        try:
            models = await fetch_models(pkey, pcfg.get("base_url"), api_key)
            context.user_data["models"] = models
            context.user_data.pop("awaiting", None)
            free_n = sum(1 for m in models if m["free"])
            await status.edit_text(
                f"✅ {len(models)} моделей (✅ {free_n} бесплатных)\n\nВыберите модель:",
                reply_markup=model_kb(models, 0),
            )
        except Exception as e:
            context.user_data.clear()
            await status.edit_text(
                f"❌ Не удалось загрузить модели: <code>{e}</code>\n\nПроверьте ключ.",
                reply_markup=back_kb(),
                parse_mode=ParseMode.HTML,
            )
        return True

    return False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_logs(n: int = 30) -> str:
    try:
        r = subprocess.run(
            ["journalctl", "-u", "arxiv-bot", "-n", str(n), "--no-pager", "--output=short"],
            capture_output=True, text=True, timeout=10,
        )
        text = r.stdout.strip() or "(логи пусты)"
        return text[-3500:] if len(text) > 3500 else text
    except Exception as e:
        return f"(ошибка: {e})"


def _check_updates() -> tuple[bool, str]:
    try:
        subprocess.run(["git", "fetch", "origin", "--quiet"], cwd=WORKDIR, capture_output=True, timeout=15)
        local = subprocess.run(["git", "rev-parse", "HEAD"], cwd=WORKDIR, capture_output=True, text=True).stdout.strip()
        remote = subprocess.run(["git", "rev-parse", "origin/main"], cwd=WORKDIR, capture_output=True, text=True).stdout.strip()
        if local == remote:
            return False, f"Уже последняя версия ({local[:7]})"
        count = subprocess.run(
            ["git", "rev-list", "--count", f"{local}..{remote}"],
            cwd=WORKDIR, capture_output=True, text=True,
        ).stdout.strip()
        return True, f"Доступно {count} новых коммит(а) → {remote[:7]}"
    except Exception as e:
        return False, f"Ошибка проверки: {e}"


def _do_update() -> tuple[bool, str]:
    try:
        subprocess.run(["git", "pull", "origin", "main"], cwd=WORKDIR, capture_output=True, timeout=60, check=True)
        pip = WORKDIR / ".venv" / "bin" / "pip"
        if pip.exists():
            subprocess.run(
                [str(pip), "install", "-q", "-r", str(WORKDIR / "requirements.txt")],
                timeout=180, check=True,
            )
        return True, ""
    except subprocess.CalledProcessError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)
