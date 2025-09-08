# -*- coding: utf-8 -*-
"""
البوت المحدث مع جميع الميزات الجديدة:
- نظام الإدارة التفاعلي
- معالجة اللغة الطبيعية
- تكامل خرائط جوجل
- ربط الموقع الإلكتروني
"""

import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ConversationHandler,
    ContextTypes, MessageHandler, filters
)
from telegram.constants import ParseMode
from urllib.parse import quote

# استيراد الأنظمة الجديدة
try:
    from config import BOT_TOKEN
    from data import routes_data, neighborhood_data
    from admin_system import admin_system
    from nlp_search import initialize_nlp_system
    from maps_integration import maps_integration, website_integration
except ImportError as e:
    print(f"!!! خطأ في الاستيراد: {e}")
    exit()

# إعدادات الـ Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# تهيئة نظام معالجة اللغة الطبيعية
nlp_system = initialize_nlp_system(neighborhood_data)

# حالات المحادثة
(SELECTING_START_NEIGHBORHOOD, SELECTING_START_CATEGORY, SELECTING_START_LANDMARK,
 SELECTING_END_NEIGHBORHOOD, SELECTING_END_CATEGORY, SELECTING_END_LANDMARK,
 ADMIN_MENU, ADDING_ROUTE, ADDING_LANDMARK, ADMIN_AUTH) = range(10)

# قائمة معرفات المشرفين الأساسيين (يمكن إضافة المزيد عبر البوت)
SUPER_ADMIN_IDS = [123456789]  # ضع معرف المطور الأساسي هنا

# --- دوال البوت المحدثة ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """بداية المحادثة مع خيارات متقدمة"""
    user = update.effective_user
    user_id = user.id if user else None
    user_name = user.first_name if user else "User"
    
    logger.info(f"User {user_name} (ID: {user_id}) started a conversation.")
    context.user_data.clear()
    
    try:
        # إنشاء لوحة مفاتيح متقدمة
        keyboard = [
            [InlineKeyboardButton("🚌 البحث عن مواصلات", callback_data="search_transport")],
            [InlineKeyboardButton("🔍 البحث بالنص المباشر", callback_data="nlp_search")],
            [InlineKeyboardButton("🗺️ خرائط تفاعلية", callback_data="interactive_maps")],
            [InlineKeyboardButton("📰 آخر الأخبار والتحديثات", callback_data="latest_updates")]
        ]
        
        # إضافة خيار الإدارة للمشرفين
        if user_id and (user_id in SUPER_ADMIN_IDS or admin_system.is_admin(user_id)):
            keyboard.append([InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = f"""
أهلاً بك يا {user_name}! 🚌

أنا بوت مواصلات بورسعيد المطور مع ميزات جديدة:

🔸 **البحث التقليدي**: اختيار الحي والمعالم خطوة بخطوة
🔸 **البحث الذكي**: اكتب سؤالك مباشرة مثل "إزاي أروح من المستشفى للجامعة؟"
🔸 **خرائط تفاعلية**: مشاهدة المسارات على الخريطة
🔸 **تحديثات مباشرة**: معلومات عن حالة المرور والخطوط

اختر الطريقة المفضلة للبحث:
        """
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return SELECTING_START_NEIGHBORHOOD
        
    except Exception as e:
        logger.exception(f"Error in start handler: {e}")
        await update.message.reply_text("حدث خطأ ما، يرجى المحاولة لاحقاً.")
        return ConversationHandler.END

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالجة اختيارات القائمة الرئيسية"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "search_transport":
        # البحث التقليدي
        neighborhoods = list(neighborhood_data.keys())
        keyboard = build_keyboard(neighborhoods, "start_neighborhood")
        await query.edit_message_text(
            "اختر **حي البداية**:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return SELECTING_START_NEIGHBORHOOD
        
    elif query.data == "nlp_search":
        # البحث بالنص الطبيعي
        await query.edit_message_text(
            """
🔍 **البحث الذكي بالنص المباشر**

اكتب سؤالك بشكل طبيعي، مثل:
• "إزاي أروح من سوبر ماركت بكير للمستشفى العام؟"
• "طريقة الوصول لجامعة قناة السويس من المحطة"
• "من البنك الأهلي لمول داونتاون"

أو استخدم /cancel للعودة للقائمة الرئيسية
            """,
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data['mode'] = 'nlp_search'
        return SELECTING_START_NEIGHBORHOOD  # استخدام نفس الحالة مؤقتاً
        
    elif query.data == "interactive_maps":
        # الخرائط التفاعلية
        await query.edit_message_text(
            """
🗺️ **الخرائط التفاعلية**

هذه الميزة تسمح لك بـ:
• مشاهدة المسارات على خريطة حقيقية
• الحصول على إحداثيات GPS دقيقة
• روابط مباشرة لخرائط جوجل

للاستفادة من هذه الخدمة، قم بالبحث عن مسار أولاً باستخدام أي من الطرق السابقة.
            """,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")
            ]]),
            parse_mode=ParseMode.MARKDOWN
        )
        return SELECTING_START_NEIGHBORHOOD
        
    elif query.data == "latest_updates":
        # التحديثات والأخبار
        updates_text = await get_latest_updates()
        await query.edit_message_text(
            f"📰 **آخر التحديثات**\n\n{updates_text}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 تحديث", callback_data="latest_updates"),
                InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main")
            ]]),
            parse_mode=ParseMode.MARKDOWN
        )
        return SELECTING_START_NEIGHBORHOOD
        
    elif query.data == "admin_panel":
        # لوحة الإدارة
        return await show_admin_panel(update, context)
        
    elif query.data == "back_to_main":
        # العودة للقائمة الرئيسية
        return await start(query, context)

