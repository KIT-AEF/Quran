from flask import Flask
import subprocess
import threading
import time
import os
import requests

# --- 1. بيانات البث الخاصة بك ---
# =================================================================
SERVER_URL = "rtmps://dc4-1.rtmp.t.me/s/"
STREAM_KEY = "3204163505:BZcclelza7tVj0cVNLyOBQ"
# =================================================================

# --- إعدادات (لا تحتاج لتغييرها) ---
SURA_DIRECTORY = "quran_suras"
PLAYLIST_FILE = "playlist.txt"
BASE_AUDIO_URL = "https://server8.mp3quran.net/afs/" # رابط شيخ مشاري العفاسي

app = Flask(__name__)

@app.route('/')
def home():
    return "Quran Stream Bot is running."

# --- [التعديل الجديد] ---
# تم إضافة هذا المسار خصيصًا لخدمات المراقبة مثل cron-job
# لإبقاء الخدمة مستيقظة دون التسبب في خطأ "output too large"
@app.route('/health')
def health_check():
    """
    مسار مخصص لخدمات المراقبة. يعيد استجابة صغيرة وسريعة.
    """
    return "OK", 200
# --- نهاية التعديل ---

def download_all_suras():
    """
    تتحقق من وجود السور، وإذا لم تكن موجودة، تقوم بتحميلها كلها.
    """
    print("--> [INFO] التحقق من وجود ملفات السور...")
    if not os.path.exists(SURA_DIRECTORY):
        print(f"--> [INFO] المجلد '{SURA_DIRECTORY}' غير موجود، سيتم إنشاؤه.")
        os.makedirs(SURA_DIRECTORY)

    for i in range(1, 115): # من سورة 1 إلى 114
        sura_number = f'{i:03}' # تحويل الرقم إلى صيغة 001, 002, ...
        file_name = f"{sura_number}.mp3"
        file_path = os.path.join(SURA_DIRECTORY, file_name)
        
        if os.path.exists(file_path):
            print(f"--> [SUCCESS] سورة رقم {sura_number} موجودة بالفعل.")
            continue

        print(f"--> [DOWNLOAD] جاري تحميل سورة رقم {sura_number}...")
        audio_url = f"{BASE_AUDIO_URL}{sura_number}.mp3"
        
        try:
            response = requests.get(audio_url, stream=True)
            response.raise_for_status()
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"--> [SUCCESS] تم تحميل سورة رقم {sura_number} بنجاح.")
        except requests.exceptions.RequestException as e:
            print(f"!!! [ERROR] فشل تحميل سورة {sura_number}: {e}")
            if os.path.exists(file_path):
                os.remove(file_path)
            break

def create_playlist():
    """
    ينشئ ملف playlist.txt يحتوي على قائمة بالسور لتشغيلها بالترتيب.
    """
    print("--> [INFO] جاري إنشاء قائمة التشغيل (playlist.txt)...")
    sura_files = sorted([f for f in os.listdir(SURA_DIRECTORY) if f.endswith('.mp3')])

    if not sura_files:
        print(f"!!! [ERROR] المجلد '{SURA_DIRECTORY}' فارغ. لا يمكن إنشاء قائمة التشغيل.")
        return False
        
    with open(PLAYLIST_FILE, 'w', encoding='utf-8') as f:
        for sura_file in sura_files:
            f.write(f"file '{SURA_DIRECTORY}/{sura_file}'\n")
    print(f"--> [SUCCESS] تم إنشاء قائمة التشغيل بنجاح وتحتوي على {len(sura_files)} سورة.")
    return True

def start_ffmpeg_stream():
    """
    يبدأ عملية بث FFmpeg باستخدام قائمة التشغيل.
    """
    if "الصق" in SERVER_URL or "الصق" in STREAM_KEY:
        print("!!! خطأ: يرجى وضع بيانات البث الصحيحة.")
        return
    print("--> [INFO] ستبدأ محاولة تشغيل البث التسلسلي...")
    time.sleep(3)
    try:
        full_rtmp_url = f"{SERVER_URL.strip()}/{STREAM_KEY.strip()}"
        command = [
            'ffmpeg', '-re', '-stream_loop', '-1', '-f', 'concat',
            '-safe', '0', '-i', PLAYLIST_FILE, '-vn', '-c:a', 'aac', '-ar', '44100',
            '-b:a', '128k', '-f', 'flv', full_rtmp_url
        ]
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, encoding='utf-8', errors='ignore'
        )
        for line in process.stdout:
            print(line.strip())
    except Exception as e:
        print(f"!!! [ERROR] حدث خطأ أثناء تشغيل FFmpeg: {e}")

if __name__ == '__main__':
    # الخطوة 1: تحميل جميع السور إذا لم تكن موجودة
    download_all_suras()

    # الخطوة 2: إنشاء قائمة التشغيل من الملفات الموجودة
    if create_playlist():
        # الخطوة 3: بدء عملية البث في خيط منفصل
        stream_thread = threading.Thread(target=start_ffmpeg_stream)
        stream_thread.daemon = True
        stream_thread.start()

        # الخطوة 4: تشغيل خادم الويب
        app.run(host='0.0.0.0', port=8080)
