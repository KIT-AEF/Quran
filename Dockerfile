# 1. ابدأ من صورة بايثون رسمية
FROM python:3.9-slim

# 2. قم بتثبيت FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

# 3. جهز مجلد العمل داخل الخادم
WORKDIR /app

# 4. انسخ ملف المتطلبات
COPY requirements.txt .

# 5. قم بتثبيت مكتبات بايثون (Flask, requests)
RUN pip install --no-cache-dir -r requirements.txt

# 6. انسخ باقي ملفات الكود (ملف main.py)
COPY . .

# 7. حدد الأمر الذي سيتم تشغيله عند بدء التشغيل
CMD ["python", "main.py"]
