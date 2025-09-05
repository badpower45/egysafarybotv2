# -*- coding: utf-8 -*-
# bot.py (النسخة النهائية الحالية - تتضمن إصلاحات الواجهة ومنطق القرب)

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ConversationHandler,
    ContextTypes, MessageHandler, filters
)
from telegram.constants import ParseMode

# --- استيراد البيانات والتوكن ---
try:
    from config import BOT_TOKEN
except ImportError:
    print("!!! خطأ فادح: لم يتم العثور على ملف 'config.py' أو متغير 'BOT_TOKEN' بداخله.")
    print("!!! تأكد من إنشاء ملف 'config.py' في نفس المجلد ووضع 'BOT_TOKEN = \"YourToken\"' بداخله.")
    exit()

try:
    # تأكد من أن data.py يحتوي على الهيكل الجديد لـ neighborhood_data
    from data import routes_data, neighborhood_data
except ImportError:
    print("!!! خطأ فادح: لم يتم العثور على ملف 'data.py' أو المتغيرات 'routes_data' و 'neighborhood_data' بداخله.")
    print("!!! تأكد من إنشاء ملف 'data.py' في نفس المجلد ووضع هياكل البيانات الصحيحة فيه (بالهيكل الجديد).")
    exit()
except Exception as e:
    print(f"!!! خطأ فادح أثناء استيراد البيانات من data.py: {e}")
    exit()


# --- إعدادات الـ Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # مستوى DEBUG مفيد أثناء التطوير

# --- تعريف الحالات (States) ---
(SELECTING_START_NEIGHBORHOOD, SELECTING_START_CATEGORY, SELECTING_START_LANDMARK,
 SELECTING_END_NEIGHBORHOOD, SELECTING_END_CATEGORY, SELECTING_END_LANDMARK) = range(6)

# --- الدوال المساعدة ---

def get_landmark_data_from_name(landmark_name: str, neighborhoods_dict: dict) -> dict | None:
    """يبحث عن بيانات معلم معين بالاسم في كل الأحياء والتصنيفات."""
    if not isinstance(landmark_name, str):
        logger.error(f"Invalid type for landmark_name: {type(landmark_name)}")
        return None
    search_name = landmark_name.strip().lower()
    if not search_name:
        logger.warning("Empty landmark name received for search.")
        return None

    logger.debug(f"Searching for landmark exact match (case-insensitive): '{search_name}'")
    for neighborhood, categories in neighborhoods_dict.items():
        if not isinstance(categories, dict): continue # Skip if neighborhood data is not a dict
        for category, landmarks in categories.items():
            if not isinstance(landmarks, list): continue # Skip if category data is not a list

            # Check structure of the first item to determine format
            if landmarks and isinstance(landmarks[0], dict): # New structure {"name": ..., "served_by": ...}
                 for landmark_dict in landmarks:
                      current_name = landmark_dict.get("name")
                      # Ensure current_name is a string before comparing
                      if isinstance(current_name, str) and current_name.strip().lower() == search_name:
                           logger.debug(f"Exact match found: {landmark_dict}")
                           # Return a copy including neighborhood and category
                           return_data = landmark_dict.copy()
                           return_data['neighborhood'] = neighborhood
                           return_data['category'] = category
                           return return_data
            elif landmarks and isinstance(landmarks[0], str): # Old structure [str, str] (Fallback, should not happen with correct data.py)
                logger.warning(f"Category '{category}' in neighborhood '{neighborhood}' seems to use old data structure (list of strings).")
                for item_name in landmarks:
                     if isinstance(item_name, str) and item_name.strip().lower() == search_name:
                          logger.debug(f"Fallback match found for string: {item_name}")
                          # Return basic structure if found in old format list
                          return {"name": landmark_name, "served_by": {}, "neighborhood": neighborhood, "category": category}

    logger.warning(f"Landmark '{landmark_name}' not found in any category/neighborhood.")
    return None

