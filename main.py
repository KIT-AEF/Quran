import os
import time
import json
import threading
import subprocess
import requests
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- 1. إعدادات البث الأساسية ---
SERVER_URL = "rtmps://dc4-1.rtmp.t.me/s/"
STREAM_KEY = "3204163505:BZcclelza7tVj0cVNLyOBQ"
SURA_DIRECTORY = "quran_suras"
BASE_AUDIO_URL = "https://server8.mp3quran.net/afs/"

# --- 2. إعدادات بوت التليجرام (مهم: قم بملء هذه البيانات) ---
TELEGRAM_BOT_TOKEN = "8428224491:AAEQA4jVdmITDaA8Wx2xUCQp2E_fAkU2vN4"
ADMIN_USER_ID = 7115401970  # هنا ضع رقم الـ ID الخاص بحسابك على تليجرام

# --- 3. متغيرات عامة لإدارة حالة البث ---
STATE_FILE = "stream_state.json"
stream_process = None
should_stream = threading.Event() # للتحكم في بدء وإيقاف حلقة البث
sura_files = [] # قائمة بملفات السور المرتبة

app = Flask(__name__)

# --- وظائف إدارة حالة البث ---

def load_stream_state():
    """تحميل حالة البث (آخر سورة تم تشغيلها) من ملف JSON."""
    if not os.path.exists(STATE_FILE):
        return {"current_sura_index": 0}
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"current_sura_index": 0}

def save_stream_state(state):
    """حفظ الحالة الحالية للبث في ملف JSON."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

# --- وظائف تجهيز المحتوى ---

def download_all_suras():
    """تحميل جميع ملفات السور إذا لم تكن موجودة."""
    print("--> [INFO] التحقق من وجود ملفات السور...")
    os.makedirs(SURA_DIRECTORY, exist_ok=True)
    for i in range(1, 115):
        sura_number_str = f'{i:03}'
        file_path = os.path.join(SURA_DIRECTORY, f"{sura_number_str}.mp3")
        if os.path.exists(file_path):
            continue
        print(f"--> [DOWNLOAD] جاري تحميل سورة رقم {sura_number_str}...")
        try:
            response = requests.get(f"{BASE_AUDIO_URL}{sura_number_str}.mp3", stream=True)
            response.raise_for_status()
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"--> [SUCCESS] تم تحميل سورة {sura_number_str}.")
        except requests.exceptions.RequestException as e:
            print(f"!!! [ERROR] فشل تحميل سورة {sura_number_str}: {e}")
            break

def prepare_sura_list():
    """تجهيز قائمة مرتبة بمسارات ملفات السور."""
    global sura_files
    if not os.path.exists(SURA_DIRECTORY):
        print(f"!!! [ERROR] المجلد '{SURA_DIRECTORY}' غير موجود.")
        return False
    sura_files = sorted([os.path.join(SURA_DIRECTORY, f) for f in os.listdir(SURA_DIRECTORY) if f.endswith('.mp3')])
    if not sura_files:
        print(f"!!! [ERROR] لا توجد ملفات صوتية في المجلد '{SURA_DIRECTORY}'.")
        return False
    print(f"--> [SUCCESS] تم تجهيز قائمة التشغيل وتحتوي على {len(sura_files)} سورة.")
    return True

# --- وظائف التحكم في البث (FFmpeg) ---

def run_streaming_loop():
    """
    الحلقة الرئيسية التي تدير البث.
    تقوم بتشغيل سورة تلو الأخرى وتحفظ التقدم.
    """
    global stream_process
    print("--> [INFO] حلقة البث بدأت وتنتظر أمر التشغيل...")
    
    while True:
        should_stream.wait() # تتوقف هنا حتى يتم استدعاء should_stream.set()

        state = load_stream_state()
        current_sura_index = state.get("current_sura_index", 0)

        # التأكد من أن المؤشر ضمن نطاق القائمة
        if current_sura_index >= len(sura_files):
            current_sura_index = 0

        sura_to_play = sura_files[current_sura_index]
        print(f"--> [STREAMING] سيبدأ البث الآن من: {os.path.basename(sura_to_play)}")

        full_rtmp_url = f"{SERVER_URL.strip()}/{STREAM_KEY.strip()}"
        command = [
            'ffmpeg', '-re', '-i', sura_to_play,
            '-vn', '-c:a', 'aac', '-ar', '44100', '-b:a', '128k',
            '-f', 'flv', full_rtmp_url
        ]

        try:
            # بدء عملية FFmpeg
            stream_process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, encoding='utf-8', errors='ignore'
            )

            # طباعة مخرجات FFmpeg (مفيد للمراقبة)
            for line in stream_process.stdout:
                print(line.strip())
            
            stream_process.wait() # انتظار انتهاء العملية

        except Exception as e:
            print(f"!!! [ERROR] حدث خطأ في عملية FFmpeg: {e}")
            time.sleep(5) # انتظار 5 ثواني قبل المحاولة مجدداً

        finally:
            stream_process = None
            if should_stream.is_set(): # إذا لم يتم إيقاف البث يدويًا
                # الانتقال إلى السورة التالية وحفظ الحالة
                next_sura_index = (current_sura_index + 1) % len(sura_files)
                save_stream_state({"current_sura_index": next_sura_index})
                print(f"--> [INFO] انتهت السورة الحالية. سيتم تشغيل السورة التالية.")
            else:
                print("--> [INFO] تم إيقاف البث يدويًا.")


# --- أوامر بوت التليجرام ---

async def start_stream_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر لبدء البث."""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("عذرًا، هذا الأمر متاح للمدير فقط.")
        return

    if should_stream.is_set():
        await update.message.reply_text("✅ البث يعمل بالفعل.")
        return

    should_stream.set()
    await update.message.reply_text("🚀 تم إعطاء أمر بدء البث. سيبدأ خلال لحظات...")
    print("--> [COMMAND] تم استقبال أمر بدء البث من المدير.")

