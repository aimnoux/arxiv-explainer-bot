import re

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from . import admin as admin_module
from .arxiv_client import extract_arxiv_id, fetch_paper_text
from .config import PROVIDERS, load_config, save_config
from .formatter import escape_md, format_analysis, split_message
from .llm_client import get_llm_client

ARXIV_URL_RE = re.compile(r"arxiv\.org/(abs|pdf)/[\d.]+v?\d*")
ARXIV_ID_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")

WELCOME_USER = (
    "👋 Привет\\! Я анализирую научные статьи с *arxiv\\.org*\\.\n\n"
    "Просто пришли мне ссылку:\n"
    "`https://arxiv.org/abs/2406.12345`\n\n"
    "Или просто ID статьи:\n"
    "`2406.12345`"
)

WELCOME_ADMIN = (
    "👋 Привет\\! Я анализирую научные статьи с *arxiv\\.org*\\.\n\n"
    "Пришли ссылку — получишь разбор статьи\\.\n\n"
    "Для настройки бота: /admin"
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = _safe_load_config()

    # Bootstrap: if no admin set yet, first /start becomes admin
    if not cfg.get("admin_user_id"):
        user = update.effective_user
        cfg["admin_user_id"] = user.id
        save_config(cfg)
        await update.message.reply_text(
            f"👑 Вы установлены как администратор бота\\.\n"
            f"Ваш Telegram ID: `{user.id}`\n\n"
            "Для настройки: /admin",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    if admin_module.is_admin(update):
        await update.message.reply_text(WELCOME_ADMIN, parse_mode=ParseMode.MARKDOWN_V2)
    else:
        await update.message.reply_text(WELCOME_USER, parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if admin_module.is_admin(update):
        await update.message.reply_text(WELCOME_ADMIN, parse_mode=ParseMode.MARKDOWN_V2)
    else:
        await update.message.reply_text(WELCOME_USER, parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        cfg = load_config()
    except FileNotFoundError:
        await update.message.reply_text(
            "❌ Конфиг не найден\\. Запустите `python3 -m bot.wizard`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    provider_key = cfg.get("llm_provider", "?")
    provider_name = PROVIDERS.get(provider_key, {}).get("name", provider_key)
    model = cfg.get("llm_model", "?")
    lang = cfg.get("language", "ru")

    text = (
        f"⚙️ *Текущий конфиг*\n\n"
        f"Провайдер: `{escape_md(provider_name)}`\n"
        f"Модель: `{escape_md(model)}`\n"
        f"Язык: `{escape_md(lang)}`"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Admin multi-step flow takes priority
    if await admin_module.handle_text(update, context):
        return

    text = (update.message.text or "").strip()

    if not (ARXIV_URL_RE.search(text) or ARXIV_ID_RE.match(text)):
        return

    arxiv_id = extract_arxiv_id(text)
    if not arxiv_id:
        await update.message.reply_text(
            "❌ Не могу распознать ссылку\\. Пример: `https://arxiv.org/abs/2406.12345`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    status_msg = await update.message.reply_text("⏳ Скачиваю статью\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)

    try:
        cfg = load_config()
    except FileNotFoundError:
        await status_msg.edit_text(
            "❌ Конфиг не найден\\. Запустите `python3 -m bot.wizard`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    try:
        paper = await fetch_paper_text(arxiv_id, max_pages=cfg.get("max_paper_pages", 20))
    except Exception as e:
        await status_msg.edit_text(
            f"❌ Не удалось скачать статью\\. Попробуй позже или проверь ссылку\\.\n\n`{escape_md(str(e))}`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    provider_key = cfg.get("llm_provider", "")
    provider_name = PROVIDERS.get(provider_key, {}).get("name", provider_key)
    model = cfg.get("llm_model", "")
    await status_msg.edit_text(
        f"🧠 Анализирую через `{escape_md(provider_name)}`/`{escape_md(model)}`\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    try:
        llm = get_llm_client(cfg)
        analysis = await llm.analyze(paper)
    except ValueError as e:
        await status_msg.edit_text(f"❌ {escape_md(str(e))}", parse_mode=ParseMode.MARKDOWN_V2)
        return
    except Exception as e:
        await status_msg.edit_text(
            f"❌ Ошибка LLM: `{escape_md(str(e))}`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    formatted = format_analysis(paper, analysis)
    parts = split_message(formatted)

    await status_msg.delete()
    for part in parts:
        await update.message.reply_text(part, parse_mode=ParseMode.MARKDOWN_V2)


def _safe_load_config() -> dict:
    try:
        return load_config()
    except FileNotFoundError:
        return {}
