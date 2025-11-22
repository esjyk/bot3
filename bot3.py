import telebot
from telebot import types
import re
import logging
import requests
from datetime import datetime
from flask import Flask, request
import os

# ======== SOZLAMALAR ========
BOT_TOKEN = "8416235735:AAEy_LrCi9de8Mt2yv0L5EeFSAhRNVF7fpI"
ADMIN_SECRET = "fox7003"
CHANNELS = [
    "@mediafoxtv_kanal"
]
STORAGE_CHANNEL = "@mediafoxtv_kanal"

# Supabase sozlamalari
SUPABASE_URL = "https://mekfclixsbywzbyofngg.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1la2ZjbGl4c2J5d3pieW9mbmdnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjMzNTA1NTQsImV4cCI6MjA3ODkyNjU1NH0.4EZ2nUhgJJU7Th9stRUcPAJV1oXdYT1Hb9RU0U5zBOE"
SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Webhook sozlamalari
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')  # Render URL: https://your-app.onrender.com
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

# Xotirada sessiyalarni saqlash
user_sessions = {}

# ======== LOGGING ========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ======== BOT VA FLASK ========
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)


# ======== SUPABASE FUNKSIYALARI ========

def save_movie(code, message_id, description):
    """Kinoni Supabase bazasiga saqlash"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/movies"
        data = {
            "code": code,
            "message_id": message_id,
            "description": description
        }
        
        response = requests.post(url, json=data, headers=SUPABASE_HEADERS)
        
        if response.status_code in [200, 201]:
            logger.info(f"✅ Kino saqlandi: {code}")
            return True
        else:
            logger.error(f"Supabase saqlash xatosi: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Kino saqlashda xato: {e}")
        return False


def get_movie_by_code(code):
    """Kod bo'yicha kinoni topish"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/movies"
        params = {"code": f"eq.{code}", "select": "*"}
        
        response = requests.get(url, params=params, headers=SUPABASE_HEADERS)
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                return data[0]
        return None
    except Exception as e:
        logger.error(f"Kino qidirishda xato: {e}")
        return None


def update_movie(code, message_id=None, description=None):
    """Kinoni yangilash"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/movies"
        params = {"code": f"eq.{code}"}
        data = {}
        
        if message_id:
            data["message_id"] = message_id
        if description:
            data["description"] = description
            
        response = requests.patch(url, json=data, params=params, headers=SUPABASE_HEADERS)
        
        if response.status_code == 200:
            logger.info(f"✅ Kino yangilandi: {code}")
            return True
        return False
    except Exception as e:
        logger.error(f"Kino yangilashda xato: {e}")
        return False


def delete_movie(code):
    """Kinoni o'chirish"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/movies"
        params = {"code": f"eq.{code}"}
        
        response = requests.delete(url, params=params, headers=SUPABASE_HEADERS)
        
        if response.status_code == 200:
            logger.info(f"✅ Kino o'chirildi: {code}")
            return True
        return False
    except Exception as e:
        logger.error(f"Kino o'chirishda xato: {e}")
        return False


def get_all_movies(limit=100):
    """Barcha kinolarni olish"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/movies"
        params = {"select": "*", "limit": limit, "order": "created_at.desc"}
        
        response = requests.get(url, params=params, headers=SUPABASE_HEADERS)
        
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        logger.error(f"Kinolarni olishda xato: {e}")
        return []


def get_movies_count():
    """Kinolar sonini olish"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/movies"
        params = {"select": "count"}
        headers = {**SUPABASE_HEADERS, "Prefer": "count=exact"}
        
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            # Response headers dan count ni olish
            count = response.headers.get('Content-Range', '0-0/0').split('/')[-1]
            return int(count)
        return 0
    except Exception as e:
        logger.error(f"Hisoblashda xato: {e}")
        return 0


# ======== SESSIYA BILAN ISHLASH ========

def get_user_session(user_id):
    """Foydalanuvchi sessiyasini olish"""
    return user_sessions.get(user_id)


