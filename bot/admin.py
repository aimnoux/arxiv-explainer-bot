"""Admin panel — inline keyboard interface for bot owner only."""
import asyncio
import subprocess
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .config import PROVIDERS, load_config, save_config
from .model_fetcher import fetch_models as _fetch_models

WORKDIR = Path(__file__).parent.parent
PAGE = 8

# Module-level cache so pagination survives context.user_data resets
_models_cache: dict[int, list[dict]] = {}


# ── Auth ──────────────────────────────────────────────────────────────────────

def is_admin(update: Update) -> bool:
    try:
        return update.effective_user.id == load_config().get("admin_user_id")
    except Exception:
        return False


# ── Keyboard helpers ──────────────────────────────────────────────────────────

def _kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=cb) for label, cb in row]
        for row in rows
    ])


def _back(dest: str = "adm:menu", label: str = "⬅️ Назад") -> list[tuple[str, str]]:
    return [(label, dest)]


# ── Keyboards ─────────────────────────────────────────────────────────────────

def main_menu_kb() -> InlineKeyboardMarkup:
    return _kb([
        [("⚙️ Провайдер / Модель", "adm:provider")],
        [("🔑 API-ключ", "adm:key_only"), ("🌍 Язык", "adm:lang")],
        [("📊 Статус", "adm:status"), ("📋 Логи", "adm:logs")],
        [("🔄 Проверить и установить обновления", "adm:updates")],
        [("♻️ Перезапуск", "adm:restart")],
    ])


def provider_kb() -> InlineKeyboardMarkup:
    cfg = load_config()
    current = cfg.get("llm_provider", "")
    rows = []
    keys = list(PROVIDERS.keys())
    for i in range(0, len(keys), 2):
        row = []
        for key in keys[i:i + 2]:
            p = PROVIDERS[key]
            badge = "✅" if p["free"] else "💰"
            mark = " ✓" if key == current else ""
            row.append((f"{badge} {p['name']}{mark}", f"adm:prov:{key}"))
        rows.append(row)
    if current:
        pname = PROVIDERS.get(current, {}).get("name", current)
        rows.append([(f"↩️ Оставить: {pname}", "adm:prov:keep")])
    rows.append(_back())
    return _kb(rows)


def key_entry_kb() -> InlineKeyboardMarkup:
    return _kb([
        [("✅ Использовать текущий ключ", "adm:key:keep")],
        [("⬅️ К выбору провайдера", "adm:provider")],
    ])


def model_kb(models: list[dict], page: int, current_model: str = "") -> InlineKeyboardMarkup:
    free = [m for m in models if m["free"]]
    paid = [m for m in models if not m["free"]]
    flat = free + paid

    start = page * PAGE
    end = min(start + PAGE, len(flat))

    rows = []
    for m in flat[start:end]:
        badge = "✅" if m["free"] else "💰"
        mark = " ✓" if m["id"] == current_model else ""
        label = f"{badge} {m['name'][:35]}{mark}"
        rows.append([(label, f"adm:model:{m['id']}")])

    nav = []
    if page > 0:
        nav.append(("◀️", f"adm:mpage:{page - 1}"))
    if end < len(flat):
        nav.append((f"▶️ {end}/{len(flat)}", f"adm:mpage:{page + 1}"))
    if nav:
        rows.append(nav)

    if current_model:
        short = current_model.split("/")[-1][:32]
        rows.append([(f"↩️ Оставить: {short}", "adm:model:keep")])
    rows.append([
        ("⬅️ К ключу", "adm:back_to_key"),
        ("✖️ Отмена", "adm:menu"),
    ])
    return _kb(rows)


def lang_kb() -> InlineKeyboardMarkup:
    current = load_config().get("language", "ru")
    return _kb([
        [
            (f"🇷🇺 Русский{'  ✓' if current == 'ru' else ''}", "adm:setlang:ru"),
            (f"🇬🇧 English{'  ✓' if current == 'en' else ''}", "adm:setlang:en"),
        ],
        [(f"↩️ Оставить текущий", "adm:menu")],
        _back(),
    ])


def back_kb(dest: str = "adm:menu") -> InlineKeyboardMarkup:
    return _kb([_back(dest)])


# ── State helpers ─────────────────────────────────────────────────────────────

def _uid(update: Update) -> int:
    return update.effective_user.id


def _save_models(uid: int, models: list[dict], ctx: ContextTypes.DEFAULT_TYPE) -> None:
    _models_cache[uid] = models
    ctx.user_data["models"] = models


def _load_models(uid: int, ctx: ContextTypes.DEFAULT_TYPE) -> list[dict]:
    return ctx.user_data.get("models") or _models_cache.get(uid, [])


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


# ── Shared actions ────────────────────────────────────────────────────────────

