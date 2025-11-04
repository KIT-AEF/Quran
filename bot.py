from flask import Flask
import subprocess
import threading
import time
import os

# --- 1. تم إضافة بيانات البث الخاصة بك ---
# =================================================================
SERVER_URL = "rtmps://dc4-1.rtmp.t.me/s/"
STREAM_KEY = "3204163505:BZcclelza7tVj0cVNLyOBQ"
# =================================================================

# --- إعدادات (لا تحتاج لتغييرها) ---
SURA_DIRECTORY = "quran_suras"
PLAYLIST_FILE = "playlist.txt"

app = Flask(__name__)

@app.route('/')
def home():
    return "Quran Stream Bot is running sequentially."

def create_playlist():
    """
    ينشئ ملف playlist.txt يحتوي على قائمة بالسور لتشغيلها بالترتيب.
    """
    print("--> [INFO] جاري إنشاء قائمة التشغيل (playlist.txt)...")
    try:
        if not os.path.isdir(SURA_DIRECTORY) or not os.listdir(SURA_DIRECTORY):
            print(f"!!! [ERROR] المجلد '{SURA_DIRECTORY}' فارغ أو غير موجود.")
            print("!!! [ERROR] يرجى التأكد من اكتمال تحميل السور أولاً.")
            return False

        # الحصول على قائمة بالسور وفرزها لضمان الترتيب الصحيح
        sura_files = sorted([f for f in os.listdir(SURA_DIRECTORY) if f.endswith('.mp3')])

        with open(PLAYLIST_FILE, 'w', encoding='utf-8') as f:
            for sura_file in sura_files:
                # كتابة المسار بالشكل الذي يفهمه FFmpeg
                f.write(f"file '{SURA_DIRECTORY}/{sura_file}'\n")

        print(f"--> [SUCCESS] تم إنشاء قائمة التشغيل بنجاح وتحتوي على {len(sura_files)} سورة.")
        return True
    except Exception as e:
        print(f"!!! [ERROR] فشل إنشاء قائمة التشغيل: {e}")
        return False

def start_ffmpeg_stream():
    if "الصق" in SERVER_URL or "الصق" in STREAM_KEY:
        print("!!! خطأ: يرجى وضع بيانات البث الصحيحة.")
        return

    print("--> [INFO] ستبدأ محاولة تشغيل البث التسلسلي...")
    time.sleep(3)

    try:
        full_rtmp_url = f"{SERVER_URL.strip()}/{STREAM_KEY.strip()}"

        # أمر FFmpeg المطور ليقرأ من قائمة التشغيل ويكررها
        command = [
            'ffmpeg',
            '-re',
            '-stream_loop', '-1',  # تكرار قائمة التشغيل بأكملها إلى ما لا نهاية
            '-f', 'concat',
            '-safe', '0',
            '-i', PLAYLIST_FILE,
            '-vn', '-c:a', 'aac', '-ar', '44100', '-b:a', '128k',
            '-f', 'flv', full_rtmp_url
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
    # الخطوة 1: إنشاء قائمة التشغيل
    if create_playlist():
        # الخطوة 2: بدء عملية البث
        stream_thread = threading.Thread(target=start_ffmpeg_stream)
        stream_thread.daemon = True
        stream_thread.start()

        # الخطوة 3: تشغيل خادم الويب
        app.run(host='0.0.0.0', port=8080)