def build_keyboard(items: list, prefix: str) -> InlineKeyboardMarkup:
    """ينشئ لوحة مفاتيح بأزرار. يقبل قائمة نصوص أو قواميس تحتوي على مفتاح 'name'."""
    keyboard = []
    row = []
    max_per_row = 2
    processed_identifiers = set() # To avoid duplicate callback_data if truncation happens

    logger.debug(f"Building keyboard with prefix '{prefix}' for {len(items)} items.")

    if not items:
        logger.warning(f"build_keyboard received empty list for prefix '{prefix}'")
        # Return keyboard with only cancel button? Or empty? Let's add cancel.
        keyboard.append([InlineKeyboardButton("إلغاء ❌", callback_data="cancel_action")])
        return InlineKeyboardMarkup(keyboard)

    for item_data in items:
        item_text = None
        callback_identifier = None # The identifier used in callback_data (should match keys/names)

        if isinstance(item_data, dict):
            item_text = item_data.get("name")
            callback_identifier = item_text # Use the original name from the dict as the identifier
        elif isinstance(item_data, str):
            item_text = item_data
            callback_identifier = item_data # Use the string itself as the identifier
        else:
            logger.warning(f"Skipping unexpected item type in build_keyboard: {type(item_data)}")
            continue

        # Ensure text and identifier are valid strings
        if not isinstance(item_text, str) or not isinstance(callback_identifier, str) or \
           not item_text or not callback_identifier:
            logger.warning(f"Skipping item with invalid text or callback ID: {item_data}")
            continue

        # Construct callback data: prefix + : + identifier
        callback_data_str = f"{prefix}:{callback_identifier}"

        # Check callback_data length ONLY if necessary (max 64 bytes)
        # Truncation can lead to errors if identifiers become non-unique or don't match data keys
        if len(callback_data_str.encode('utf-8')) > 64:
            logger.error(f"Callback data for '{item_text}' is too long ({len(callback_data_str.encode('utf-8'))} bytes)! Data: '{callback_data_str}'. THIS WILL LIKELY CAUSE AN ERROR. Consider shortening names in data.py or using IDs.")
            # Option: skip button, or send truncated (but likely broken) data? Let's skip.
            continue
            # Alternative (Truncation - use with caution):
            # max_len_identifier = 64 - len(prefix.encode('utf-8')) - 1
            # if max_len_identifier < 1: max_len_identifier = 1 # Need at least 1 char
            # callback_identifier_short = callback_identifier.encode('utf-8')[:max_len_identifier].decode('utf-8', 'ignore')
            # callback_data_str = f"{prefix}:{callback_identifier_short}"
            # logger.warning(f"Callback data for '{item_text}' was too long, using truncated ID (might cause error): {callback_identifier_short}")

        # Add button to row
        row.append(InlineKeyboardButton(item_text, callback_data=callback_data_str))
        if len(row) == max_per_row:
            keyboard.append(row)
            row = []
    if row: # Add remaining buttons if any
        keyboard.append(row)

    # Add cancel button in a separate row
    keyboard.append([InlineKeyboardButton("إلغاء ❌", callback_data="cancel_action")])
    return InlineKeyboardMarkup(keyboard)