def update_user_session(user_id, is_admin=False, state=None, temp_data=None):
    """Foydalanuvchi sessiyasini yangilash"""
    user_sessions[user_id] = {
        "is_admin": is_admin,
        "state": state,
        "temp_data": temp_data,
        "updated_at": datetime.now().isoformat()
    }


def clear_user_session(user_id):
    """Foydalanuvchi sessiyasini tozalash"""
    if user_id in user_sessions:
        del user_sessions[user_id]


# ======== YORDAMCHI FUNKSIYALAR ========

def extract_code(text):
    if not text:
        return None
    m = re.search(r'\b(\d{3,4})\b', text)
    return m.group(1) if m else None


def check_subscription(user_id):
    """Foydalanuvchi barcha kanallarga obuna bo'lganligini tekshiradi"""
    for channel in CHANNELS:
        try:
            status = bot.get_chat_member(channel, user_id).status
            if status not in ['member', 'administrator', 'creator']:
                return False
        except Exception as e:
            logger.error(f"Obuna tekshirishda xato ({channel}): {e}")
            continue
    return True


def create_subscription_keyboard():
    """Obuna bo'lish tugmalarini yaratadi"""
    markup = types.InlineKeyboardMarkup()
    for i, channel in enumerate(CHANNELS, 1):
        channel_name = channel.replace("@", "")
        markup.add(types.InlineKeyboardButton(
            f"📢 Kanal {i}",
            url=f"https://t.me/{channel_name}"
        ))
    markup.add(types.InlineKeyboardButton(
        "✅ A'zolikni tekshirish",
        callback_data="check_subscription"
    ))
    return markup


def create_main_menu():
    """Asosiy menyu tugmalarini yaratadi"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔢 Kod bilan qidirish", "➕ Guruhga qo'shish")
    markup.row("ℹ️ Bizga qo'shiling")
    return markup


def create_admin_menu():
    """Admin menyu tugmalarini yaratadi"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📤 Kino yuklash", "🔢 Kod bilan qidirish")
    markup.row("❌ Admin rejimdan chiqish")
    return markup


def get_bot_invite_link():
    """Bot uchun guruhga qo'shish havolasini yaratish"""
    bot_username = bot.get_me().username
    return f"https://t.me/{bot_username}?startgroup=true"


# ======== HANDLERLAR ========