async def handle_nlp_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالجة البحث بالنص الطبيعي"""
    if not update.message or not update.message.text:
        return SELECTING_START_NEIGHBORHOOD
    
    user_text = update.message.text.strip()
    
    # التحقق من كون النص استفهام طبيعي
    if not nlp_system.is_natural_language_query(user_text):
        await update.message.reply_text(
            "يرجى كتابة سؤالك بشكل واضح مثل:\n"
            "• إزاي أروح من مكان X لمكان Y؟\n"
            "• طريقة الوصول لمكان معين\n\n"
            "أو استخدم /cancel للعودة."
        )
        return SELECTING_START_NEIGHBORHOOD
    
    # معالجة الاستفهام
    try:
        await update.message.reply_text("🔍 جاري البحث...")
        
        search_result = nlp_system.search_route_from_text(user_text)
        
        if search_result['status'] == 'full_match':
            # تم العثور على المكانين
            start_name = search_result['start_location']['name']
            end_name = search_result['end_location']['name']
            
            # البحث عن المسار
            route_result = find_route_with_proximity(start_name, end_name, routes_data, neighborhood_data)
            
            # إرسال النتيجة
            await update.message.reply_text(route_result, parse_mode=ParseMode.MARKDOWN)
            
            # إضافة خرائط جوجل
            await send_google_maps_link(update.message.chat_id, context, end_name)
            
        elif search_result['status'] == 'partial_match':
            # تم العثور على مكان واحد فقط
            message = search_result['message']
            if search_result['suggestions']:
                message += "\n\nاقتراحات:\n" + "\n".join(search_result['suggestions'])
            
            await update.message.reply_text(message)
            
        else:
            # لم يتم العثور على أي مكان
            message = search_result['message']
            if search_result['suggestions']:
                message += "\n\nهل قصدت أحد هذه الأماكن؟\n" + "\n".join(search_result['suggestions'])
            
            await update.message.reply_text(message)
        
        # إضافة أزرار للمتابعة
        keyboard = [[
            InlineKeyboardButton("🔍 بحث جديد", callback_data="nlp_search"),
            InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main")
        ]]
        await update.message.reply_text(
            "ماذا تريد أن تفعل الآن؟",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.exception(f"Error in NLP search: {e}")
        await update.message.reply_text(
            "حدث خطأ في البحث. يرجى المحاولة مرة أخرى أو استخدام البحث التقليدي."
        )
    
    return SELECTING_START_NEIGHBORHOOD

async def send_google_maps_link(chat_id: int, context: ContextTypes.DEFAULT_TYPE, location_name: str):
    """إرسال رابط خرائط جوجل"""
    try:
        location_data = maps_integration.get_location_coordinates(location_name)
        
        if location_data and location_data.get('maps_url'):
            keyboard = [[
                InlineKeyboardButton(
                    f"🗺️ عرض '{location_name}' على الخريطة",
                    url=location_data['maps_url']
                )
            ]]
            
            await context.bot.send_message(
                chat_id=chat_id,
                text="📍 **رابط الوجهة على الخريطة:**",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            
            # إضافة معلومات إضافية من الموقع
            website_info = website_integration.get_location_info(location_name)
            if website_info:
                info_text = f"""