# --- معالج للـ callback data غير الصحيحة ---
async def handle_invalid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعالج الحالات التي يتم فيها استقبال بيانات callback غير صحيحة."""
    query = update.callback_query
    reply_text = "حدث خطأ في البيانات المستلمة. يرجى البدء من جديد باستخدام /start."
    user_id = update.effective_user.id if update.effective_user else "Unknown"
    if query:
        # Always answer callback query to remove loading state
        try: await query.answer("خطأ!", show_alert=True) # show_alert might be better
        except Exception as e: logger.error(f"Error answering callback query: {e}")

        logger.warning(f"Received invalid/malformed callback_data: {query.data} from user {user_id}")
        try:
            await query.edit_message_text(text=reply_text)
        except Exception as e:
            logger.warning(f"Could not edit message on invalid callback: {e}. Sending new message.")
            try: await context.bot.send_message(chat_id=update.effective_chat.id, text=reply_text)
            except Exception as send_e: logger.error(f"Failed to send fallback message: {send_e}")
    else:
        logger.error("handle_invalid_callback called but update.callback_query is None!")
        if update.effective_chat:
             try: await context.bot.send_message(chat_id=update.effective_chat.id, text=reply_text)
             except Exception as send_e: logger.error(f"Failed to send fallback message: {send_e}")

    context.user_data.clear()
    return ConversationHandler.END

# --- دوال معالجة المحادثة ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_id = user.id if user else "Unknown"
    user_name = user.first_name if user else "User"
    logger.info(f"User {user_name} (ID: {user_id}) started a conversation.")
    context.user_data.clear()
    try:
        neighborhoods = list(neighborhood_data.keys())
        if not neighborhoods:
            logger.error("neighborhood_data is empty or not loaded correctly.")
            await update.message.reply_text("عفواً، لا توجد بيانات أحياء متاحة حالياً. يرجى مراجعة المطور.")
            return ConversationHandler.END

        keyboard = build_keyboard(neighborhoods, "start_neighborhood")
        await update.message.reply_text(
            f"أهلاً بك يا {user_name}! أنا بوت المواصلات.\n\n"
            f"من فضلك اختر **حي البداية**:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN # Ensure Markdown works
        )
        return SELECTING_START_NEIGHBORHOOD
    except Exception as e:
        logger.exception(f"Error in start handler: {e}")
        await update.message.reply_text("حدث خطأ ما، يرجى المحاولة لاحقاً أو الاتصال بالدعم.")
        return ConversationHandler.END


async def select_start_neighborhood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not query.data or ":" not in query.data: return await handle_invalid_callback(update, context)
    try:
        await query.answer()
        chosen_neighborhood = query.data.split(":", 1)[1]

        if chosen_neighborhood not in neighborhood_data:
            logger.error(f"Neighborhood key '{chosen_neighborhood}' from callback NOT FOUND in data.")
            await query.edit_message_text(text=f"خطأ داخلي: لم يتم العثور على بيانات الحي '{chosen_neighborhood}'.")
            context.user_data.clear()
            return ConversationHandler.END

        context.user_data['start_neighborhood'] = chosen_neighborhood
        logger.info(f"User {update.effective_user.first_name} selected start neighborhood: {chosen_neighborhood}")

        categories = list(neighborhood_data.get(chosen_neighborhood, {}).keys())
        if not categories:
            logger.warning(f"No categories found for neighborhood: '{chosen_neighborhood}'. Check data.py.")
            await query.edit_message_text(text=f"عفواً، لا توجد تصنيفات متاحة حالياً لـ '{chosen_neighborhood}'.")
            context.user_data.clear() # End if no categories found
            return ConversationHandler.END

        keyboard = build_keyboard(categories, "start_category")
        await query.edit_message_text(
            text=f"📍 حي البداية: {chosen_neighborhood}\n\n"
                 f"الآن اختر **نوع المكان** الذي تبدأ منه:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return SELECTING_START_CATEGORY
    except Exception as e:
        logger.exception(f"Error in select_start_neighborhood: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="حدث خطأ أثناء معالجة اختيارك. يرجى المحاولة بـ /start.")
        context.user_data.clear()
        return ConversationHandler.END


async def select_start_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not query.data or ":" not in query.data: return await handle_invalid_callback(update, context)

    chosen_category = query.data.split(":", 1)[1]
    context.user_data['start_category'] = chosen_category
    chosen_neighborhood = context.user_data.get('start_neighborhood', 'الحي المختار') # Fallback text
    logger.info(f"User {update.effective_user.first_name} selected start category: {chosen_category} in {chosen_neighborhood}")

    landmarks_data_list = neighborhood_data.get(chosen_neighborhood, {}).get(chosen_category, [])
    if not landmarks_data_list:
        logger.warning(f"No landmarks found for {chosen_neighborhood} -> {chosen_category}")
        await query.edit_message_text(
            text=f"عفواً، لا توجد معالم مدرجة تحت تصنيف '{chosen_category}' في '{chosen_neighborhood}' حالياً."
        )
        # End conversation or allow back? Ending for now.
        context.user_data.clear()
        return ConversationHandler.END

    keyboard = build_keyboard(landmarks_data_list, "start_landmark")
    try:
        await query.edit_message_text(
            text=f"📍 حي البداية: {chosen_neighborhood}\n"
                 f"🏷️ التصنيف: {chosen_category}\n\n"
                 f"الآن اختر **المعلم / المكان المحدد** الذي ستبدأ منه:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return SELECTING_START_LANDMARK
    except Exception as e:
        logger.error(f"Error editing message in select_start_category: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                      text=f"📍 حي البداية: {chosen_neighborhood}\n🏷️ التصنيف: {chosen_category}\n\nالآن اختر **المعلم / المكان المحدد** الذي ستبدأ منه:",
                                      reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        return SELECTING_START_LANDMARK


async def select_start_landmark(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not query.data or ":" not in query.data: return await handle_invalid_callback(update, context)

    chosen_landmark = query.data.split(":", 1)[1]
    context.user_data['start_landmark'] = chosen_landmark
    start_neighborhood = context.user_data.get('start_neighborhood', '')
    logger.info(f"User {update.effective_user.first_name} selected start landmark: {chosen_landmark} in {start_neighborhood}")

    neighborhoods = list(neighborhood_data.keys())
    keyboard = build_keyboard(neighborhoods, "end_neighborhood")
    try:
        await query.edit_message_text(
            text=f"✅ نقطة البداية: **{chosen_landmark}** ({start_neighborhood})\n\n"
                 f"--------------------\n"
                 f"الآن، من فضلك اختر **حي الوجهة**:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return SELECTING_END_NEIGHBORHOOD
    except Exception as e:
         logger.error(f"Error editing message in select_start_landmark: {e}")
         await context.bot.send_message(chat_id=update.effective_chat.id,
                                      text=f"✅ نقطة البداية: **{chosen_landmark}** ({start_neighborhood})\n\n--------------------\nالآن، من فضلك اختر **حي الوجهة**:",
                                      reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
         return SELECTING_END_NEIGHBORHOOD


# --- دوال اختيار الوجهة ---

async def select_end_neighborhood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not query.data or ":" not in query.data: return await handle_invalid_callback(update, context)

    chosen_neighborhood = query.data.split(":", 1)[1]
    if chosen_neighborhood not in neighborhood_data:
        logger.error(f"End Neighborhood key '{chosen_neighborhood}' from callback NOT FOUND.")
        await query.edit_message_text(text=f"خطأ: لم يتم العثور على بيانات للحي '{chosen_neighborhood}'.")
        return ConversationHandler.END
    context.user_data['end_neighborhood'] = chosen_neighborhood
    logger.info(f"User {update.effective_user.first_name} selected end neighborhood: {chosen_neighborhood}")

    categories = list(neighborhood_data.get(chosen_neighborhood, {}).keys())
    if not categories:
        await query.edit_message_text(text=f"عفواً، لا توجد تصنيفات متاحة لـ '{chosen_neighborhood}'.")
        return ConversationHandler.END

    keyboard = build_keyboard(categories, "end_category")
    try:
        await query.edit_message_text(
            text=f"📍 نقطة البداية: {context.user_data.get('start_landmark', '?')} ({context.user_data.get('start_neighborhood', '?')})\n"
                 f"🏁 حي الوجهة: {chosen_neighborhood}\n\n"
                 f"الآن اختر **نوع مكان الوجهة**:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return SELECTING_END_CATEGORY
    except Exception as e:
         logger.error(f"Error editing message in select_end_neighborhood: {e}")
         await context.bot.send_message(chat_id=update.effective_chat.id,
                                      text=f"📍 نقطة البداية: {context.user_data.get('start_landmark', '?')} ({context.user_data.get('start_neighborhood', '?')})\n🏁 حي الوجهة: {chosen_neighborhood}\n\nالآن اختر **نوع مكان الوجهة**:",
                                      reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
         return SELECTING_END_CATEGORY


async def select_end_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not query.data or ":" not in query.data: return await handle_invalid_callback(update, context)

    chosen_category = query.data.split(":", 1)[1]
    context.user_data['end_category'] = chosen_category
    chosen_neighborhood = context.user_data.get('end_neighborhood', 'الحي المختار')
    logger.info(f"User selected end category: {chosen_category} in {chosen_neighborhood}")

    landmarks_data_list = neighborhood_data.get(chosen_neighborhood, {}).get(chosen_category, [])
    if not landmarks_data_list:
        await query.edit_message_text(text=f"عفواً، لا توجد معالم مدرجة تحت تصنيف '{chosen_category}' في '{chosen_neighborhood}' حالياً.")
        return ConversationHandler.END

    keyboard = build_keyboard(landmarks_data_list, "end_landmark")
    try:
        await query.edit_message_text(
            text=f"📍 نقطة البداية: {context.user_data.get('start_landmark', '?')} ({context.user_data.get('start_neighborhood', '?')})\n"
                 f"🏁 حي الوجهة: {chosen_neighborhood}\n"
                 f"🏷️ تصنيف الوجهة: {chosen_category}\n\n"
                 f"الآن اختر **المعلم / المكان المحدد** للوجهة:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return SELECTING_END_LANDMARK
    except Exception as e:
         logger.error(f"Error editing message in select_end_category: {e}")
         await context.bot.send_message(chat_id=update.effective_chat.id,
                                      text=f"📍 نقطة البداية: {context.user_data.get('start_landmark', '?')} ({context.user_data.get('start_neighborhood', '?')})\n🏁 حي الوجهة: {chosen_neighborhood}\n🏷️ تصنيف الوجهة: {chosen_category}\n\nالآن اختر **المعلم / المكان المحدد** للوجهة:",
                                      reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
         return SELECTING_END_LANDMARK


# -*- coding: utf-8 -*-
# bot.py (الدالة المحدثة لربط الخرائط)

import logging
from urllib.parse import quote # <<< تأكد من وجود هذا الاستيراد
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup # <<< تأكد من وجود هذه الاستيرادات
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ConversationHandler,
    ContextTypes, MessageHandler, filters
)
from telegram.constants import ParseMode
# --- استيراد البيانات والتوكن و الدوال المساعدة الأخرى ---
# (احتفظ بباقي استيراداتك هنا)
try:
    from config import BOT_TOKEN
    from data import routes_data, neighborhood_data
    # تأكد من استيراد دوالك المساعدة هنا
    #from helpers import get_landmark_data_from_name, build_keyboard, find_route_with_proximity, handle_invalid_callback # افترض وجودها في helpers.py
except ImportError:
     print("!!! Error importing config/data/helpers.")
     exit()

# ... (احتفظ بإعدادات الـ logger وحالات المحادثة States ودوال المحادثة الأخرى) ...
logger = logging.getLogger(__name__)

# --- الدالة المعدلة: select_end_landmark_and_find_route ---
async def select_end_landmark_and_find_route(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not query.data or ":" not in query.data:
        # Assuming handle_invalid_callback exists and is imported
        return await handle_invalid_callback(update, context)

    chosen_end_landmark = query.data.split(":", 1)[1]
    context.user_data['end_landmark'] = chosen_end_landmark
    logger.info(f"User {update.effective_user.first_name} selected end landmark: {chosen_end_landmark}")

    start_landmark = context.user_data.get('start_landmark')
    end_landmark = context.user_data.get('end_landmark')

    if not start_landmark or not end_landmark:
        try: await query.edit_message_text(text="حدث خطأ، لم يتم تحديد نقطة البداية أو النهاية بشكل صحيح.")
        except Exception as e: logger.warning(f"Failed edit: {e}")
        context.user_data.clear()
        return ConversationHandler.END

    # --- عرض رسالة البحث ---
    try:
        await query.edit_message_text(
            text=f"✅ البداية: **{start_landmark}**\n"
                 f"🏁 الوجهة: **{end_landmark}**\n\n"
                 f"تمام! جاري البحث عن خط المواصلات ورابط الخريطة...",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.warning(f"Failed edit before search message: {e}. Sending new message.")
        try:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="تمام! جاري البحث...")
        except Exception as send_e:
            logger.error(f"Failed to send fallback searching message: {send_e}")

    # --- البحث عن اقتراح الطريق ---
    # Assuming find_route_with_proximity is defined or imported
    route_suggestion = find_route_with_proximity(start_landmark, end_landmark, routes_data, neighborhood_data)

    # --- <<< الكود المحدث: الحصول على رابط خرائط جوجل باستخدام الأداة >>> ---
    destination_map_url = None
    destination_map_name = end_landmark # الاسم الافتراضي
    try:
        logger.info(f"Attempting to get map link for destination: '{end_landmark}' using maps_local.Google Maps")
        query_text = f"{end_landmark}, Port Said"

        # --------------------------------------------------------------------
        # !!! هنا يتم استدعاء الأداة فعلياً !!!
        # --------------------------------------------------------------------
        # Tool Code Simulation Start (Correct tool name in comment)
        # print(maps_local.Google Maps(query=query_text)) # <--- الاستدعاء الفعلي للأداة
        # Tool Code Simulation End

        # --------------------------------------------------------------------
        # !!! هنا يتم معالجة نتيجة الأداة !!!
        # --------------------------------------------------------------------
        places_result = None # <--- استبدل None بنتيجة الأداة الفعلية
        # --- بداية كود معالجة النتيجة ---
        if places_result and hasattr(places_result, 'places') and places_result.places:
            first_place = places_result.places[0]
            place_name_found = getattr(first_place, 'name', end_landmark)
            place_map_url = getattr(first_place, 'map_url', None)

            if place_map_url:
                 destination_map_url = place_map_url
                 destination_map_name = place_name_found
                 logger.info(f"Map link found: {destination_map_url}")
            else:
                 logger.warning(f"Tool found place '{place_name_found}' but no map_url.")
                 # استخدم رابط البحث العام كبديل (تم تصحيح الرابط)
                 destination_map_url = f"https://maps.google.com/?cid=92316089597044274817{quote(query_text)}" # <<< الرابط المصحح
                 destination_map_name = end_landmark
                 logger.info(f"Using generic search URL as fallback (map_url missing): {destination_map_url}")
        else:
            logger.warning(f"Could not find place or map link for '{end_landmark}' using tool.")
            # استخدم رابط البحث العام كبديل (تم تصحيح الرابط)
            destination_map_url = f"https://maps.google.com/?cid=92316089597044274818{quote(query_text)}" # <<< الرابط المصحح
            destination_map_name = end_landmark
            logger.info(f"Using generic search URL as fallback (place not found): {destination_map_url}")
        # --- نهاية كود معالجة النتيجة ---

    except Exception as e:
        logger.error(f"Error during map link retrieval or processing for '{end_landmark}': {e}")
        destination_map_url = None
        destination_map_name = end_landmark

    # --- إرسال النتائج للمستخدم ---
    await context.bot.send_message(chat_id=update.effective_chat.id, text=route_suggestion, parse_mode='Markdown')

    if destination_map_url:
        try:
            keyboard = [[InlineKeyboardButton(f"🗺️ عرض موقع '{destination_map_name}' على الخريطة", url=destination_map_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(chat_id=update.effective_chat.id, text="📍 رابط الوجهة:", reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Error sending map link button: {e}")
            try:
                await context.bot.send_message(chat_id=update.effective_chat.id,
                                               text=f"🗺️ رابط موقع '{destination_map_name}' على الخريطة:\n{destination_map_url}",
                                               parse_mode='Markdown',
                                               disable_web_page_preview=True)
            except Exception as send_text_e:
                 logger.error(f"Failed to send map link as text: {send_text_e}")
    else:
        pass # لا ترسل شيئاً إذا لم يكن هناك رابط

    # --- إنهاء المحادثة ---
    context.user_data.clear()
    return ConversationHandler.END

# --- (احتفظ بباقي الكود: main, باقي الدوال المعالجة, etc.) ---

# --- ### دالة البحث عن الطريق باستخدام بيانات القرب ### ---
def find_route_with_proximity(start_landmark_name, end_landmark_name, available_routes, neighborhoods):
    """
    Finds direct routes using proximity data.
    """
    logger.info(f"Smart search started for: '{start_landmark_name}' -> '{end_landmark_name}'")
    possible_routes_details = []

    if not isinstance(start_landmark_name, str) or not isinstance(end_landmark_name, str):
         logger.error(f"Invalid landmark names received: Start={type(start_landmark_name)}, End={type(end_landmark_name)}")
         return "❌ خطأ في بيانات البحث."

    if start_landmark_name.strip().lower() == end_landmark_name.strip().lower():
        return f"✅ أنت بالفعل في وجهتك أو قريب جداً منها: **'{start_landmark_name}'**!"

    logger.debug(f"Looking up START landmark: '{start_landmark_name}'")
    start_data = get_landmark_data_from_name(start_landmark_name, neighborhoods)
    logger.debug(f"Looking up END landmark: '{end_landmark_name}'")
    end_data = get_landmark_data_from_name(end_landmark_name, neighborhoods)

    if not start_data:
        logger.warning(f"Could not find start landmark data for '{start_landmark_name}'.")
        return f"❌ عذراً، لم أتمكن من العثور على بيانات لنقطة البداية '{start_landmark_name}'."
    if not end_data:
        logger.warning(f"Could not find end landmark data for '{end_landmark_name}'.")
        return f"❌ عذراً، لم أتمكن من العثور على بيانات لنقطة النهاية '{end_landmark_name}'."

    start_served_by = start_data.get("served_by", {}) if isinstance(start_data, dict) else {}
    end_served_by = end_data.get("served_by", {}) if isinstance(end_data, dict) else {}
    logger.debug(f"START ('{start_landmark_name}') served_by: {start_served_by}")
    logger.debug(f"END ('{end_landmark_name}') served_by: {end_served_by}")

    if not start_served_by: logger.warning(f"Start landmark '{start_landmark_name}' has empty/invalid 'served_by' data: {start_served_by}")
    if not end_served_by: logger.warning(f"End landmark '{end_landmark_name}' has empty/invalid 'served_by' data: {end_served_by}")


    acceptable_proximity = ["قريبة جدا", "متوسطة"]
    common_routes_found = []
    logger.debug(f"Acceptable proximity levels: {acceptable_proximity}")
    logger.debug(f"Checking routes listed in START served_by keys: {list(start_served_by.keys())}")

    for route_name_base, start_info in start_served_by.items():
        # Skip if route_name_base itself is not a valid route (e.g., if served_by wasn't properly structured)
        if not isinstance(start_info, dict): continue
        logger.debug(f"Processing potential base route: '{route_name_base}'")

        if route_name_base in end_served_by:
            end_info = end_served_by[route_name_base]
            if not isinstance(end_info, dict): continue

            logger.debug(f"... Route '{route_name_base}' found in END served_by.")
            start_prox = start_info.get("proximity")
            end_prox = end_info.get("proximity")
            logger.debug(f"... Route '{route_name_base}': Start prox='{start_prox}', End prox='{end_prox}'")

            is_start_prox_acceptable = start_prox in acceptable_proximity
            is_end_prox_acceptable = end_prox in acceptable_proximity
            logger.debug(f"... Proximity check: Start acceptable={is_start_prox_acceptable}, End acceptable={is_end_prox_acceptable}")

            if is_start_prox_acceptable and is_end_prox_acceptable:
                logger.debug(f"... Proximity ACCEPTABLE for '{route_name_base}'. Checking direction...")

                start_nearest_stop = start_info.get("nearest_stop")
                end_nearest_stop = end_info.get("nearest_stop")
                logger.debug(f"... Nearest stops from data: Start='{start_nearest_stop}', End='{end_nearest_stop}'")

                if not start_nearest_stop or not end_nearest_stop:
                    logger.warning(f"... Missing nearest_stop data for route '{route_name_base}'. Cannot check direction.")
                    continue

                # Find ALL actual route variants in routes_data that contain the base name
                matching_variants = [r for r in available_routes if isinstance(r.get("routeName"), str) and route_name_base in r.get("routeName")]
                if not matching_variants:
                     logger.warning(f"... No route definitions found in routes_data for base name '{route_name_base}'.")
                     continue

                variant_found_valid_sequence = False
                for route_definition in matching_variants:
                     actual_route_name = route_definition.get("routeName")
                     key_points = route_definition.get("keyPoints")
                     if not key_points or not isinstance(key_points, list):
                         logger.warning(f"   ... Route variant '{actual_route_name}' has invalid keyPoints.")
                         continue

                     # Find indices of the NEAREST STOPS (case-insensitive, whitespace-insensitive)
                     start_stop_search = start_nearest_stop.strip().lower()
                     end_stop_search = end_nearest_stop.strip().lower()
                     start_indices = [i for i, point in enumerate(key_points) if isinstance(point, str) and start_stop_search in point.strip().lower()]
                     end_indices = [i for i, point in enumerate(key_points) if isinstance(point, str) and end_stop_search in point.strip().lower()]
                     logger.debug(f"   ... Checking variant '{actual_route_name}': Start Stop '{start_nearest_stop}' indices={start_indices}, End Stop '{end_nearest_stop}' indices={end_indices}")

                     if not start_indices: logger.warning(f"   ... Nearest start stop '{start_nearest_stop}' NOT found in keyPoints of '{actual_route_name}'.")
                     if not end_indices: logger.warning(f"   ... Nearest end stop '{end_nearest_stop}' NOT found in keyPoints of '{actual_route_name}'.")

                     if start_indices and end_indices:
                         if any(s_idx < e_idx for s_idx in start_indices for e_idx in end_indices):
                             logger.info(f"   ... VALID sequence found for route variant '{actual_route_name}'.")
                             common_routes_found.append({
                                 "routeName": actual_route_name,
                                 "start_landmark_name": start_landmark_name,
                                 "end_landmark_name": end_landmark_name,
                                 "start_proximity": start_prox,
                                 "end_proximity": end_prox,
                                 "start_nearest_stop": start_nearest_stop,
                                 "end_nearest_stop": end_nearest_stop,
                                 "fare": route_definition.get('fare', 'غير محددة'),
                                 "notes": route_definition.get('notes', '')
                             })
                             variant_found_valid_sequence = True
                             # Don't break, allow finding multiple variants (e.g., inner/outer return)
                         # else: logger.debug(f"   ... Invalid sequence for route variant '{actual_route_name}'.")

                if not variant_found_valid_sequence:
                     logger.warning(f"... Base route '{route_name_base}' had acceptable proximity, but NO variant had correct stop sequence.")

            else: logger.debug(f"... Proximity NOT acceptable for '{route_name_base}'. Skipping.")
        # else: logger.debug(f"... Route '{route_name_base}' (from start) not found in END served_by.")


    logger.debug(f"Finished checking direct routes. Found {len(common_routes_found)} options.")

    # --- Format results ---
    if common_routes_found:
         possible_routes_details = []
         for route_info in common_routes_found:
              suggestion = f"✅ خط مباشر مقترح: **'{route_info['routeName']}'**"
              suggestion += f"\n  - للركوب: اذهب إلى **'{route_info['start_nearest_stop']}'** (يعتبر '{route_info['start_proximity']}' من '{route_info['start_landmark_name']}')."
              suggestion += f"\n  - النزول: انزل عند **'{route_info['end_nearest_stop']}'**."
              if route_info['end_proximity'] == "قريبة جدا":
                   suggestion += f"\n  - وجهتك **'{route_info['end_landmark_name']}'** ستكون قريبة جداً من مكان نزولك."
              elif route_info['end_proximity'] == "متوسطة":
                    suggestion += f"\n  - وجهتك **'{route_info['end_landmark_name']}'** ستكون على مسافة '{route_info['end_proximity']}' من مكان نزولك (قد تحتاج لمشي بسيط)."
              suggestion += f"\n  - الأجرة التقريبية: {route_info['fare']}"
              if route_info['notes']:
                   suggestion += f"\n  - ملاحظات: {route_info['notes']}"
              possible_routes_details.append(suggestion)

         final_reply = f"تم العثور على الخيارات التالية:\n\n"
         final_reply += "\n\n---\n\n".join(possible_routes_details)
         final_reply += "\n\n**ملاحظة:** دقة أماكن الركوب/النزول والقرب تعتمد على البيانات التي أدخلناها. يمكنك دائماً سؤال السائق للتأكيد."
         return final_reply

    # --- No direct routes found ---
    logger.warning(f"FINAL VERDICT: No direct routes found after proximity/sequence checks for '{start_landmark_name}' -> '{end_landmark_name}'.")
    # (Future: Add transfer logic here)
    reason = "لعدم وجود خط مباشر يخدم المكانين معاً بدرجة قرب مقبولة وبالترتيب الصحيح حسب البيانات الحالية."
    return f"❌ عذراً، لم أجد مساراً مباشراً حالياً.\n{reason}\nقد تحتاج لخط آخر أو تبديل مواصلات (سيتم إضافة هذه الخيارات لاحقاً)."

# --- دالة الإلغاء cancel ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_first_name = update.effective_user.first_name if update.effective_user else "المستخدم"
    logger.info(f"User {user_first_name} canceled the conversation.")
    reply_text = "تم إلغاء العملية الحالية. يمكنك البدء من جديد باستخدام /start."

    query = update.callback_query
    if query: # Check if cancel originated from a button press
        # Handle specific cancel button callback_data
        if query.data == "cancel_action":
            await query.answer()
            try:
                await query.edit_message_text(text=reply_text)
            except Exception as e:
                logger.warning(f"Could not edit message on cancel callback: {e}. Sending new message instead.")
                await context.bot.send_message(chat_id=update.effective_chat.id, text=reply_text)
        else:
             # If it's another callback query leading to cancel (e.g., an error state redirecting)
             await query.answer() # Answer blankly? Or show alert?
             await context.bot.send_message(chat_id=update.effective_chat.id, text=reply_text) # Send confirmation

    elif update.message: # Handle /cancel command typed by user
        await update.message.reply_text(reply_text)

    context.user_data.clear()
    return ConversationHandler.END

# --- دالة لمعالجة النصوص غير المتوقعة (اختياري) ---
async def handle_unexpected_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
     # Check if user has conversation data, implying they are mid-conversation
     if context.user_data:
          logger.info(f"Unexpected text from {update.effective_user.first_name} during conversation: {update.message.text}")
          await update.message.reply_text("من فضلك استخدم الأزرار للاختيار، أو استخدم /cancel للإلغاء.")
     # Do nothing if text is outside the conversation flow

# --- الدالة الرئيسية main ---
def main() -> None:
    """يشغل البوت."""
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECTING_START_NEIGHBORHOOD: [CallbackQueryHandler(select_start_neighborhood, pattern=r'^start_neighborhood:')],
            SELECTING_START_CATEGORY: [CallbackQueryHandler(select_start_category, pattern=r'^start_category:')],
            SELECTING_START_LANDMARK: [CallbackQueryHandler(select_start_landmark, pattern=r'^start_landmark:')],
            SELECTING_END_NEIGHBORHOOD: [CallbackQueryHandler(select_end_neighborhood, pattern=r'^end_neighborhood:')],
            SELECTING_END_CATEGORY: [CallbackQueryHandler(select_end_category, pattern=r'^end_category:')],
            SELECTING_END_LANDMARK: [CallbackQueryHandler(select_end_landmark_and_find_route, pattern=r'^end_landmark:')],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(cancel, pattern=r'^cancel_action$'), # Handle cancel button
            # Optional: Catch unexpected text messages during conversation states
            # MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unexpected_text)
            ],
        per_message=False,
    )

    application.add_handler(conv_handler)

    # Optional: Add handler for any text message outside the conversation
    # application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_outside_conversation))

    logger.info("Bot starting with PROXIMITY-AWARE route logic...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()