@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    chat_type = message.chat.type
    
    if chat_type in ['group', 'supergroup']:
        bot.send_message(
            message.chat.id,
            "✅ Bot guruhingizda faol!\n\n"
            "🎬 Kino kodini yuboring yoki /help buyrug'ini kiriting.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return
    
    if not check_subscription(user_id):
        bot.send_message(
            message.chat.id,
            "🔒 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
            "👇 Barcha kanallarga a'zo bo'lib, '✅ A'zolikni tekshirish' tugmasini bosing.",
            reply_markup=create_subscription_keyboard()
        )
        return
    
    clear_user_session(user_id)
    bot.send_message(
        message.chat.id,
        f"👋 Salom {message.from_user.first_name}!\n\n"
        "🎬 Xush kelibsiz! Quyidagi imkoniyatlardan foydalaning:",
        reply_markup=create_main_menu()
    )


@bot.message_handler(commands=["help"])
def help_command(message):
    chat_type = message.chat.type
    
    if chat_type in ['group', 'supergroup']:
        bot.send_message(
            message.chat.id,
            "📖 <b>Guruhda foydalanish:</b>\n\n"
            "🔢 Kino kodini yuboring\n (masalan: /1111)\n"
            "🎬 Bot avtomatik kinoni yuboradi\n\n"
            "💡 Shaxsiy chatda ko'proq imkoniyatlar mavjud!"
        )
    else:
        bot.send_message(
            message.chat.id,
            "📖 <b>Bot qo'llanma:</b>\n\n"
            "🔢 Kod bilan qidirish - 3-4 xonali kod kiriting\n"
            "➕ Guruhga qo'shish - Botni guruhingizga qo'shing\n"
            "ℹ️ Bizga qo'shiling - Bot haqida ma'lumot\n\n"
            "💡 Guruhda ham ishlatishingiz mumkin!",
            reply_markup=create_main_menu()
        )


@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_sub_callback(call):
    user_id = call.from_user.id
    
    try:
        if check_subscription(user_id):
            bot.edit_message_text(
                f"✅ A'zolik tasdiqlandi!\n\n"
                f"👋 Salom {call.from_user.first_name}!\n\n"
                "🎬 Xush kelibsiz! Quyidagi imkoniyatlardan foydalaning:",
                call.message.chat.id,
                call.message.message_id
            )
            bot.send_message(
                call.message.chat.id,
                "Tanlang:",
                reply_markup=create_main_menu()
            )
        else:
            try:
                bot.answer_callback_query(
                    call.id,
                    "❌ Siz hali barcha kanallarga obuna bo'lmadingiz!",
                    show_alert=True
                )
            except:
                pass
    except Exception as e:
        logger.error(f"Callback xatosi: {e}")


@bot.message_handler(content_types=["video"])
def handle_video(message):
    user_id = message.from_user.id
    chat_type = message.chat.type
    
    if chat_type in ['group', 'supergroup']:
        bot.send_message(
            message.chat.id,
            "ℹ️ Kino yuklash uchun botni shaxsiy chatda ishlatib, admin rejimga o'ting."
        )
        return
    
    if not check_subscription(user_id):
        bot.send_message(
            message.chat.id,
            "🔒 Botdan foydalanish uchun kanallarga obuna bo'ling!",
            reply_markup=create_subscription_keyboard()
        )
        return
    
    session = get_user_session(user_id)
    if not session or not session.get("is_admin"):
        bot.send_message(message.chat.id, "❌ Sizda admin ruxsati yo'q!")
        return

    update_user_session(user_id, True, "waiting_for_code", {"message_id": message.message_id})
    bot.send_message(message.chat.id, "🔢 Ushbu kino uchun 3 yoki 4 xonali kod yuboring.")


@bot.message_handler(func=lambda message: message.content_type == "text")
def handle_text(message):
    user_id = message.from_user.id
    chat_type = message.chat.type
    text = message.text.strip()

    # === GURUHDA ISHLASH ===
    if chat_type in ['group', 'supergroup']:
        code = extract_code(text)
        if code:
            movie = get_movie_by_code(code)
            if movie:
                try:
                    bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=STORAGE_CHANNEL,
                        message_id=movie["message_id"]
                    )
                except Exception as e:
                    logger.error(f"Guruhda kino yuborishda xato: {e}")
                    bot.send_message(message.chat.id, "⚠️ Kino yuborishda xatolik yuz berdi.")
            else:
                bot.send_message(message.chat.id, "❌ Bu kodga mos kino topilmadi.")
        return

    # === ADMIN REJIMGA O'TISH ===
    if text == ADMIN_SECRET:
        update_user_session(user_id, True, None, None)
        bot.send_message(
            message.chat.id,
            "🔐 Admin rejim yoqildi!\n\n"
            "📤 Kino yuklash uchun video yuboring yoki menyudan tanlang.",
            reply_markup=create_admin_menu()
        )
        return

    # === ADMIN REJIMDAN CHIQISH ===
    session = get_user_session(user_id)
    if text == "❌ Admin rejimdan chiqish" and session and session.get("is_admin"):
        clear_user_session(user_id)
        bot.send_message(
            message.chat.id,
            "👋 Admin rejimdan chiqdingiz!",
            reply_markup=create_main_menu()
        )
        return

    # === A'ZOLIK TEKSHIRUVI ===
    if not check_subscription(user_id) and (not session or not session.get("is_admin")):
        bot.send_message(
            message.chat.id,
            "🔒 Botdan foydalanish uchun kanallarga obuna bo'ling!",
            reply_markup=create_subscription_keyboard()
        )
        return

    # === MENYU TUGMALARI ===
    if text == "🔢 Kod bilan qidirish":
        update_user_session(user_id, session.get("is_admin", False) if session else False, "search_by_code", None)
        bot.send_message(
            message.chat.id,
            "🔢 Kino kodini kiriting (3 yoki 4 xonali):\n\n"
            "📝 Masalan: 1111"
        )
        return

    elif text == "➕ Guruhga qo'shish":
        invite_link = get_bot_invite_link()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            "➕ Guruhga qo'shish",
            url=invite_link
        ))
        bot.send_message(
            message.chat.id,
            "🤖 <b>Botni guruhingizga qo'shing!</b>\n\n"
            "✅ Guruhingizda kinolarni tezda topish\n"
            "✅ Barcha a'zolar foydalanishi mumkin\n"
            "✅ Kod yuboring, kino tayyor!\n\n"
            "👇 Quyidagi tugmani bosib guruhingizga qo'shing:",
            reply_markup=markup
        )
        return

    elif text == "ℹ️ Bizga qo'shiling":
        count = get_movies_count()
        bot.send_message(
            message.chat.id,
            "<b>🎬 MediaFox jamoasiga qo'shiling!</b>\n\n"
            "<i>Salom, kino va media ixlosmandlari!</i>\n\n"
            "🚀 Sizni MediaFox jamoasiga qo'shilishga taklif qilamiz! "
            "Hamkorlik orqali siz:\n"
            "• <b>Eksklyuziv kontent</b>ga ega bo'lasiz\n"
            "• <b>Loyihalarda faol ishtirok</b> qilishingiz mumkin\n"
            "• <b>Yangiliklar va maxsus imkoniyatlar</b>ni birinchi bo'lib bilasiz\n\n"
            "💡 Biz bilan birga <i>qiziqarli va interaktiv loyihalarda</i> ishtirok eting!\n\n"
            f"📊 Bazada <b>{count}</b> ta media mavjud\n\n"
            "🤝 Ma'lumot uchun: <b>@Azizbek_7003</b>\n",
            reply_markup=create_main_menu() if not (session and session.get("is_admin")) else create_admin_menu()
        )
        return

    elif text == "📤 Kino yuklash" and session and session.get("is_admin"):
        bot.send_message(message.chat.id, "📹 Endi kino videosini yuboring.")
        return

    # === AGAR ADMIN KOD KIRITAYOTGAN BO'LSA ===
    if session and session.get("is_admin") and session.get("state") == "waiting_for_code":
        code = extract_code(text)
        if not code:
            bot.send_message(message.chat.id, "❌ Iltimos, 3 yoki 4 xonali kod kiriting.")
            return

        # Kod mavjudligini tekshirish
        existing = get_movie_by_code(code)
        if existing:
            bot.send_message(
                message.chat.id,
                f"⚠️ <code>{code}</code> kodi allaqachon mavjud!\n\n"
                f"📝 Mavjud kino: {existing.get('description', 'Noma\'lum')}\n\n"
                "Boshqa kod kiriting."
            )
            return

        temp_data = session.get("temp_data", {})
        temp_data["code"] = code
        update_user_session(user_id, True, "waiting_for_desc", temp_data)
        bot.send_message(message.chat.id, "✍️ Endi shu kino uchun izoh (nom yoki tavsif) kiriting.")
        return

    # === AGAR ADMIN IZOH YOZAYOTGAN BO'LSA ===
    if session and session.get("is_admin") and session.get("state") == "waiting_for_desc":
        temp_data = session.get("temp_data", {})
        code = temp_data.get("code")
        video_message_id = temp_data.get("message_id")
        desc = text

        caption = f"🎬 Media kodi: {code}\n📝 Media nomi: {desc}\n\n Bot: @Mediafoxtv_bot"

        try:
            # Kanalla yuborish
            sent = bot.copy_message(
                chat_id=STORAGE_CHANNEL,
                from_chat_id=message.chat.id,
                message_id=video_message_id,
                caption=caption
            )
            
            # Supabase-ga saqlash
            if save_movie(code, sent.message_id, desc):
                count = get_movies_count()
                bot.send_message(
                    message.chat.id,
                    f"✅ Kino muvaffaqiyatli saqlandi!\n\n"
                    f"🎬 Kod: <code>{code}</code>\n"
                    f"📝 {desc}\n"
                    f"💾 Supabase-da saqlandi\n\n"
                    f"📊 Jami: <b>{count}</b> ta Media",
                    reply_markup=create_admin_menu()
                )
                clear_user_session(user_id)
            else:
                bot.send_message(message.chat.id, "⚠️ Ma'lumotlar bazasiga saqlashda xatolik yuz berdi.")
        except Exception as e:
            logger.error(f"Video yuklashda xato: {e}")
            bot.send_message(message.chat.id, "⚠️ Video yuklashda xatolik yuz berdi.")
        return

    # === KOD BILAN QIDIRISH ===
    if session and session.get("state") == "search_by_code":
        code = extract_code(text)
        if not code:
            bot.send_message(message.chat.id, "❌ Iltimos, 3 yoki 4 xonali kod kiriting.")
            return

        movie = get_movie_by_code(code)
        if not movie:
            bot.send_message(message.chat.id, "❌ Bu kodga mos kino topilmadi.")
            return

        try:
            bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=STORAGE_CHANNEL,
                message_id=movie["message_id"]
            )
            clear_user_session(user_id)
        except Exception as e:
            logger.error(f"Kino yuborishda xato: {e}")
            bot.send_message(message.chat.id, "⚠️ Kino yuborishda xatolik yuz berdi.")
        return

    # === ODDIY KOD YUBORISH (state bo'lmasa) ===
    code = extract_code(text)
    if code:
        movie = get_movie_by_code(code)
        if movie:
            try:
                bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=STORAGE_CHANNEL,
                    message_id=movie["message_id"]
                )
            except Exception as e:
                logger.error(f"Kino yuborishda xato: {e}")
                bot.send_message(message.chat.id, "⚠️ Kino yuborishda xatolik yuz berdi.")
        else:
            bot.send_message(message.chat.id, "❌ Bu kodga mos kino topilmadi.")
    else:
        bot.send_message(
            message.chat.id,
            "❓ Iltimos, menyudan tanlang yoki to'g'ri kod kiriting.",
            reply_markup=create_main_menu() if not (session and session.get("is_admin")) else create_admin_menu()
        )


