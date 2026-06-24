import logging

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from .admin import cmd_admin, handle_callback
from .config import load_config
from .handlers import cmd_help, cmd_start, handle_message

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def _on_startup(app: Application) -> None:
    cfg = load_config()
    admin_id = cfg.get("admin_user_id")
    if admin_id:
        try:
            await app.bot.send_message(
                chat_id=admin_id,
                text="✅ Бот запущен и готов к работе.",
            )
        except Exception as e:
            logger.warning("Could not send startup message: %s", e)


def main() -> None:
    cfg = load_config()
    token = cfg["telegram_token"]

    app = Application.builder().token(token).post_init(_on_startup).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=r"^adm:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot started, polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
