# Echo Room - Chat Application

تطبيق دردشة متكامل مبني بـ Flask و SocketIO

## المميزات
- نظام تسجيل دخول وإنشاء حساب
- إنشاء السيرفرات والقنوات
- دردشة فورية (Real-time)
- نظام الأصدقاء
- مكالمات صوتية ومرئية (WebRTC)
- مشاركة الشاشة
- حفظ الرسائل والجلسات

## متطلبات التشغيل
- Python 3.11+
- المكتبات المذكورة في requirements.txt

## التشغيل المحلي
```bash
# تثبيت المكتبات
pip install -r requirements.txt

# تشغيل التطبيق
python app.py
```

## الرفع على Railway

### الخطوات:
1. أنشئ حساب على Railway.app
2. اضغط "New Project"
3. اختر "Deploy from GitHub repo"
4. ارفع الملفات التالية:
   - app.py
   - index.html
   - requirements.txt
   - Procfile
   - runtime.txt (اختياري)
   - .gitignore

5. Railway سيكتشف الإعدادات تلقائياً ويبدأ التشغيل

### ملاحظات مهمة:
- التطبيق سيعمل على المنفذ (PORT) المحدد من Railway تلقائياً
- ملف data/ سيُنشأ تلقائياً لحفظ البيانات
- لا حاجة لإعدادات إضافية

## البنية
```
.
├── app.py              # ملف الباك اند الرئيسي
├── index.html          # واجهة المستخدم
├── requirements.txt    # المكتبات المطلوبة
├── Procfile           # إعدادات Railway
├── runtime.txt        # نسخة Python
└── data/              # مجلد البيانات (يُنشأ تلقائياً)
    ├── users.json
    ├── messages.json
    ├── servers.json
    ├── channels.json
    ├── friends.json
    ├── emojis.json
    └── sessions.json
```

## المنافذ المستخدمة
- المنفذ الافتراضي: 5000
- سيتم استخدام المنفذ المحدد من Railway تلقائياً

## الدعم الفني
للمشاكل أو الاستفسارات، راجع التوثيق الرسمي لـ Railway