# ======== FLASK WEBHOOK ROUTE ========

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    """Telegram webhook handler"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return '', 403


@app.route('/')
def index():
    """Health check endpoint"""
    return 'Bot is running!', 200


@app.route('/set_webhook')
def set_webhook():
    """Webhook o'rnatish uchun endpoint"""
    if WEBHOOK_URL:
        webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
        bot.remove_webhook()
        result = bot.set_webhook(url=webhook_url)
        if result:
            return f'Webhook set successfully to {webhook_url}', 200
        else:
            return 'Failed to set webhook', 500
    else:
        return 'WEBHOOK_URL not configured', 500


# ======== ASOSIY QISM ========
if __name__ == "__main__":
    print("🎬 Bot ishga tushdi...")
    print(f"💾 Ma'lumotlar bazasi: Supabase")
    logger.info("Bot webhook rejimida ishlayapti...")
    
    # Supabase ulanishini tekshirish
    try:
        count = get_movies_count()
        print(f"✅ Supabase ulanish muvaffaqiyatli! Bazada {count} ta kino mavjud.")
    except Exception as e:
        print(f"⚠️ Supabase ulanish xatosi: {e}")
    
    # Webhook o'rnatish
    if WEBHOOK_URL:
        webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        print(f"✅ Webhook o'rnatildi: {webhook_url}")
    
    # Flask server ishga tushirish
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)


