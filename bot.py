import os
import json
import random
import logging
import telebot
from flask import Flask, request

# --- الإعدادات ---

# 1. احصل على التوكن من متغيرات البيئة. هذا هو الأسلوب الأكثر أمانًا على Render.
# (سنقوم بإعداده في لوحة تحكم Render لاحقًا)
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# 2. إذا لم تجد التوكن كمتغير بيئة، استخدم هذا التوكن المؤقت (للتجربة فقط).
# !! هام: استبدله بالتوكن الجديد والسري الخاص بك.
if not BOT_TOKEN:
    BOT_TOKEN = "7289246350:AAGv8tDGiClli1veXVJ4nstGU52cLr-0wU8" # <--- !! ضع التوكن هنا للتجربة فقط !!


# --- تهيئة البوت والتطبيق ---
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


# --- تحميل بيانات القرآن الكريم ---
try:
    # هذا المسار سيعمل على Render لأن الملفات تكون في نفس المجلد
    with open('quran.json', 'r', encoding='utf-8') as f:
        QURAN_DATA = json.load(f)
    logging.info("تم تحميل ملف القرآن بنجاح.")
except Exception as e:
    logging.error(f"خطأ فادح في تحميل ملف القرآن: {e}")
    QURAN_DATA = None


# --- دوال البوت الأساسية ---
def get_random_ayah():
    """تختار هذه الدالة سورة وآية عشوائية وتعيد النص المنسق."""
    if not QURAN_DATA:
        return "عذرًا، حدث خطأ في تحميل بيانات القرآن."
    
    try:
        random_surah = random.choice(QURAN_DATA)
        random_verse = random.choice(random_surah['verses'])
        
        surah_name = random_surah['name']
        surah_transliteration = random_surah['transliteration']
        verse_number = random_verse['id']
        verse_text = random_verse['text']
        
        message = (
            f"{verse_text}\n\n"
            f"📖 {surah_name} ({surah_transliteration}) - الآية {verse_number}"
        )
        return message
    except Exception as e:
        logging.error(f"خطأ في اختيار آية: {e}")
        return "عذرًا، لم أتمكن من جلب آية في الوقت الحالي."


# --- Webhook Handler (نقطة اتصال تليجرام) ---
# تليجرام سيرسل التحديثات إلى هذا الرابط
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    """يستقبل التحديثات من تليجرام."""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '!', 200
    else:
        return 'خطأ، الطلب غير صحيح.', 403


# --- معالجات الأوامر (Handlers) ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    """الرد على أمر /start"""
    bot.reply_to(message, "أهلاً بك في بوت آيات القرآن الكريم. أرسل الأمر /new للحصول على آية عشوائية.")

@bot.message_handler(commands=['new'])
def send_new_ayah(message):
    """الرد على أمر /new"""
    ayah_text = get_random_ayah()
    bot.reply_to(message, ayah_text)


# هذا الجزء مهم لـ Render للتأكد من أن الويب هوك يتم إعداده عند بدء التشغيل
# أو يمكنك إعداده يدويًا باستخدام أمر curl كما شرحت سابقًا.
try:
    # الحصول على رابط الخدمة من متغيرات البيئة التي يوفرها Render تلقائيًا
    RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')
    if RENDER_EXTERNAL_URL:
        # إزالة الويب هوك القديم أولاً ثم إعداد الجديد
        bot.remove_webhook()
        bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{BOT_TOKEN}")
        logging.info(f"تم إعداد الويب هوك بنجاح على Render.")
except Exception as e:
    logging.error(f"لم يتمكن من إعداد الويب هوك تلقائيًا: {e}")