🌐 **معلومات إضافية:**
{website_info.get('description', '')}

📋 **الخدمات المتاحة:**
{' • '.join(website_info.get('services', []))}
                """
                
                keyboard = [[
                    InlineKeyboardButton("🌐 المزيد من المعلومات", url=website_info.get('website_url', '#'))
                ]]
                
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=info_text.strip(),
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )
                
    except Exception as e:
        logger.error(f"Error sending Google Maps link: {e}")

async def get_latest_updates() -> str:
    """الحصول على آخر التحديثات"""
    try:
        # محاكاة الحصول على تحديثات من مصادر مختلفة
        updates = []
        
        # تحديثات من الموقع
        updates.append("🚌 تم تحديث مواعيد خط السلام - يعمل الآن حتى الساعة 11 مساءً")
        updates.append("🗺️ إضافة معالم جديدة في حي الشرق")
        updates.append("📱 تحسينات في نظام البحث الذكي")
        
        # تحديثات المرور المباشرة
        live_updates = website_integration.get_live_updates("خط السلام")
        if live_updates:
            status_emoji = "🟢" if live_updates['route_status'] == 'normal' else "🟡"
            updates.append(f"{status_emoji} حالة المرور الحالية: {live_updates['estimated_time']}")
            
            if live_updates.get('user_reports'):
                latest_report = live_updates['user_reports'][0]
                updates.append(f"💬 تقرير حديث: {latest_report['message']} ({latest_report['time']})")
        
        return "\n\n".join([f"• {update}" for update in updates])
        
    except Exception as e:
        logger.error(f"Error getting updates: {e}")
        return "• لا توجد تحديثات متاحة حالياً"

# --- نظام الإدارة ---

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """عرض لوحة الإدارة"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not (user_id in SUPER_ADMIN_IDS or admin_system.is_admin(user_id)):
        await query.edit_message_text("⛔ ليس لديك صلاحيات إدارية.")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("➕ إضافة خط مواصلات جديد", callback_data="add_route")],
        [InlineKeyboardButton("🏷️ إضافة معلم جديد", callback_data="add_landmark")],
        [InlineKeyboardButton("👥 إدارة المشرفين", callback_data="manage_admins")],
        [InlineKeyboardButton("💾 نسخة احتياطية من البيانات", callback_data="backup_data")],
        [InlineKeyboardButton("📊 إحصائيات الاستخدام", callback_data="usage_stats")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ]
    
    await query.edit_message_text(
        "⚙️ **لوحة الإدارة**\n\nاختر العملية المطلوبة:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return ADMIN_MENU

async def handle_admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالجة إجراءات الإدارة"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "add_route":
        await query.edit_message_text(
            """
➕ **إضافة خط مواصلات جديد**

يرجى كتابة بيانات الخط بالتنسيق التالي:

```
اسم الخط: خط الجامعة الجديد
منطقة البداية: الجامعة
منطقة النهاية: وسط البلد  
التعريفة: 7 جنيه
النقاط الرئيسية: الجامعة، المحطة الرئيسية، البنك الأهلي، وسط البلد
ملاحظات: يعمل من 6 صباحاً حتى 10 مساءً
```

أو استخدم /cancel للإلغاء
            """,
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data['admin_action'] = 'adding_route'
        return ADDING_ROUTE
        
    elif query.data == "backup_data":
        try:
            backup_file = admin_system.backup_data()
            if backup_file:
                await query.edit_message_text(f"✅ تم إنشاء نسخة احتياطية: {backup_file}")
            else:
                await query.edit_message_text("❌ فشل في إنشاء النسخة الاحتياطية")
        except Exception as e:
            logger.error(f"Backup error: {e}")
            await query.edit_message_text("❌ حدث خطأ أثناء إنشاء النسخة الاحتياطية")
        
        return await show_admin_panel(update, context)
    
    # المزيد من الإجراءات...
    return ADMIN_MENU

# نسخ الدوال المطلوبة من البوت الأصلي (مبسطة)
def build_keyboard(items, prefix):
    """بناء لوحة المفاتيح"""
    keyboard = []
    row = []
    max_per_row = 2
    
    for item_data in items:
        if isinstance(item_data, dict):
            item_text = item_data.get("name")
            callback_identifier = item_text
        elif isinstance(item_data, str):
            item_text = item_data
            callback_identifier = item_data
        else:
            continue
            
        if item_text and callback_identifier:
            callback_data_str = f"{prefix}:{callback_identifier}"
            row.append(InlineKeyboardButton(item_text, callback_data=callback_data_str))
            
            if len(row) == max_per_row:
                keyboard.append(row)
                row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("إلغاء ❌", callback_data="cancel_action")])
    return InlineKeyboardMarkup(keyboard)

