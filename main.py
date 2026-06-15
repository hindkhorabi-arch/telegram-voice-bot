"""
Main entry point for the Telegram Audio Duration Bot.
All-in-one script containing database logic, handers, keep-alive, and core logic.
"""

import logging
import os
import sqlite3
import re
from datetime import datetime
from flask import Flask
from threading import Thread

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# 1. إعدادات الـ Logs (التقارير)
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# إيقاف رسائل سيرفر Flask المزعجة
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

DB_FILE = "bot_database.db"

# ==========================================
# 2. كود الـ Keep Alive (منع النوم) المدمج
# ==========================================
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "🟢 Bot is alive and running 24/7 on Pella!", 200

def run_server():
    app_flask.run(host='0.0.0.0', port=8080)

def keep_alive():
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()

# ==========================================
# 3. إعدادات وقاعدة البيانات (Database)
# ==========================================
async def init_db() -> None:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # جدول المجموعات
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            created_at TEXT
        )
    """)
    # جدول السجلات (الريكوردات)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            group_id INTEGER,
            duration_secs INTEGER,
            file_unique_id TEXT,
            created_at TEXT,
            FOREIGN KEY(group_id) REFERENCES groups(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Database initialised successfully.")

# ==========================================
# 4. دوال التحكم والـ Handlers الأساسية
# ==========================================

def get_main_keyboard():
    keyboard = [["🎵 Calculate Duration"], ["📁 Create Group", "📚 My Groups"], ["📊 All Records"]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # تهيئة حالات المستخدم المخصصة
    context.user_data["state"] = None
    context.user_data["current_calc_duration"] = None
    
    welcome_text = "أهلاً بكِ في بوت حساب مدد الملفات الصوتية والريكوردات وتنسيقها في مجموعات! 🎧🚀"
    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    user_id = update.message.from_user.id
    current_state = context.user_data.get("state")

    # التعامل مع أزرار الكيبورد السفلي الرئيسية
    if user_text == "🎵 Calculate Duration":
        context.user_data["state"] = "waiting_for_audio_calc"
        await update.message.reply_text("من فضلكِ أرسلي الريكورد أو الملف الصوتي لحساب مدته.")
        return
    elif user_text == "📁 Create Group":
        context.user_data["state"] = "waiting_for_group_name"
        await update.message.reply_text("من فضلكِ أرسلي اسم المجموعة الجديدة المراد إنشاؤها:")
        return
    elif user_text == "📚 My Groups":
        await show_groups_page(update, user_id, page=1, is_callback=False)
        return
    elif user_text == "📊 All Records":
        await show_all_records(update, user_id, page=1, is_callback=False)
        return

    # التعامل مع حالات إدخال النص (Conversation States)
    if current_state == "waiting_for_group_name":
        group_name = user_text.strip()
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO groups (user_id, name, created_at) VALUES (?, ?, ?)", 
                       (user_id, group_name, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        context.user_data["state"] = None
        await update.message.reply_text(f"✅ تم إنشاء المجموعة بنجاح باسم: **{group_name}**", parse_mode="Markdown")
        
    elif current_state == "waiting_for_rename_group":
        group_id = context.user_data.get("target_group_id")
        new_name = user_text.strip()
        if group_id:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("UPDATE groups SET name = ? WHERE id = ? AND user_id = ?", (new_name, group_id, user_id))
            conn.commit()
            conn.close()
            context.user_data["state"] = None
            await update.message.reply_text(f"✅ تم تعديل اسم المجموعة إلى: **{new_name}**", parse_mode="Markdown")
        else:
            context.user_data["state"] = None
            await update.message.reply_text("❌ حدث خطأ، يرجى المحاولة مرة أخرى.")

# ==========================================
# 5. معالجة الملفات الصوتية والريكوردات
# ==========================================
async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    current_state = context.user_data.get("state")
    
    # جلب ملف الصوت أو الريكورد
    audio_obj = update.message.voice or update.message.audio
    if not audio_obj:
        return

    duration = audio_obj.duration
    mins = duration // 60
    secs = duration % 60
    duration_str = f"{mins:02d}:{secs:02d}"

    # إذا كان المستخدم في حالة حساب المدة فقط
    if current_state == "waiting_for_audio_calc":
        context.user_data["current_calc_duration"] = duration
        context.user_data["state"] = None
        
        keyboard = [
            [InlineKeyboardButton("➕ إضافة لمجموعة", callback_data="add_to_group_from_calc")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_add_to_group")]
        ]
        await update.message.reply_text(
            f"⏱ مدة هذا الملف هي: `{duration_str}`\n\nهل تودين حفظ هذا السجل في إحدى مجموعاتكِ؟",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        # الحفظ التلقائي أو الحر (خارج وضع الحساب)
        context.user_data["current_calc_duration"] = duration
        keyboard = [
            [InlineKeyboardButton("📁 اختر مجموعة لحفظ الريكورد", callback_data="add_to_group_from_calc")]
        ]
        await update.message.reply_text(
            f"⚙️ تم استقبال الريكورد بنجاح، مدته: `{duration_str}`.\nيمكنكِ حفظه بالضغط أدناه:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

# ==========================================
# 6. التصفح والتحكم بالمجموعات والسجلات (Pagination & Callbacks)
# ==========================================
async def show_groups_page(update, user_id, page=1, is_callback=True):
    limit = 5
    offset = (page - 1) * limit
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM groups WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?", (user_id, limit, offset))
    rows = cursor.execute("SELECT id, name FROM groups WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?", (user_id, limit, offset)).fetchall()
    total = cursor.execute("SELECT COUNT(*) FROM groups WHERE user_id = ?", (user_id,)).fetchone()[0]
    conn.close()

    if not rows and page == 1:
        text = "📁 ليس لديكِ أي مجموعات حالياً. اضغطي على 'Create Group' لإنشاء أول مجموعة."
        if is_callback:
            await update.callback_query.message.reply_text(text)
        else:
            await update.message.reply_text(text)
        return

    text = f"📚 **قائمة مجموعاتكِ (صفحة {page}/{(total + limit - 1) // limit}):**"
    keyboard = []
    for r_id, r_name in rows:
        keyboard.append([InlineKeyboardButton(f"📁 {r_name}", callback_data=f"group_detail:{r_id}")])

    # أزرار التنقل بين الصفحات
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"groups_page:{page-1}"))
    if offset + limit < total:
        nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"groups_page:{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)
    if is_callback:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_all_records(update, user_id, page=1, is_callback=True):
    limit = 10
    offset = (page - 1) * limit
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    rows = cursor.execute("""
        SELECT r.id, r.duration_secs, g.name 
        FROM records r 
        LEFT JOIN groups g ON r.group_id = g.id 
        WHERE r.user_id = ? ORDER BY r.id DESC LIMIT ? OFFSET ?
    """, (user_id, limit, offset)).fetchall()
    total = cursor.execute("SELECT COUNT(*) FROM records r WHERE r.user_id = ?", (user_id,)).fetchone()[0]
    conn.close()

    if not rows:
        text = "📊 لا توجد أي سجلات صوتية محفوظة حالياً."
        if is_callback:
            await update.callback_query.message.reply_text(text)
        else:
            await update.message.reply_text(text)
        return

    text = f"📊 **كل السجلات الصوتية المحفوظة (صفحة {page}):**\n\n"
    keyboard = []
    for r_id, secs, g_name in rows:
        m = secs // 60
        s = secs % 60
        g_label = g_name if g_name else "بدون مجموعة"
        text += f"🔹 سجل رقم {r_id} | المدة: {m:02d}:{s:02d} | [{g_label}]\n"
        keyboard.append([InlineKeyboardButton(f"🗑 حذف سجل {r_id}", callback_data=f"del_any_record:{r_id}")])

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"all_records_page:{page-1}"))
    if offset + limit < total:
        nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"all_records_page:{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)
    if is_callback:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# ==========================================
# 7. معالجة ضغطات الأزرار (Callback Query Handler)
# ==========================================
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "cancel_add_to_group":
        context.user_data["current_calc_duration"] = None
        await query.edit_text("❌ تم إلغاء العملية وحذف الحساب المؤقت.")
        return

    elif data == "add_to_group_from_calc":
        # عرض المجموعات ليختار منها لحفظ الريكورد المحسوب
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        groups = cursor.execute("SELECT id, name FROM groups WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
        conn.close()
        
        if not groups:
            await query.edit_text("❌ ليس لديكِ أي مجموعات لحفظ الريكورد بها حالياً، يرجى إنشاء مجموعة أولاً.")
            return
            
        text = "📁 اختاري المجموعة التي تودين حفظ الريكورد داخلها:"
        keyboard = []
        for g_id, g_name in groups:
            keyboard.append([InlineKeyboardButton(g_name, callback_data=f"save_calc_to_group:{g_id}")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel_add_to_group")])
        await query.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("save_calc_to_group:"):
        group_id = int(data.split(":")[1])
        duration = context.user_data.get("current_calc_duration")
        if duration:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO records (user_id, group_id, duration_secs, created_at) VALUES (?, ?, ?, ?)",
                           (user_id, group_id, duration, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            context.user_data["current_calc_duration"] = None
            await query.edit_text("✅ تم حفظ الريكورد بنجاح داخل المجموعة المحددة!")
        else:
            await query.edit_text("❌ انتهت صلاحية بيانات الحساب، يرجى إرسال الريكورد من جديد.")

    elif data.startswith("groups_page:"):
        page = int(data.split(":")[1])
        await show_groups_page(update, user_id, page=page, is_callback=True)

    elif data.startswith("all_records_page:"):
        page = int(data.split(":")[1])
        await show_all_records(update, user_id, page=page, is_callback=True)

    elif data.startswith("del_any_record:"):
        rec_id = int(data.split(":")[1])
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM records WHERE id = ? AND user_id = ?", (rec_id, user_id))
        conn.commit()
        conn.close()
        await query.edit_text(f"🗑 تم حذف السجل رقم {rec_id} بنجاح.")

    elif data.startswith("group_detail:"):
        group_id = int(data.split(":")[1])
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        g_name = cursor.execute("SELECT name FROM groups WHERE id = ? AND user_id = ?", (group_id, user_id)).fetchone()
        records = cursor.execute("SELECT id, duration_secs FROM records WHERE group_id = ? AND user_id = ?", (group_id, user_id)).fetchall()
        conn.close()

        if not g_name:
            await query.edit_text("❌ لم يتم العثور على المجموعة.")
            return

        g_name = g_name[0]
        total_secs = sum(r[1] for r in records)
        t_min = total_secs // 60
        t_sec = total_secs % 60

        text = f"📁 **المجموعة: {g_name}**\n"
        text += f"📊 عدد السجلات: `{len(records)}` ملف\n"
        text += f"⏱ إجمالي مدة المجموعة: `{t_min:02d}:{t_sec:02d}`\n\n"
        text += "📝 **السجلات الفرعية:**\n"
        
        for idx, (r_id, r_secs) in enumerate(records, start=1):
            text += f"   {idx}. سجل {r_id} ⬅️ مدته ({r_secs // 60:02d}:{r_secs % 60:02d})\n"

        keyboard = [
            [InlineKeyboardButton("✏️ تعديل اسم المجموعة", callback_data=f"rename_group:{group_id}")],
"""
Main entry point for the Telegram Audio Duration Bot.
All-in-one script containing database logic, handers, keep-alive, and core logic.
"""

import logging
import os
import sqlite3
import re
from datetime import datetime
from flask import Flask
from threading import Thread

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# 1. إعدادات الـ Logs (التقارير)
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# إيقاف رسائل سيرفر Flask المزعجة
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

DB_FILE = "bot_database.db"

# ==========================================
# 2. كود الـ Keep Alive (منع النوم) المدمج
# ==========================================
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "🟢 Bot is alive and running 24/7 on Pella!", 200

def run_server():
    app_flask.run(host='0.0.0.0', port=8080)

def keep_alive():
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()

# ==========================================
# 3. إعدادات وقاعدة البيانات (Database)
# ==========================================
async def init_db() -> None:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # جدول المجموعات
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            created_at TEXT
        )
    """)
    # جدول السجلات (الريكوردات)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            group_id INTEGER,
            duration_secs INTEGER,
            file_unique_id TEXT,
            created_at TEXT,
            FOREIGN KEY(group_id) REFERENCES groups(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Database initialised successfully.")

# ==========================================
# 4. دوال التحكم والـ Handlers الأساسية
# ==========================================

def get_main_keyboard():
    keyboard = [["🎵 Calculate Duration"], ["📁 Create Group", "📚 My Groups"], ["📊 All Records"]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # تهيئة حالات المستخدم المخصصة
    context.user_data["state"] = None
    context.user_data["current_calc_duration"] = None
    
    welcome_text = "أهلاً بكِ في بوت حساب مدد الملفات الصوتية والريكوردات وتنسيقها في مجموعات! 🎧🚀"
    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    user_id = update.message.from_user.id
    current_state = context.user_data.get("state")

    # التعامل مع أزرار الكيبورد السفلي الرئيسية
    if user_text == "🎵 Calculate Duration":
        context.user_data["state"] = "waiting_for_audio_calc"
        await update.message.reply_text("من فضلكِ أرسلي الريكورد أو الملف الصوتي لحساب مدته.")
        return
    elif user_text == "📁 Create Group":
        context.user_data["state"] = "waiting_for_group_name"
        await update.message.reply_text("من فضلكِ أرسلي اسم المجموعة الجديدة المراد إنشاؤها:")
        return
    elif user_text == "📚 My Groups":
        await show_groups_page(update, user_id, page=1, is_callback=False)
        return
    elif user_text == "📊 All Records":
        await show_all_records(update, user_id, page=1, is_callback=False)
        return

    # التعامل مع حالات إدخال النص (Conversation States)
    if current_state == "waiting_for_group_name":
        group_name = user_text.strip()
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO groups (user_id, name, created_at) VALUES (?, ?, ?)", 
                       (user_id, group_name, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        context.user_data["state"] = None
        await update.message.reply_text(f"✅ تم إنشاء المجموعة بنجاح باسم: **{group_name}**", parse_mode="Markdown")
        
    elif current_state == "waiting_for_rename_group":
        group_id = context.user_data.get("target_group_id")
        new_name = user_text.strip()
        if group_id:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("UPDATE groups SET name = ? WHERE id = ? AND user_id = ?", (new_name, group_id, user_id))
            conn.commit()
            conn.close()
            context.user_data["state"] = None
            await update.message.reply_text(f"✅ تم تعديل اسم المجموعة إلى: **{new_name}**", parse_mode="Markdown")
        else:
            context.user_data["state"] = None
            await update.message.reply_text("❌ حدث خطأ، يرجى المحاولة مرة أخرى.")

# ==========================================
# 5. معالجة الملفات الصوتية والريكوردات
# ==========================================
async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    current_state = context.user_data.get("state")
    
    # جلب ملف الصوت أو الريكورد
    audio_obj = update.message.voice or update.message.audio
    if not audio_obj:
        return

    duration = audio_obj.duration
    mins = duration // 60
    secs = duration % 60
    duration_str = f"{mins:02d}:{secs:02d}"

    # إذا كان المستخدم في حالة حساب المدة فقط
    if current_state == "waiting_for_audio_calc":
        context.user_data["current_calc_duration"] = duration
        context.user_data["state"] = None
        
        keyboard = [
            [InlineKeyboardButton("➕ إضافة لمجموعة", callback_data="add_to_group_from_calc")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_add_to_group")]
        ]
        await update.message.reply_text(
            f"⏱ مدة هذا الملف هي: `{duration_str}`\n\nهل تودين حفظ هذا السجل في إحدى مجموعاتكِ؟",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        # الحفظ التلقائي أو الحر (خارج وضع الحساب)
        context.user_data["current_calc_duration"] = duration
        keyboard = [
            [InlineKeyboardButton("📁 اختر مجموعة لحفظ الريكورد", callback_data="add_to_group_from_calc")]
        ]
        await update.message.reply_text(
            f"⚙️ تم استقبال الريكورد بنجاح، مدته: `{duration_str}`.\nيمكنكِ حفظه بالضغط أدناه:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

# ==========================================
# 6. التصفح والتحكم بالمجموعات والسجلات (Pagination & Callbacks)
# ==========================================
async def show_groups_page(update, user_id, page=1, is_callback=True):
    limit = 5
    offset = (page - 1) * limit
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM groups WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?", (user_id, limit, offset))
    rows = cursor.execute("SELECT id, name FROM groups WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?", (user_id, limit, offset)).fetchall()
    total = cursor.execute("SELECT COUNT(*) FROM groups WHERE user_id = ?", (user_id,)).fetchone()[0]
    conn.close()

    if not rows and page == 1:
        text = "📁 ليس لديكِ أي مجموعات حالياً. اضغطي على 'Create Group' لإنشاء أول مجموعة."
        if is_callback:
            await update.callback_query.message.reply_text(text)
        else:
            await update.message.reply_text(text)
        return

    text = f"📚 **قائمة مجموعاتكِ (صفحة {page}/{(total + limit - 1) // limit}):**"
    keyboard = []
    for r_id, r_name in rows:
        keyboard.append([InlineKeyboardButton(f"📁 {r_name}", callback_data=f"group_detail:{r_id}")])

    # أزرار التنقل بين الصفحات
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"groups_page:{page-1}"))
    if offset + limit < total:
        nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"groups_page:{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)
    if is_callback:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_all_records(update, user_id, page=1, is_callback=True):
    limit = 10
    offset = (page - 1) * limit
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    rows = cursor.execute("""
        SELECT r.id, r.duration_secs, g.name 
        FROM records r 
        LEFT JOIN groups g ON r.group_id = g.id 
        WHERE r.user_id = ? ORDER BY r.id DESC LIMIT ? OFFSET ?
    """, (user_id, limit, offset)).fetchall()
    total = cursor.execute("SELECT COUNT(*) FROM records r WHERE r.user_id = ?", (user_id,)).fetchone()[0]
    conn.close()

    if not rows:
        text = "📊 لا توجد أي سجلات صوتية محفوظة حالياً."
        if is_callback:
            await update.callback_query.message.reply_text(text)
        else:
            await update.message.reply_text(text)
        return

    text = f"📊 **كل السجلات الصوتية المحفوظة (صفحة {page}):**\n\n"
    keyboard = []
    for r_id, secs, g_name in rows:
        m = secs // 60
        s = secs % 60
        g_label = g_name if g_name else "بدون مجموعة"
        text += f"🔹 سجل رقم {r_id} | المدة: {m:02d}:{s:02d} | [{g_label}]\n"
        keyboard.append([InlineKeyboardButton(f"🗑 حذف سجل {r_id}", callback_data=f"del_any_record:{r_id}")])

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"all_records_page:{page-1}"))
    if offset + limit < total:
        nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"all_records_page:{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)
    if is_callback:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# ==========================================
# 7. معالجة ضغطات الأزرار (Callback Query Handler)
# ==========================================
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "cancel_add_to_group":
        context.user_data["current_calc_duration"] = None
        await query.edit_text("❌ تم إلغاء العملية وحذف الحساب المؤقت.")
        return

    elif data == "add_to_group_from_calc":
        # عرض المجموعات ليختار منها لحفظ الريكورد المحسوب
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        groups = cursor.execute("SELECT id, name FROM groups WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
        conn.close()
        
        if not groups:
            await query.edit_text("❌ ليس لديكِ أي مجموعات لحفظ الريكورد بها حالياً، يرجى إنشاء مجموعة أولاً.")
            return
            
        text = "📁 اختاري المجموعة التي تودين حفظ الريكورد داخلها:"
        keyboard = []
        for g_id, g_name in groups:
            keyboard.append([InlineKeyboardButton(g_name, callback_data=f"save_calc_to_group:{g_id}")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel_add_to_group")])
        await query.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("save_calc_to_group:"):
        group_id = int(data.split(":")[1])
        duration = context.user_data.get("current_calc_duration")
        if duration:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO records (user_id, group_id, duration_secs, created_at) VALUES (?, ?, ?, ?)",
                           (user_id, group_id, duration, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            context.user_data["current_calc_duration"] = None
            await query.edit_text("✅ تم حفظ الريكورد بنجاح داخل المجموعة المحددة!")
        else:
            await query.edit_text("❌ انتهت صلاحية بيانات الحساب، يرجى إرسال الريكورد من جديد.")

    elif data.startswith("groups_page:"):
        page = int(data.split(":")[1])
        await show_groups_page(update, user_id, page=page, is_callback=True)

    elif data.startswith("all_records_page:"):
        page = int(data.split(":")[1])
        await show_all_records(update, user_id, page=page, is_callback=True)

    elif data.startswith("del_any_record:"):
        rec_id = int(data.split(":")[1])
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM records WHERE id = ? AND user_id = ?", (rec_id, user_id))
        conn.commit()
        conn.close()
        await query.edit_text(f"🗑 تم حذف السجل رقم {rec_id} بنجاح.")

    elif data.startswith("group_detail:"):
        group_id = int(data.split(":")[1])
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        g_name = cursor.execute("SELECT name FROM groups WHERE id = ? AND user_id = ?", (group_id, user_id)).fetchone()
        records = cursor.execute("SELECT id, duration_secs FROM records WHERE group_id = ? AND user_id = ?", (group_id, user_id)).fetchall()
        conn.close()

        if not g_name:
            await query.edit_text("❌ لم يتم العثور على المجموعة.")
            return

        g_name = g_name[0]
        total_secs = sum(r[1] for r in records)
        t_min = total_secs // 60
        t_sec = total_secs % 60

        text = f"📁 **المجموعة: {g_name}**\n"
        text += f"📊 عدد السجلات: `{len(records)}` ملف\n"
        text += f"⏱ إجمالي مدة المجموعة: `{t_min:02d}:{t_sec:02d}`\n\n"
        text += "📝 **السجلات الفرعية:**\n"
        
        for idx, (r_id, r_secs) in enumerate(records, start=1):
            text += f"   {idx}. سجل {r_id} ⬅️ مدته ({r_secs // 60:02d}:{r_secs % 60:02d})\n"

        keyboard = [
            [InlineKeyboardButton("✏️ تعديل اسم المجموعة", callback_data=f"rename_group:{group_id}")],
