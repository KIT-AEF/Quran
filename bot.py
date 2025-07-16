import os
import json
import random
import logging
import telebot
from flask import Flask, request

# --- الإعدادات ---

# يفضل قراءة التوكن من متغيرات البيئة على Render.
# إذا لم يجده، سيستخدم التوكن المكتوب هنا.
# !! تأكد من استخدام توكن جديد وسري !!
BOT_TOKEN = os.environ.get('BOT_TOKEN', "7875008240:AAEJs7FCGrtNF8why6IJf4vAX-FZgYyEgA0")


# --- تهيئة البوت والتطبيق ---
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


# --- تحميل بيانات القرآن الكريم ---
try:
    # المسار الكامل للملف على PythonAnywhere أو المسار النسبي على Render
    # استخدام os.path.join يجعله أكثر مرونة
    current_dir = os.path.dirname(os.path.abspath(__file__))
    quran_file_path = os.path.join(current_dir, 'quran.json')
    with open(quran_file_path, 'r', encoding='utf-8') as f:
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
    """الرد على أمر /start برسالة جديدة"""
    chat_id = message.chat.id
    welcome_text = "أهلاً بك في بوت آيات القرآن الكريم.\nأرسل الأمر /new للحصول على آية عشوائية."
    bot.send_message(chat_id, welcome_text)

@bot.message_handler(commands=['new'])
def send_new_ayah(message):
    """إرسال آية جديدة عند استقبال أمر /new"""
    chat_id = message.chat.id
    ayah_text = get_random_ayah()
    bot.send_message(chat_id, ayah_text)


# هذا الجزء مهم لـ Render للتأكد من أن الويب هوك يتم إعداده عند بدء التشغيل
try:
    RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')
    if RENDER_EXTERNAL_URL:
        bot.remove_webhook()
        bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{BOT_TOKEN}")
        logging.info("تم إعداد الويب هوك بنجاح على Render.")
except Exception as e:
    logging.error(f"لم يتمكن من إعداد الويب هوك تلقائيًا: {e}")
