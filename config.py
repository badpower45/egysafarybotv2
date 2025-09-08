# -*- coding: utf-8 -*-
# ملف لتخزين الإعدادات الحساسة مثل توكن البوت

import os

# استخدام متغير البيئة من Replit Secrets
BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    print("!!! خطأ فادح: لم يتم العثور على BOT_TOKEN في متغيرات البيئة.")
    print("!!! تأكد من إضافة BOT_TOKEN إلى Replit Secrets.")
    exit()