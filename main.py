import telebot
from keep_alive import keep_alive

# التوكن الخاص بك مدمج وجاهز
BOT_TOKEN = "8791289428:AAHtyh40fINcgHL7bhsYmOoXqUrdM9a7kNQ"
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "أهلاً بك! البوت الخاص بك يعمل الآن بنجاح وبشكل مستمر 24 ساعة.")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f"لقد أرسلت: {message.text}")

if __name__ == "__main__":
    # تشغيل سيرفر الويب لمنع النوم
    keep_alive()
    print("🚀 Web server started! Starting Telegram Bot...")
    
    # تشغيل البوت مع ميزة إعادة الاتصال التلقائي
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
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
    # قراءة التوكن بأمان من إعدادات سيرفر Pella
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set.")

    app = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )

    # 1. أوامر البوت (Commands)
    app.add_handler(CommandHandler("start", start))

    # 2. أزرار التحكم والقوائم (Callback query handlers)
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
    
    # قسم كل السجلات (All Records)
    app.add_handler(CallbackQueryHandler(all_records_callback,             pattern="^all_records$"))
    app.add_handler(CallbackQueryHandler(all_records_page_callback,        pattern=r"^all_records_page:\d+$"))
    app.add_handler(CallbackQueryHandler(del_any_record_callback,          pattern=r"^del_any_record:\d+$"))
    app.add_handler(CallbackQueryHandler(pick_group_for_record_callback,   pattern=r"^pick_group_for_record:\d+$"))
    app.add_handler(CallbackQueryHandler(assign_record_to_group_callback,  pattern=r"^assign_record_to_group:\d+:\d+$"))
    app.add_handler(CallbackQueryHandler(send_single_record_callback,      pattern=r"^send_record:\d+$"))
    
    # الحسابات والمجموعات (Calc → group)
    app.add_handler(CallbackQueryHandler(add_to_group_from_calc_callback,  pattern="^add_to_group_from_calc$"))
    app.add_handler(CallbackQueryHandler(save_calc_to_group_callback,      pattern=r"^save_calc_to_group:\d+$"))
    app.add_handler(CallbackQueryHandler(cancel_add_to_group_callback,     pattern="^cancel_add_to_group$"))

    # 3. معالجة الرسائل والريكوردات (Message handlers)
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # تشغيل سيرفر الويب المصغر لمنع النوم (keep_alive)
    keep_alive()
    
    # تشغيل البوت بنظام الـ Polling المستقر والمتوافق تماماً مع Pella
    logger.info("Bot is starting — polling for updates on Pella...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
