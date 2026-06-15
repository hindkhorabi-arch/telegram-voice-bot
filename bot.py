"""
Main entry point for the Telegram Audio Duration Bot.
Registers all handlers and starts polling (dev) or webhook (production).
"""

import logging
import os

from keep_alive import keep_alive
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from database import init_db
from handlers.start import start, main_menu_callback
from handlers.audio import handle_audio
from handlers.groups import (
    # Calculate / menu
    calc_duration_callback,
    create_group_callback,
    my_groups_callback,
    groups_page_callback,
    # Group CRUD
    group_detail_callback,
    group_finish_callback,
    group_cancel_callback,
    view_records_callback,
    delete_record_callback,
    rename_group_callback,
    delete_group_callback,
    confirm_delete_group_callback,
    # All Records view
    all_records_callback,
    all_records_page_callback,
    del_any_record_callback,
    pick_group_for_record_callback,
    assign_record_to_group_callback,
    send_single_record_callback,
    # Calc → group
    add_to_group_from_calc_callback,
    save_calc_to_group_callback,
    cancel_add_to_group_callback,
    # Text (ReplyKeyboard + conversation states)
    handle_text,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application) -> None:
    await init_db()
    logger.info("Database initialised.")


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set.")

    app = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", start))

    # Callback query handlers (more specific patterns first)
    app.add_handler(CallbackQueryHandler(main_menu_callback,               pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(calc_duration_callback,           pattern="^calc_duration$"))
    app.add_handler(CallbackQueryHandler(create_group_callback,            pattern="^create_group$"))
    app.add_handler(CallbackQueryHandler(my_groups_callback,               pattern="^my_groups$"))
    app.add_handler(CallbackQueryHandler(groups_page_callback,             pattern=r"^groups_page:\d+$"))
    app.add_handler(CallbackQueryHandler(group_detail_callback,            pattern=r"^group_detail:\d+$"))
    app.add_handler(CallbackQueryHandler(group_finish_callback,            pattern="^group_finish$"))
    app.add_handler(CallbackQueryHandler(group_cancel_callback,            pattern="^group_cancel$"))
    app.add_handler(CallbackQueryHandler(view_records_callback,            pattern=r"^view_records:\d+$"))
    app.add_handler(CallbackQueryHandler(delete_record_callback,           pattern=r"^delete_record:\d+:\d+$"))
    app.add_handler(CallbackQueryHandler(rename_group_callback,            pattern=r"^rename_group:\d+$"))
    app.add_handler(CallbackQueryHandler(delete_group_callback,            pattern=r"^delete_group:\d+$"))
    app.add_handler(CallbackQueryHandler(confirm_delete_group_callback,    pattern=r"^confirm_delete_group:\d+$"))
    # All Records
    app.add_handler(CallbackQueryHandler(all_records_callback,             pattern="^all_records$"))
    app.add_handler(CallbackQueryHandler(all_records_page_callback,        pattern=r"^all_records_page:\d+$"))
    app.add_handler(CallbackQueryHandler(del_any_record_callback,          pattern=r"^del_any_record:\d+$"))
    app.add_handler(CallbackQueryHandler(pick_group_for_record_callback,   pattern=r"^pick_group_for_record:\d+$"))
    app.add_handler(CallbackQueryHandler(assign_record_to_group_callback,  pattern=r"^assign_record_to_group:\d+:\d+$"))
    app.add_handler(CallbackQueryHandler(send_single_record_callback,      pattern=r"^send_record:\d+$"))
    # Calc → group
    app.add_handler(CallbackQueryHandler(add_to_group_from_calc_callback,  pattern="^add_to_group_from_calc$"))
    app.add_handler(CallbackQueryHandler(save_calc_to_group_callback,      pattern=r"^save_calc_to_group:\d+$"))
    app.add_handler(CallbackQueryHandler(cancel_add_to_group_callback,     pattern="^cancel_add_to_group$"))

    # Message handlers
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    is_production = os.environ.get("NODE_ENV") == "production"
    domain = os.environ.get("REPLIT_DOMAINS", "").split(",")[0].strip()

    if is_production and domain:
        webhook_url = f"https://{domain}/bot/webhook"
        logger.info(f"Starting in webhook mode: {webhook_url}")
        app.run_webhook(
            listen="0.0.0.0",
            port=5000,
            url_path="/bot/webhook",
            webhook_url=webhook_url,
            allowed_updates=["message", "callback_query"],
        )
    else:
        keep_alive()
        logger.info("Bot is starting — polling for updates...")
        app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()

