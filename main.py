import os
import time
import json
import threading
import subprocess
import requests
import telebot
from flask import Flask

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
should_stream = threading.Event()
sura_files = []

# --- 4. إعداد تطبيق فلاسك وبوت تليجرام ---
app = Flask(__name__)
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode='Markdown')

# --- وظائف إدارة حالة البث (بدون تغيير) ---

def load_stream_state():
    if not os.path.exists(STATE_FILE):
        return {"current_sura_index": 0}
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"current_sura_index": 0}

def save_stream_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

# --- وظائف تجهيز المحتوى (بدون تغيير) ---

def download_all_suras():
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
    global sura_files
    if not os.path.exists(SURA_DIRECTORY):
        return False
    sura_files = sorted([os.path.join(SURA_DIRECTORY, f) for f in os.listdir(SURA_DIRECTORY) if f.endswith('.mp3')])
    if not sura_files:
        return False
    print(f"--> [SUCCESS] تم تجهيز قائمة التشغيل وتحتوي على {len(sura_files)} سورة.")
    return True

# --- وظائف التحكم في البث (بدون تغيير) ---

def run_streaming_loop():
    global stream_process
    print("--> [INFO] حلقة البث بدأت وتنتظر أمر التشغيل...")
    while True:
        should_stream.wait() # يتوقف هنا حتى يتم إعطاء أمر التشغيل
        state = load_stream_state()
        current_sura_index = state.get("current_sura_index", 0)
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
            stream_process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, encoding='utf-8', errors='ignore'
            )
            for line in stream_process.stdout:
                print(line.strip())
            stream_process.wait()
        except Exception as e:
            print(f"!!! [ERROR] حدث خطأ في عملية FFmpeg: {e}")
            time.sleep(5)
        finally:
            stream_process = None
            if should_stream.is_set():
                next_sura_index = (current_sura_index + 1) % len(sura_files)
                save_stream_state({"current_sura_index": next_sura_index})
                print(f"--> [INFO] انتهت السورة الحالية. سيتم تشغيل السورة التالية.")
            else:
                print("--> [INFO] تم إيقاف البث يدويًا.")

# --- أوامر بوت التليجرام (باستخدام Telebot) ---

def is_admin(message):
    """فلتر للتحقق من أن المستخدم هو المدير."""
    return message.from_user.id == ADMIN_USER_ID

@bot.message_handler(commands=['startstream'], func=is_admin)
def start_stream_command(message):
    if should_stream.is_set():
        bot.reply_to(message, "✅ البث يعمل بالفعل.")
        return
    should_stream.set()
    bot.reply_to(message, "🚀 تم إعطاء أمر بدء البث. سيبدأ خلال لحظات...")
    print("--> [COMMAND] تم استقبال أمر بدء البث من المدير.")

@bot.message_handler(commands=['stopstream'], func=is_admin)
def stop_stream_command(message):
    global stream_process
    if not should_stream.is_set():
        bot.reply_to(message, "ℹ️ البث متوقف بالفعل.")
        return
    should_stream.clear()
    if stream_process:
        try:
            stream_process.terminate()
            print("--> [COMMAND] تم إيقاف عملية FFmpeg.")
        except Exception as e:
            print(f"!!! [ERROR] لم يتم إيقاف FFmpeg بنجاح: {e}")
    bot.reply_to(message, "🛑 تم إعطاء أمر إيقاف البث.")

@bot.message_handler(commands=['status'], func=is_admin)
def status_command(message):
    state = load_stream_state()
    current_sura_index = state.get("current_sura_index", 0)
    sura_name = os.path.basename(sura_files[current_sura_index])
    if should_stream.is_set():
        status_message = (
            f"🟢 *حالة البث: يعمل*\n\n"
            f"📖 *السورة الحالية (أو التالية):* `{sura_name}`"
        )
    else:
        status_message = (
            f"🔴 *حالة البث: متوقف*\n\n"
            f"📖 *السورة التالية عند التشغيل:* `{sura_name}`"
        )
    bot.reply_to(message, status_message)

@bot.message_handler(func=lambda message: not is_admin(message))
def unauthorized_user(message):
    """الرد على المستخدمين غير المصرح لهم."""
    bot.reply_to(message, "عذرًا، هذا البوت خاص بالتحكم في البث وغير متاح للعامة.")

def run_bot():
    """تشغيل البوت في حلقة مستمرة لضمان عدم توقفه."""
    print("--> [SUCCESS] بوت تليجرام جاهز ويعمل الآن.")
    while True:
        try:
            bot.polling(non_stop=True)
        except Exception as e:
            print(f"!!! [ERROR] خطأ في بوت تليجرام، إعادة التشغيل خلال 15 ثانية: {e}")
            time.sleep(15)

# --- إعدادات خادم الويب (بدون تغيير) ---
@app.route('/')
def home():
    return "Quran Stream Bot is running with Telegram control (Telebot)."

@app.route('/health')
def health_check():
    return "OK", 200

# --- الدالة الرئيسية للتشغيل ---
if __name__ == '__main__':
    # 1. تحميل السور وتجهيز القائمة
    download_all_suras()
    if prepare_sura_list():
        # 2. بدء خيط البث في الخلفية
        stream_thread = threading.Thread(target=run_streaming_loop, daemon=True)
        stream_thread.start()

        # 3. بدء بوت التليجرام في خيط منفصل
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()

        # 4. تشغيل خادم الويب في الخيط الرئيسي (للاستضافة على Render)
        port = int(os.environ.get("PORT", 8080))
        app.run(host='0.0.0.0', port=port)