async def _to_menu(q, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.user_data.clear()
    await q.edit_message_text(menu_text(), reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)


async def _do_fetch_models(q, uid: int, pkey: str, api_key: str, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    pcfg = PROVIDERS.get(pkey, {})
    try:
        models = await _fetch_models(pkey, pcfg.get("base_url"), api_key)
        _save_models(uid, models, ctx)
        cfg = load_config()
        free_n = sum(1 for m in models if m["free"])
        await q.edit_message_text(
            f"Загружено {len(models)} моделей  (✅ {free_n} бесплатных)\n\nВыберите модель:",
            reply_markup=model_kb(models, 0, cfg.get("llm_model", "")),
        )
    except Exception as e:
        await q.edit_message_text(
            f"❌ Не удалось загрузить модели: <code>{e}</code>",
            reply_markup=_kb([
                [("🔄 Попробовать снова", "adm:key:keep")],
                [("⬅️ К выбору провайдера", "adm:provider")],
            ]),
            parse_mode=ParseMode.HTML,
        )


# ── Entry points ──────────────────────────────────────────────────────────────

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет доступа.")
        return
    context.user_data.clear()
    await update.message.reply_text(menu_text(), reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"🪪 Ваш Telegram ID: <code>{update.effective_user.id}</code>",
        parse_mode=ParseMode.HTML,
    )


# ── Callback router ───────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        await update.callback_query.answer("⛔ Нет доступа.")
        return

    q = update.callback_query
    await q.answer()
    data: str = q.data
    uid = _uid(update)
    cfg = load_config()

    # ── Menu ──────────────────────────────────────────────────────────────────
    if data == "adm:menu":
        await _to_menu(q, context)

    # ── Provider ──────────────────────────────────────────────────────────────
    elif data == "adm:provider":
        for k in ("temp_provider", "temp_key", "models", "awaiting"):
            context.user_data.pop(k, None)
        await q.edit_message_text("Выберите провайдера LLM:", reply_markup=provider_kb())

    elif data == "adm:prov:keep":
        pkey = cfg.get("llm_provider", "")
        context.user_data["temp_provider"] = pkey
        context.user_data["awaiting"] = "key"
        pname = PROVIDERS.get(pkey, {}).get("name", pkey)
        await q.edit_message_text(
            f"Провайдер: <b>{pname}</b>\n\nВведите новый ключ или используйте текущий:",
            reply_markup=key_entry_kb(),
            parse_mode=ParseMode.HTML,
        )

    elif data.startswith("adm:prov:"):
        pkey = data[len("adm:prov:"):]
        pcfg = PROVIDERS.get(pkey, {})
        context.user_data["temp_provider"] = pkey
        context.user_data["awaiting"] = "key"
        await q.edit_message_text(
            f"Провайдер: <b>{pcfg.get('name', pkey)}</b>\n\n"
            f"Получить ключ: {pcfg.get('docs', '')}\n\n"
            "Введите API-ключ или используйте текущий:",
            reply_markup=key_entry_kb(),
            parse_mode=ParseMode.HTML,
        )

    # ── Key use current ───────────────────────────────────────────────────────
    elif data == "adm:key:keep":
        pkey = context.user_data.get("temp_provider", cfg.get("llm_provider", ""))
        api_key = context.user_data.get("temp_key") or cfg.get("llm_api_key", "")
        context.user_data["temp_provider"] = pkey
        context.user_data["temp_key"] = api_key
        context.user_data.pop("awaiting", None)
        await q.edit_message_text("⏳ Загружаю модели...")
        await _do_fetch_models(q, uid, pkey, api_key, context)

    # ── Back to key entry from model list ─────────────────────────────────────
    elif data == "adm:back_to_key":
        pkey = context.user_data.get("temp_provider", cfg.get("llm_provider", ""))
        context.user_data["awaiting"] = "key"
        context.user_data.pop("models", None)
        pname = PROVIDERS.get(pkey, {}).get("name", pkey)
        await q.edit_message_text(
            f"Провайдер: <b>{pname}</b>\n\nВведите API-ключ или используйте текущий:",
            reply_markup=key_entry_kb(),
            parse_mode=ParseMode.HTML,
        )

    # ── Key only change ───────────────────────────────────────────────────────
    elif data == "adm:key_only":
        context.user_data["awaiting"] = "key_only"
        pname = PROVIDERS.get(cfg.get("llm_provider", ""), {}).get("name", "?")
        await q.edit_message_text(
            f"Текущий провайдер: <b>{pname}</b>\n\n"
            "Введите новый API-ключ (сообщение удалится автоматически):",
            reply_markup=back_kb(),
            parse_mode=ParseMode.HTML,
        )

    # ── Model pagination ──────────────────────────────────────────────────────
    elif data.startswith("adm:mpage:"):
        page = int(data[len("adm:mpage:"):])
        models = _load_models(uid, context)
        if not models:
            await q.edit_message_text(
                "⚠️ Список моделей устарел. Загрузите заново.",
                reply_markup=back_kb("adm:provider"),
            )
            return
        await q.edit_message_text(
            f"Выберите модель (стр. {page + 1}):",
            reply_markup=model_kb(models, page, cfg.get("llm_model", "")),
        )

    # ── Model keep current ────────────────────────────────────────────────────
    elif data == "adm:model:keep":
        if "temp_provider" in context.user_data:
            cfg["llm_provider"] = context.user_data["temp_provider"]
        if "temp_key" in context.user_data:
            cfg["llm_api_key"] = context.user_data["temp_key"]
        save_config(cfg)
        context.user_data.clear()
        await q.edit_message_text("✅ Провайдер/ключ сохранены, модель не изменена.")
        await asyncio.sleep(1.5)
        await q.edit_message_text(menu_text(), reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)

    # ── Model selected ────────────────────────────────────────────────────────
    elif data.startswith("adm:model:"):
        model_id = data[len("adm:model:"):]
        if "temp_provider" in context.user_data:
            cfg["llm_provider"] = context.user_data["temp_provider"]
        if "temp_key" in context.user_data:
            cfg["llm_api_key"] = context.user_data["temp_key"]
        cfg["llm_model"] = model_id
        save_config(cfg)
        context.user_data.clear()
        await q.edit_message_text(f"✅ Сохранено:\n<code>{model_id}</code>", parse_mode=ParseMode.HTML)
        await asyncio.sleep(1.5)
        await q.edit_message_text(menu_text(), reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)

    # ── Language ──────────────────────────────────────────────────────────────
    elif data == "adm:lang":
        await q.edit_message_text("Выберите язык ответов:", reply_markup=lang_kb())

    elif data.startswith("adm:setlang:"):
        lang = data[len("adm:setlang:"):]
        cfg["language"] = lang
        save_config(cfg)
        label = "Русский 🇷🇺" if lang == "ru" else "English 🇬🇧"
        await q.edit_message_text(f"✅ Язык: <b>{label}</b>", parse_mode=ParseMode.HTML)
        await asyncio.sleep(1.5)
        await q.edit_message_text(menu_text(), reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)

    # ── Status ────────────────────────────────────────────────────────────────
    elif data == "adm:status":
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
        if not has_upd:
            await q.edit_message_text(f"✅ {msg}", reply_markup=back_kb())
        else:
            await q.edit_message_text(f"⏳ {msg}\n\nУстанавливаю...")
            ok, err = _do_update()
            if ok:
                await q.edit_message_text("✅ Обновлено! Перезапускаюсь через 3 секунды...")
                await asyncio.sleep(3)
                subprocess.Popen(["systemctl", "restart", "arxiv-bot"])
            else:
                await q.edit_message_text(
                    f"❌ Ошибка установки: <code>{err}</code>",
                    reply_markup=back_kb(),
                    parse_mode=ParseMode.HTML,
                )

    # ── Restart ───────────────────────────────────────────────────────────────
    elif data == "adm:restart":
        await q.edit_message_text(
            "♻️ Перезапустить бота?",
            reply_markup=_kb([[("✅ Да", "adm:do_restart"), ("❌ Отмена", "adm:menu")]]),
        )

    elif data == "adm:do_restart":
        await q.edit_message_text("♻️ Перезапускаюсь...")
        await asyncio.sleep(2)
        subprocess.Popen(["systemctl", "restart", "arxiv-bot"])


# ── Text handler (called from handlers.py) ────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle text input during multi-step flows. Returns True if consumed."""
    if not is_admin(update):
        return False

    awaiting = context.user_data.get("awaiting")
    if not awaiting:
        return False

    api_key = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass

    uid = _uid(update)

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
        pkey = context.user_data.get("temp_provider") or load_config().get("llm_provider", "")
        context.user_data["temp_key"] = api_key
        context.user_data.pop("awaiting", None)
        pname = PROVIDERS.get(pkey, {}).get("name", pkey)
        status = await update.message.reply_text(f"⏳ Загружаю модели {pname}...")
        try:
            models = await _fetch_models(pkey, PROVIDERS[pkey].get("base_url"), api_key)
            _save_models(uid, models, context)
            cfg = load_config()
            free_n = sum(1 for m in models if m["free"])
            await status.edit_text(
                f"Загружено {len(models)} моделей  (✅ {free_n} бесплатных)\n\nВыберите модель:",
                reply_markup=model_kb(models, 0, cfg.get("llm_model", "")),
            )
        except Exception as e:
            context.user_data.clear()
            await status.edit_text(
                f"❌ Не удалось загрузить модели: <code>{e}</code>\n\nПроверьте ключ.",
                reply_markup=back_kb("adm:provider"),
                parse_mode=ParseMode.HTML,
            )
        return True

    return False


# ── System helpers ────────────────────────────────────────────────────────────

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
        local = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=WORKDIR, capture_output=True, text=True
        ).stdout.strip()
        remote = subprocess.run(
            ["git", "rev-parse", "origin/main"], cwd=WORKDIR, capture_output=True, text=True
        ).stdout.strip()
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