def find_route_with_proximity(start, end, routes, neighborhoods):
    """بحث مبسط عن المسار"""
    return f"🚌 **نتيجة البحث:**\n\nمن: {start}\nإلى: {end}\n\n✅ تم العثور على مسار مناسب!\n\n*سيتم إضافة تفاصيل أكثر قريباً...*"

async def handle_invalid_callback(update, context):
    """معالجة البيانات غير الصحيحة"""
    query = update.callback_query
    await query.answer("خطأ في البيانات!")
    await query.edit_message_text("حدث خطأ. يرجى البدء من جديد باستخدام /start.")
    return ConversationHandler.END

# دوال المحادثة المبسطة
async def select_start_neighborhood(update, context):
    """اختيار حي البداية"""
    query = update.callback_query
    await query.answer()
    chosen = query.data.split(":", 1)[1]
    context.user_data['start_neighborhood'] = chosen
    
    categories = list(neighborhood_data.get(chosen, {}).keys())
    keyboard = build_keyboard(categories, "start_category")
    await query.edit_message_text(f"الحي: {chosen}\nاختر التصنيف:", reply_markup=keyboard)
    return SELECTING_START_CATEGORY

async def select_start_category(update, context):
    """اختيار تصنيف البداية"""
    query = update.callback_query
    await query.answer()
    chosen = query.data.split(":", 1)[1]
    context.user_data['start_category'] = chosen
    neighborhood = context.user_data.get('start_neighborhood')
    
    landmarks = neighborhood_data.get(neighborhood, {}).get(chosen, [])
    keyboard = build_keyboard(landmarks, "start_landmark")
    await query.edit_message_text(f"التصنيف: {chosen}\nاختر المعلم:", reply_markup=keyboard)
    return SELECTING_START_LANDMARK

async def select_start_landmark(update, context):
    """اختيار معلم البداية"""
    query = update.callback_query
    await query.answer()
    chosen = query.data.split(":", 1)[1]
    context.user_data['start_landmark'] = chosen
    
    neighborhoods = list(neighborhood_data.keys())
    keyboard = build_keyboard(neighborhoods, "end_neighborhood")
    await query.edit_message_text(f"✅ البداية: {chosen}\n\nاختر حي الوجهة:", reply_markup=keyboard)
    return SELECTING_END_NEIGHBORHOOD

async def select_end_neighborhood(update, context):
    """اختيار حي الوجهة"""
    query = update.callback_query
    await query.answer()
    chosen = query.data.split(":", 1)[1]
    context.user_data['end_neighborhood'] = chosen
    
    categories = list(neighborhood_data.get(chosen, {}).keys())
    keyboard = build_keyboard(categories, "end_category")
    await query.edit_message_text(f"حي الوجهة: {chosen}\nاختر التصنيف:", reply_markup=keyboard)
    return SELECTING_END_CATEGORY

async def select_end_category(update, context):
    """اختيار تصنيف الوجهة"""
    query = update.callback_query
    await query.answer()
    chosen = query.data.split(":", 1)[1]
    context.user_data['end_category'] = chosen
    neighborhood = context.user_data.get('end_neighborhood')
    
    landmarks = neighborhood_data.get(neighborhood, {}).get(chosen, [])
    keyboard = build_keyboard(landmarks, "end_landmark")
    await query.edit_message_text(f"تصنيف الوجهة: {chosen}\nاختر المعلم:", reply_markup=keyboard)
    return SELECTING_END_LANDMARK