async def stop_stream_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر لإيقاف البث."""
    global stream_process
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("عذرًا، هذا الأمر متاح للمدير فقط.")
        return

    if not should_stream.is_set():
        await update.message.reply_text("ℹ️ البث متوقف بالفعل.")
        return

    should_stream.clear()
    if stream_process:
        try:
            stream_process.terminate() # محاولة إيقاف عملية FFmpeg
            stream_process = None
            print("--> [COMMAND] تم إيقاف عملية FFmpeg.")
        except Exception as e:
            print(f"!!! [ERROR] لم يتم إيقاف FFmpeg بنجاح: {e}")
    
    await update.message.reply_text("🛑 تم إعطاء أمر إيقاف البث. قد يستغرق لحظة ليتوقف تمامًا.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر لمعرفة حالة البث والسورة الحالية."""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("عذرًا، هذا الأمر متاح للمدير فقط.")
        return
        
    state = load_stream_state()
    current_sura_index = state.get("current_sura_index", 0)
    sura_name = os.path.basename(sura_files[current_sura_index])

    if should_stream.is_set() and stream_process:
        status_message = (
            f"🟢 **حالة البث: يعمل**\n\n"
            f"📖 **السورة الحالية (أو التالية):** `{sura_name}`"
        )
    else:
        status_message = (
            f"🔴 **حالة البث: متوقف**\n\n"
            f"📖 **السورة التالية عند التشغيل:** `{sura_name}`"
        )
    
    await update.message.reply_text(status_message, parse_mode='Markdown')

# --- إعدادات خادم الويب (Flask) ---
@app.route('/')
def home():
    return "Quran Stream Bot is running with Telegram control."

@app.route('/health')
def health_check():
    return "OK", 200

# --- الدالة الرئيسية للتشغيل ---
def main():
    # الخطوة 1: تحميل السور وتجهيز القائمة
    download_all_suras()
    if not prepare_sura_list():
        return

    # الخطوة 2: بدء حلقة البث في خيط منفصل
    stream_thread = threading.Thread(target=run_streaming_loop)
    stream_thread.daemon = True
    stream_thread.start()

    # الخطوة 3: إعداد وتشغيل بوت التليجرام
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("startstream", start_stream_command))
    application.add_handler(CommandHandler("stopstream", stop_stream_command))
    application.add_handler(CommandHandler("status", status_command))
    
    # تشغيل البوت في خيط منفصل حتى لا يتعارض مع Flask
    bot_thread = threading.Thread(target=application.run_polling)
    bot_thread.daemon = True
    bot_thread.start()
    
    print("--> [SUCCESS] بوت التليجرام جاهز ويعمل الآن.")

    # الخطوة 4: تشغيل خادم الويب (للاستضافة على Render)
    app.run(host='0.0.0.0', port=8080)

if __name__ == '__main__':
    main()
