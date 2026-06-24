import logging

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from .config import load_config
from .handlers import cmd_help, cmd_start, cmd_status, handle_message

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    cfg = load_config()
    token = cfg["telegram_token"]

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot started, polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
