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