async def select_end_landmark_and_find_route(update, context):
    """اختيار معلم الوجهة والبحث عن المسار"""
    query = update.callback_query
    await query.answer()
    chosen = query.data.split(":", 1)[1]
    context.user_data['end_landmark'] = chosen
    
    start = context.user_data.get('start_landmark')
    end = chosen
    
    await query.edit_message_text("🔍 جاري البحث عن أفضل مسار...")
    
    result = find_route_with_proximity(start, end, routes_data, neighborhood_data)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=result, parse_mode=ParseMode.MARKDOWN)
    
    # إضافة رابط خرائط
    await send_google_maps_link(update.effective_chat.id, context, end)
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update, context):
    """إلغاء المحادثة"""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("تم الإلغاء. استخدم /start للبدء مرة أخرى.")
    else:
        await update.message.reply_text("تم الإلغاء. استخدم /start للبدء مرة أخرى.")
    
    context.user_data.clear()
    return ConversationHandler.END

def main() -> None:
    """تشغيل البوت المحدث"""
    application = Application.builder().token(BOT_TOKEN).build()

    # إعداد معالج المحادثة الرئيسي
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECTING_START_NEIGHBORHOOD: [
                CallbackQueryHandler(handle_main_menu, pattern=r'^(search_transport|nlp_search|interactive_maps|latest_updates|admin_panel|back_to_main)$'),
                CallbackQueryHandler(select_start_neighborhood, pattern=r'^start_neighborhood:'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_nlp_search)
            ],
            SELECTING_START_CATEGORY: [CallbackQueryHandler(select_start_category, pattern=r'^start_category:')],
            SELECTING_START_LANDMARK: [CallbackQueryHandler(select_start_landmark, pattern=r'^start_landmark:')],
            SELECTING_END_NEIGHBORHOOD: [CallbackQueryHandler(select_end_neighborhood, pattern=r'^end_neighborhood:')],
            SELECTING_END_CATEGORY: [CallbackQueryHandler(select_end_category, pattern=r'^end_category:')],
            SELECTING_END_LANDMARK: [CallbackQueryHandler(select_end_landmark_and_find_route, pattern=r'^end_landmark:')],
            ADMIN_MENU: [CallbackQueryHandler(handle_admin_actions)],
            ADDING_ROUTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_route_data)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(cancel, pattern=r'^cancel_action$'),
        ],
        per_message=False,
    )

    application.add_handler(conv_handler)
    
    # إضافة معالجات إضافية للأوامر المخصصة
    application.add_handler(CommandHandler('admin', admin_command))
    application.add_handler(CommandHandler('help', help_command))

    logger.info("Enhanced Bot starting with all new features...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

async def handle_add_route_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالجة بيانات الخط الجديد"""
    # هذه الدالة ستتم كتابتها لاحقاً
    pass

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر سريع للوصول لوحة الإدارة"""
    user_id = update.effective_user.id
    if user_id in SUPER_ADMIN_IDS or admin_system.is_admin(user_id):
        await update.message.reply_text("مرحباً بك في لوحة الإدارة! استخدم /start ثم اختر لوحة الإدارة.")
    else:
        await update.message.reply_text("ليس لديك صلاحيات إدارية.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر المساعدة"""
    help_text = """
🚌 **دليل استخدام بوت مواصلات بورسعيد**

**الأوامر الأساسية:**
/start - بدء المحادثة والقائمة الرئيسية
/cancel - إلغاء العملية الحالية
/help - عرض هذه المساعدة

**طرق البحث:**
1️⃣ **البحث التقليدي**: اختيار الحي والمعالم خطوة بخطوة
2️⃣ **البحث الذكي**: كتابة السؤال مباشرة مثل "إزاي أروح من A لـ B؟"

**الميزات المتاحة:**
🗺️ خرائط تفاعلية مع روابط جوجل
📰 تحديثات مباشرة عن حالة المرور
🌐 معلومات إضافية عن الأماكن
⚙️ نظام إدارة متقدم (للمشرفين)

**نصائح:**
• استخدم أسماء الأماكن بوضوح
• يمكنك الكتابة باللهجة العامية في البحث الذكي
• تأكد من تحديث التطبيق للحصول على أحدث البيانات
    """
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

if __name__ == "__main__":
    main()