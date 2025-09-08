# -*- coding: utf-8 -*- 
# final_enhanced_bot.py - بوت مواصلات بورسعيد المطور النهائي مع جميع الميزات

import sys
import os
import logging
import json
from enum import Enum, auto
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote
import requests
from difflib import SequenceMatcher

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ConversationHandler,
    ContextTypes, MessageHandler, filters
)
from telegram.constants import ParseMode

# --- Fix for imports when running from a different directory ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# --- إعدادات الـ Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- استيراد البيانات والتوكن ---
try:
    from config import BOT_TOKEN
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_ACTUAL_BOT_TOKEN_HERE":
        logger.error("BOT_TOKEN not properly configured in config.py")
        raise ValueError("BOT_TOKEN is not configured properly")
except ImportError:
    logger.error("!!! خطأ فادح: لم يتم العثور على ملف 'config.py' أو متغير 'BOT_TOKEN' بداخله.")
    logger.error("!!! تأكد من إنشاء ملف 'config.py' في نفس المجلد ووضع 'BOT_TOKEN = \"YourToken\"' بداخله.")
    exit(1)
except ValueError as e:
    logger.error(f"!!! خطأ في إعداد التوكن: {e}")
    exit(1)

try:
    from data import routes_data, neighborhood_data
    
    if not routes_data or not isinstance(routes_data, list):
        logger.error("routes_data is empty or not a list")
        raise ValueError("Invalid routes_data")
    
    if not neighborhood_data or not isinstance(neighborhood_data, dict):
        logger.error("neighborhood_data is empty or not a dict")
        raise ValueError("Invalid neighborhood_data")
        
    logger.info(f"Successfully loaded {len(routes_data)} routes and {len(neighborhood_data)} neighborhoods")
    
except ImportError as e:
    logger.error(f"!!! خطأ فادح: لم يتم العثور على ملفات البيانات: {e}")
    exit(1)
except Exception as e:
    logger.error(f"!!! خطأ فادح أثناء استيراد البيانات: {e}")
    exit(1)

# --- تعريف الحالات (States) باستخدام Enum ---
class States(Enum):
    # الحالات الأساسية
    MAIN_MENU = auto()
    SELECTING_START_NEIGHBORHOOD = auto()
    SELECTING_START_CATEGORY = auto()
    SELECTING_START_LANDMARK = auto()
    SELECTING_END_NEIGHBORHOOD = auto()
    SELECTING_END_CATEGORY = auto()
    SELECTING_END_LANDMARK = auto()
    
    # حالات البحث الذكي
    NLP_SEARCH_MODE = auto()
    
    # حالات الإدارة
    ADMIN_MENU = auto()
    ADMIN_ADD_ROUTE = auto()
    ADMIN_ADD_LANDMARK = auto()
    ADMIN_MANAGE_REPORTS = auto()
    
    # حالات التقارير
    REPORTING_MODE = auto()
    REPORT_TYPE_SELECTION = auto()

# --- ملفات البيانات الديناميكية ---
ADMIN_IDS_FILE = "admin_ids.json"
REPORTS_FILE = "realtime_reports.json"
GEOCACHE_FILE = "geocache.json"

# --- معرفات المشرفين الأساسيين ---
SUPER_ADMIN_IDS = [1194413075]  # ضع معرفك هنا

# ===== نظام الإدارة =====

class AdminSystem:
    def __init__(self):
        self.admin_ids = self.load_admin_ids()
    
    def load_admin_ids(self) -> List[int]:
        """تحميل قائمة معرفات المشرفين"""
        try:
            if os.path.exists(ADMIN_IDS_FILE):
                with open(ADMIN_IDS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('admin_ids', [])
            return []
        except Exception as e:
            logger.error(f"خطأ في تحميل معرفات المشرفين: {e}")
            return []
    
    def save_admin_ids(self):
        """حفظ قائمة معرفات المشرفين"""
        try:
            with open(ADMIN_IDS_FILE, 'w', encoding='utf-8') as f:
                json.dump({'admin_ids': self.admin_ids}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"خطأ في حفظ معرفات المشرفين: {e}")
    
    def is_admin(self, user_id: int) -> bool:
        """التحقق من صلاحيات المشرف"""
        return user_id in self.admin_ids or user_id in SUPER_ADMIN_IDS
    
    def add_admin(self, user_id: int) -> bool:
        """إضافة مشرف جديد"""
        if user_id not in self.admin_ids:
            self.admin_ids.append(user_id)
            self.save_admin_ids()
            return True
        return False

admin_system = AdminSystem()

# ===== نظام التقارير المباشرة =====

class RealtimeReportsSystem:
    def __init__(self):
        self.reports = self.load_reports()
    
    def load_reports(self) -> List[Dict]:
        """تحميل التقارير المحفوظة"""
        try:
            if os.path.exists(REPORTS_FILE):
                with open(REPORTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"خطأ في تحميل التقارير: {e}")
            return []
    
    def save_reports(self):
        """حفظ التقارير"""
        try:
            with open(REPORTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.reports, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"خطأ في حفظ التقارير: {e}")
    
    def add_report(self, user_id: int, route_name: str, report_type: str, description: str):
        """إضافة تقرير جديد"""
        report = {
            'id': len(self.reports) + 1,
            'user_id': user_id,
            'route_name': route_name,
            'report_type': report_type,  # congestion, delay, detour, normal
            'description': description,
            'timestamp': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(hours=2)).isoformat(),
            'verified': False,
            'votes': 0
        }
        self.reports.append(report)
        self.save_reports()
        return report
    
    def get_active_reports(self) -> List[Dict]:
        """الحصول على التقارير النشطة"""
        now = datetime.now()
        active = []
        for report in self.reports:
            expires_at = datetime.fromisoformat(report['expires_at'])
            if expires_at > now:
                active.append(report)
        return active
    
    def get_reports_for_route(self, route_name: str) -> List[Dict]:
        """الحصول على تقارير خط معين"""
        return [r for r in self.get_active_reports() if r['route_name'] == route_name]

reports_system = RealtimeReportsSystem()

# ===== نظام الجيوكود والخرائط =====

class GeocodingSystem:
    def __init__(self):
        self.cache = self.load_geocache()
    
    def load_geocache(self) -> Dict:
        """تحميل كاش الإحداثيات"""
        try:
            if os.path.exists(GEOCACHE_FILE):
                with open(GEOCACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"خطأ في تحميل الجيوكاش: {e}")
            return {}
    
    def save_geocache(self):
        """حفظ كاش الإحداثيات"""
        try:
            with open(GEOCACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"خطأ في حفظ الجيوكاش: {e}")
    
    def get_coordinates(self, place_name: str) -> Optional[Tuple[float, float]]:
        """الحصول على إحداثيات مكان معين"""
        # البحث في الكاش أولاً
        if place_name in self.cache:
            cached = self.cache[place_name]
            return cached['lat'], cached['lng']
        
        # محاولة الجيوكود باستخدام Nominatim
        try:
            query = f"{place_name}, Port Said, Egypt"
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': query,
                'format': 'json',
                'limit': 1
            }
            headers = {'User-Agent': 'PortSaid-Transport-Bot/1.0'}
            
            response = requests.get(url, params=params, headers=headers, timeout=5)
            data = response.json()
            
            if data:
                lat = float(data[0]['lat'])
                lng = float(data[0]['lon'])
                
                # حفظ في الكاش
                self.cache[place_name] = {
                    'lat': lat,
                    'lng': lng,
                    'fetched_at': datetime.now().isoformat()
                }
                self.save_geocache()
                
                return lat, lng
        except Exception as e:
            logger.error(f"خطأ في الجيوكود لـ {place_name}: {e}")
        
        return None
    
    def get_maps_url(self, place_name: str) -> str:
        """الحصول على رابط الخريطة"""
        coordinates = self.get_coordinates(place_name)
        if coordinates:
            lat, lng = coordinates
            return f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
        else:
            # رابط بحث عام
            encoded_query = quote(f"{place_name} Port Said Egypt")
            return f"https://www.google.com/maps/search/{encoded_query}"

geocoding_system = GeocodingSystem()

# ===== نظام معالجة اللغة الطبيعية =====

class NLPSearchSystem:
    def __init__(self):
        self.landmarks_index = self._build_landmarks_index()
        
        # كلمات ربط عربية
        self.from_keywords = ['من', 'من عند', 'بدءاً من', 'انطلاقاً من']
        self.to_keywords = ['إلى', 'الى', 'لـ', 'ل', 'حتى', 'وصولاً إلى', 'باتجاه']
        self.question_keywords = ['إزاي', 'ازاي', 'كيف', 'طريقة', 'أروح', 'اروح', 'أوصل', 'اوصل']
    
    def _build_landmarks_index(self) -> Dict[str, Dict]:
        """بناء فهرس لجميع المعالم للبحث السريع"""
        index = {}
        for neighborhood, categories in neighborhood_data.items():
            for category, landmarks in categories.items():
                for landmark in landmarks:
                    if isinstance(landmark, dict):
                        name = landmark.get('name', '').lower()
                        index[name] = {
                            'neighborhood': neighborhood,
                            'category': category,
                            'original_name': landmark.get('name', '')
                        }
                    elif isinstance(landmark, str):
                        name = landmark.lower()
                        index[name] = {
                            'neighborhood': neighborhood,
                            'category': category,
                            'original_name': landmark
                        }
        return index
    
    def similarity_score(self, text1: str, text2: str) -> float:
        """حساب درجة التشابه بين نصين"""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def find_best_match(self, query: str, min_score: float = 0.6) -> Optional[Dict]:
        """البحث عن أفضل تطابق لمعلم معين"""
        query = query.lower().strip()
        best_match = None
        best_score = min_score
        
        for landmark_name, landmark_info in self.landmarks_index.items():
            score = self.similarity_score(query, landmark_name)
            if score > best_score:
                best_score = score
                best_match = {
                    'name': landmark_info['original_name'],
                    'score': score,
                    'info': landmark_info
                }
        
        return best_match
    
    def extract_locations_from_text(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """استخراج نقطتي البداية والوجهة من النص"""
        text = text.replace('؟', '').replace('?', '').strip()
        
        # البحث عن أنماط "من X إلى Y"
        for from_word in self.from_keywords:
            for to_word in self.to_keywords:
                if from_word in text and to_word in text:
                    parts = text.split(from_word, 1)
                    if len(parts) > 1:
                        remaining = parts[1].split(to_word, 1)
                        if len(remaining) > 1:
                            start_location = remaining[0].strip()
                            end_location = remaining[1].strip()
                            return start_location, end_location
        
        # البحث عن أنماط "إزاي أروح X"
        for q_word in self.question_keywords:
            if q_word in text:
                parts = text.split(q_word, 1)
                if len(parts) > 1:
                    remaining_text = parts[1].strip()
                    # إزالة كلمات إضافية
                    for remove_word in ['أروح', 'اروح', 'أوصل', 'اوصل']:
                        remaining_text = remaining_text.replace(remove_word, '').strip()
                    if remaining_text:
                        return None, remaining_text  # الوجهة فقط
        
        return None, None
    
    def search_route_from_text(self, text: str) -> Dict:
        """البحث عن مسار من النص المكتوب"""
        start_text, end_text = self.extract_locations_from_text(text)
        
        result = {
            'status': 'error',
            'message': 'لم أتمكن من فهم طلبك. يرجى المحاولة مرة أخرى.',
            'start_location': None,
            'end_location': None,
            'suggestions': []
        }
        
        if start_text:
            start_match = self.find_best_match(start_text)
            if start_match:
                result['start_location'] = start_match
        
        if end_text:
            end_match = self.find_best_match(end_text)
            if end_match:
                result['end_location'] = end_match
        
        # تحديد حالة النتيجة
        if result['start_location'] and result['end_location']:
            result['status'] = 'full_match'
            result['message'] = f"✅ تم العثور على: {result['start_location']['name']} → {result['end_location']['name']}"
        elif result['start_location']:
            result['status'] = 'partial_match'
            result['message'] = f"تم العثور على نقطة البداية: {result['start_location']['name']}. من فضلك حدد الوجهة."
        elif result['end_location']:
            result['status'] = 'partial_match'
            result['message'] = f"تم العثور على الوجهة: {result['end_location']['name']}. من فضلك حدد نقطة البداية."
        
        return result

nlp_system = NLPSearchSystem()

# ===== الدوال المساعدة =====

def build_keyboard(items: List, prefix: str, back_target: Optional[str] = None) -> InlineKeyboardMarkup:
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
            # تقصير البيانات لتجنب خطأ Telegram
            callback_identifier = callback_identifier[:30] if len(callback_identifier) > 30 else callback_identifier
            callback_data_str = f"{prefix}:{callback_identifier}"
            
            # التأكد من أن البيانات لا تتجاوز 64 بايت
            if len(callback_data_str.encode('utf-8')) <= 64:
                row.append(InlineKeyboardButton(item_text, callback_data=callback_data_str))
                
                if len(row) == max_per_row:
                    keyboard.append(row)
                    row = []
    
    if row:
        keyboard.append(row)
    
    # إضافة أزرار التنقل
    nav_buttons = []
    if back_target:
        nav_buttons.append(InlineKeyboardButton("⬅️ رجوع", callback_data=f"back_to_{back_target}"))
    nav_buttons.append(InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"))
    nav_buttons.append(InlineKeyboardButton("❌ إلغاء", callback_data="cancel_action"))
    
    keyboard.append(nav_buttons)
    return InlineKeyboardMarkup(keyboard)

def find_route_logic(start_landmark: str, end_landmark: str, routes: List[Dict]) -> str:
    """البحث عن أفضل مسار بين معلمين - محسن"""
    
    # البحث عن المسارات المباشرة
    direct_routes = []
    for route in routes:
        key_points = route.get('keyPoints', [])
        if not key_points:
            continue
            
        # البحث عن النقاط في المسار
        start_indices = [i for i, point in enumerate(key_points) 
                        if isinstance(point, str) and start_landmark.lower() in point.lower()]
        end_indices = [i for i, point in enumerate(key_points) 
                      if isinstance(point, str) and end_landmark.lower() in point.lower()]
        
        if start_indices and end_indices:
            # التحقق من الترتيب الصحيح
            if any(s_idx < e_idx for s_idx in start_indices for e_idx in end_indices):
                direct_routes.append(route)
    
    if direct_routes:
        result = "🚌 **تم العثور على مسارات مباشرة:**\n\n"
        for i, route in enumerate(direct_routes, 1):
            result += f"{i}. **{route.get('routeName', 'خط غير محدد')}**\n"
            result += f"   💰 التعريفة: {route.get('fare', 'غير محددة')}\n"
            if route.get('notes'):
                result += f"   📝 ملاحظات: {route.get('notes')}\n"
            result += "\n"
        
        # إضافة تقارير الوقت الحقيقي
        for route in direct_routes[:1]:  # للمسار الأول فقط
            route_reports = reports_system.get_reports_for_route(route.get('routeName', ''))
            if route_reports:
                result += "📡 **تقارير مباشرة:**\n"
                for report in route_reports[-2:]:  # آخر تقريرين
                    emoji = "🔴" if report['report_type'] == 'congestion' else "🟡" if report['report_type'] == 'delay' else "🟢"
                    result += f"{emoji} {report['description']} ({report['timestamp'][:16]})\n"
                result += "\n"
        
        return result
    else:
        return f"❌ **عذراً، لم أجد مساراً مباشراً بين {start_landmark} و {end_landmark}**\n\nقد تحتاج إلى:\n• استخدام أكثر من خط\n• البحث عن معالم قريبة\n• التأكد من صحة أسماء الأماكن"

# ===== معالجات الأحداث =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    """بداية المحادثة مع القائمة الرئيسية المطورة"""
    user = update.effective_user
    user_name = user.first_name if user else "مستخدم"
    logger.info(f"User {user_name} (ID: {user.id}) started conversation.")
    
    context.user_data.clear()
    
    # بناء لوحة المفاتيح الرئيسية
    keyboard = [
        [InlineKeyboardButton("🚌 البحث التقليدي", callback_data="traditional_search")],
        [InlineKeyboardButton("🔍 البحث الذكي (اكتب سؤالك)", callback_data="nlp_search")],
        [InlineKeyboardButton("🗺️ عرض الخرائط", callback_data="maps_view")],
        [InlineKeyboardButton("📊 تقارير المرور المباشرة", callback_data="live_reports")],
        [InlineKeyboardButton("📝 أبلغ عن حالة مرور", callback_data="submit_report")]
    ]
    
    # إضافة أزرار الإدارة للمشرفين
    if admin_system.is_admin(user.id):
        keyboard.append([InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""
🚌 **أهلاً بك يا {user_name} في بوت مواصلات بورسعيد المطور!**

الميزات الجديدة:
🔸 بحث ذكي بالنص الحر ("إزاي أروح من A لـ B؟")
🔸 تقارير مرور مباشرة من المستخدمين
🔸 خرائط تفاعلية مع إحداثيات دقيقة
🔸 نظام إدارة متقدم للمشرفين

اختر ما تريد:
    """
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    return States.MAIN_MENU

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    """معالجة اختيارات القائمة الرئيسية"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "traditional_search":
        # البحث التقليدي
        neighborhoods = list(neighborhood_data.keys())
        keyboard = build_keyboard(neighborhoods, "start_neighborhood")
        await query.edit_message_text(
            "🏘️ **اختر حي البداية:**",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return States.SELECTING_START_NEIGHBORHOOD
    
    elif query.data == "nlp_search":
        # البحث الذكي
        await query.edit_message_text(
            """
🔍 **البحث الذكي**

اكتب سؤالك بحرية، مثل:
• "إزاي أروح من سوبر ماركت بكير للمستشفى العام؟"
• "من الجامعة للمحطة"
• "طريقة الوصول لمول داونتاون من البنك الأهلي"

📝 اكتب سؤالك الآن:
            """,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")
            ]]),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data['mode'] = 'nlp_search'
        return States.NLP_SEARCH_MODE
    
    elif query.data == "live_reports":
        # عرض التقارير المباشرة
        active_reports = reports_system.get_active_reports()
        if active_reports:
            reports_text = "📊 **تقارير المرور المباشرة:**\n\n"
            for report in active_reports[-5:]:  # آخر 5 تقارير
                emoji = "🔴" if report['report_type'] == 'congestion' else "🟡" if report['report_type'] == 'delay' else "🟢"
                time_str = report['timestamp'][11:16]  # HH:MM
                reports_text += f"{emoji} **{report['route_name']}** ({time_str})\n{report['description']}\n\n"
        else:
            reports_text = "📊 **لا توجد تقارير مباشرة حالياً**\n\nكن أول من يشارك تقرير عن حالة المرور!"
        
        await query.edit_message_text(
            reports_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 تحديث", callback_data="live_reports")],
                [InlineKeyboardButton("📝 أضف تقرير", callback_data="submit_report")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ]),
            parse_mode=ParseMode.MARKDOWN
        )
        return States.MAIN_MENU
    
    elif query.data == "submit_report":
        # إرسال تقرير جديد
        await query.edit_message_text(
            """
📝 **إرسال تقرير مرور**

اختر نوع التقرير:
            """,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔴 ازدحام شديد", callback_data="report_congestion")],
                [InlineKeyboardButton("🟡 تأخير في المواعيد", callback_data="report_delay")],
                [InlineKeyboardButton("🔄 تغيير مسار", callback_data="report_detour")],
                [InlineKeyboardButton("🟢 الوضع طبيعي", callback_data="report_normal")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ]),
            parse_mode=ParseMode.MARKDOWN
        )
        return States.REPORT_TYPE_SELECTION
    
    elif query.data == "maps_view":
        # عرض الخرائط
        await query.edit_message_text(
            """
🗺️ **الخرائط التفاعلية**

للحصول على خريطة تفاعلية لمكان معين:
1. ابحث عن مسار أولاً
2. ستحصل تلقائياً على رابط الخريطة

يمكنك أيضاً كتابة اسم المكان مباشرة وسأعطيك رابط الخريطة.

📍 اكتب اسم المكان:
            """,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")
            ]]),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data['mode'] = 'maps_request'
        return States.NLP_SEARCH_MODE
    
    elif query.data == "admin_panel":
        if admin_system.is_admin(update.effective_user.id):
            return await show_admin_panel(update, context)
        else:
            await query.answer("ليس لديك صلاحيات إدارية", show_alert=True)
            return States.MAIN_MENU
    
    elif query.data == "main_menu":
        return await start(update, context)

async def handle_nlp_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    """معالجة البحث بالنص الطبيعي"""
    if not update.message or not update.message.text:
        return States.NLP_SEARCH_MODE
    
    user_text = update.message.text.strip()
    mode = context.user_data.get('mode', '')
    
    try:
        if mode == 'maps_request':
            # طلب خريطة لمكان معين
            maps_url = geocoding_system.get_maps_url(user_text)
            coordinates = geocoding_system.get_coordinates(user_text)
            
            if coordinates:
                lat, lng = coordinates
                coord_text = f"📍 الإحداثيات: {lat:.6f}, {lng:.6f}"
            else:
                coord_text = "📍 لم يتم العثور على إحداثيات دقيقة"
            
            keyboard = [[
                InlineKeyboardButton("🗺️ فتح الخريطة", url=maps_url),
                InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")
            ]]
            
            await update.message.reply_text(
                f"🗺️ **خريطة {user_text}**\n\n{coord_text}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif mode == 'nlp_search':
            # البحث الذكي عن مسار
            await update.message.reply_text("🔍 جاري البحث...")
            
            search_result = nlp_system.search_route_from_text(user_text)
            
            if search_result['status'] == 'full_match':
                # تم العثور على المكانين
                start_name = search_result['start_location']['name']
                end_name = search_result['end_location']['name']
                
                # البحث عن المسار
                route_result = find_route_logic(start_name, end_name, routes_data)
                
                # إرسال النتيجة
                await update.message.reply_text(route_result, parse_mode=ParseMode.MARKDOWN)
                
                # إضافة رابط الخريطة
                maps_url = geocoding_system.get_maps_url(end_name)
                keyboard = [[
                    InlineKeyboardButton("🗺️ عرض الوجهة على الخريطة", url=maps_url),
                    InlineKeyboardButton("🔍 بحث جديد", callback_data="nlp_search"),
                    InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")
                ]]
                await update.message.reply_text(
                    "🎯 **خيارات إضافية:**",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )
            
            else:
                # نتيجة جزئية أو خطأ
                message = search_result['message']
                if search_result['suggestions']:
                    message += "\n\nاقتراحات:\n" + "\n".join(search_result['suggestions'])
                
                keyboard = [[
                    InlineKeyboardButton("🔍 بحث جديد", callback_data="nlp_search"),
                    InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")
                ]]
                await update.message.reply_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        
    except Exception as e:
        logger.exception(f"خطأ في معالجة البحث الذكي: {e}")
        await update.message.reply_text(
            "حدث خطأ في البحث. يرجى المحاولة مرة أخرى أو استخدام البحث التقليدي.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")
            ]])
        )
    
    return States.MAIN_MENU

async def handle_report_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    """معالجة إرسال التقارير"""
    query = update.callback_query
    await query.answer()
    
    report_type_map = {
        'report_congestion': 'congestion',
        'report_delay': 'delay', 
        'report_detour': 'detour',
        'report_normal': 'normal'
    }
    
    report_type = report_type_map.get(query.data)
    if report_type:
        context.user_data['report_type'] = report_type
        
        type_names = {
            'congestion': '🔴 ازدحام شديد',
            'delay': '🟡 تأخير في المواعيد',
            'detour': '🔄 تغيير مسار', 
            'normal': '🟢 الوضع طبيعي'
        }
        
        await query.edit_message_text(
            f"""
📝 **إرسال تقرير: {type_names[report_type]}**

اكتب تفاصيل التقرير (اختياري):
مثل: "ازدحام شديد عند محطة السلام" أو "الخط يعمل بانتظام"

أو اضغط "إرسال بدون تفاصيل" للإرسال المباشر.
            """,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 إرسال بدون تفاصيل", callback_data="send_report_no_details")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="main_menu")]
            ]),
            parse_mode=ParseMode.MARKDOWN
        )
        return States.REPORTING_MODE
    
    return States.MAIN_MENU

async def handle_report_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    """معالجة نص التقرير"""
    if not update.message or not update.message.text:
        return States.REPORTING_MODE
    
    report_type = context.user_data.get('report_type', 'normal')
    description = update.message.text.strip()
    user_id = update.effective_user.id
    
    # إضافة التقرير
    report = reports_system.add_report(
        user_id=user_id,
        route_name="خط عام",  # يمكن تحسينه لاحقاً
        report_type=report_type,
        description=description
    )
    
    type_names = {
        'congestion': '🔴 ازدحام شديد',
        'delay': '🟡 تأخير في المواعيد',
        'detour': '🔄 تغيير مسار',
        'normal': '🟢 الوضع طبيعي'
    }
    
    success_message = f"""
✅ **تم إرسال تقريرك بنجاح!**

📊 نوع التقرير: {type_names[report_type]}
📝 التفاصيل: {description}
🕒 الوقت: {datetime.now().strftime("%H:%M")}

شكراً لك على مساهمتك في تحسين خدمة المواصلات!
    """
    
    await update.message.reply_text(
        success_message,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 عرض التقارير الحالية", callback_data="live_reports")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )
    
    context.user_data.clear()
    return States.MAIN_MENU

# دوال البحث التقليدي (مبسطة)
async def select_start_neighborhood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    query = update.callback_query
    await query.answer()
    
    chosen = query.data.split(":", 1)[1]
    context.user_data['start_neighborhood'] = chosen
    
    categories = list(neighborhood_data[chosen].keys())
    keyboard = build_keyboard(categories, "start_category", "start")
    
    await query.edit_message_text(
        f"🏘️ **الحي:** {chosen}\n\n📂 اختر التصنيف:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    return States.SELECTING_START_CATEGORY

async def select_start_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    query = update.callback_query
    await query.answer()
    
    chosen = query.data.split(":", 1)[1]
    context.user_data['start_category'] = chosen
    neighborhood = context.user_data['start_neighborhood']
    
    landmarks = neighborhood_data[neighborhood][chosen]
    keyboard = build_keyboard(landmarks, "start_landmark", "start_neighborhood")
    
    await query.edit_message_text(
        f"🏘️ **الحي:** {neighborhood}\n📂 **التصنيف:** {chosen}\n\n📍 اختر المعلم:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    return States.SELECTING_START_LANDMARK

async def select_start_landmark(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    query = update.callback_query
    await query.answer()
    
    chosen = query.data.split(":", 1)[1]
    context.user_data['start_landmark'] = chosen
    
    neighborhoods = list(neighborhood_data.keys())
    keyboard = build_keyboard(neighborhoods, "end_neighborhood", "start_category")
    
    await query.edit_message_text(
        f"✅ **نقطة البداية:** {chosen}\n\n🎯 اختر حي الوجهة:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    return States.SELECTING_END_NEIGHBORHOOD

async def select_end_neighborhood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    query = update.callback_query
    await query.answer()
    
    chosen = query.data.split(":", 1)[1]
    context.user_data['end_neighborhood'] = chosen
    
    categories = list(neighborhood_data[chosen].keys())
    keyboard = build_keyboard(categories, "end_category", "start_landmark")
    
    await query.edit_message_text(
        f"🎯 **حي الوجهة:** {chosen}\n\n📂 اختر التصنيف:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    return States.SELECTING_END_CATEGORY

async def select_end_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    query = update.callback_query
    await query.answer()
    
    chosen = query.data.split(":", 1)[1]
    context.user_data['end_category'] = chosen
    neighborhood = context.user_data['end_neighborhood']
    
    landmarks = neighborhood_data[neighborhood][chosen]
    keyboard = build_keyboard(landmarks, "end_landmark", "end_neighborhood")
    
    await query.edit_message_text(
        f"🎯 **حي الوجهة:** {neighborhood}\n📂 **التصنيف:** {chosen}\n\n📍 اختر المعلم:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    return States.SELECTING_END_LANDMARK

async def select_end_landmark_and_find_route(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    chosen = query.data.split(":", 1)[1]
    start_landmark = context.user_data.get('start_landmark')
    
    await query.edit_message_text("🔍 جاري البحث عن أفضل مسار...")
    
    # البحث عن المسار
    result = find_route_logic(start_landmark, chosen, routes_data)
    
    # إرسال النتيجة مع الخريطة
    maps_url = geocoding_system.get_maps_url(chosen)
    keyboard = [
        [InlineKeyboardButton("🗺️ عرض على الخريطة", url=maps_url)],
        [InlineKeyboardButton("📝 أبلغ عن حالة المرور", callback_data="submit_report")],
        [InlineKeyboardButton("🔍 بحث جديد", callback_data="traditional_search")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        result,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    context.user_data.clear()
    return ConversationHandler.END

# دوال الإدارة
async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    query = update.callback_query
    
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات النظام", callback_data="admin_stats")],
        [InlineKeyboardButton("✅ إدارة التقارير", callback_data="admin_reports")],
        [InlineKeyboardButton("👥 إدارة المشرفين", callback_data="admin_manage_admins")],
        [InlineKeyboardButton("🗂️ نسخ احتياطي", callback_data="admin_backup")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    
    stats_text = f"""
⚙️ **لوحة الإدارة**

📊 **إحصائيات سريعة:**
• المشرفين النشطين: {len(admin_system.admin_ids) + len(SUPER_ADMIN_IDS)}
• التقارير النشطة: {len(reports_system.get_active_reports())}
• إجمالي الأحياء: {len(neighborhood_data)}
• إجمالي الخطوط: {len(routes_data)}

اختر العملية المطلوبة:
    """
    
    if query:
        await query.edit_message_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    return States.ADMIN_MENU

async def handle_admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    query = update.callback_query
    await query.answer()
    
    if query.data == "admin_reports":
        active_reports = reports_system.get_active_reports()
        if active_reports:
            reports_text = "📋 **إدارة التقارير النشطة:**\n\n"
            for report in active_reports[-10:]:
                emoji = "🔴" if report['report_type'] == 'congestion' else "🟡" if report['report_type'] == 'delay' else "🟢"
                time_str = report['timestamp'][11:16]
                verified_str = "✅" if report['verified'] else "⏳"
                reports_text += f"{emoji} {verified_str} **{report['route_name']}** ({time_str})\n📝 {report['description']}\n\n"
        else:
            reports_text = "📋 لا توجد تقارير نشطة حالياً."
        
        await query.edit_message_text(
            reports_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 تحديث", callback_data="admin_reports")],
                [InlineKeyboardButton("🔙 لوحة الإدارة", callback_data="admin_panel")]
            ]),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif query.data == "admin_stats":
        geocache_count = len(geocoding_system.cache)
        total_landmarks = sum(len(categories[cat]) for categories in neighborhood_data.values() for cat in categories)
        
        stats_text = f"""
📊 **إحصائيات مفصلة:**

🏘️ **البيانات الأساسية:**
• الأحياء: {len(neighborhood_data)}
• المعالم: {total_landmarks}
• خطوط المواصلات: {len(routes_data)}

📡 **التقارير:**
• التقارير النشطة: {len(reports_system.get_active_reports())}
• إجمالي التقارير: {len(reports_system.reports)}

🗺️ **الجيوكود:**
• الأماكن المحفوظة: {geocache_count}

👥 **الإدارة:**
• المشرفين: {len(admin_system.admin_ids)}
• المشرفين الأساسيين: {len(SUPER_ADMIN_IDS)}
        """
        
        await query.edit_message_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 لوحة الإدارة", callback_data="admin_panel")
            ]]),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif query.data == "admin_backup":
        # إنشاء نسخة احتياطية
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_data = {
                'timestamp': timestamp,
                'reports': reports_system.reports,
                'geocache': geocoding_system.cache,
                'admin_ids': admin_system.admin_ids
            }
            
            backup_filename = f"backup_{timestamp}.json"
            with open(backup_filename, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            await query.edit_message_text(
                f"✅ **تم إنشاء نسخة احتياطية بنجاح!**\n\nاسم الملف: `{backup_filename}`\nالوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 لوحة الإدارة", callback_data="admin_panel")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ فشل في إنشاء النسخة الاحتياطية: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 لوحة الإدارة", callback_data="admin_panel")
                ]])
            )
    
    return States.ADMIN_MENU

# دوال التنقل للخلف
async def handle_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    """معالجة التنقل للخلف"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_start":
        neighborhoods = list(neighborhood_data.keys())
        keyboard = build_keyboard(neighborhoods, "start_neighborhood")
        await query.edit_message_text(
            "🏘️ **اختر حي البداية:**",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return States.SELECTING_START_NEIGHBORHOOD
    
    # المزيد من دوال التنقل يمكن إضافتها هنا...
    
    return await start(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """إلغاء المحادثة"""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "تم إلغاء العملية. استخدم /start للبدء من جديد.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🚌 بدء جديد", callback_data="main_menu")
            ]])
        )
    else:
        await update.message.reply_text(
            "تم إلغاء العملية. استخدم /start للبدء من جديد.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🚌 بدء جديد", callback_data="main_menu")
            ]])
        )
    
    context.user_data.clear()
    return ConversationHandler.END

# ===== الدالة الرئيسية =====

def main() -> None:
    """تشغيل البوت النهائي المطور"""
    logger.info("🚀 بدء تشغيل بوت مواصلات بورسعيد المطور...")
    
    application = Application.builder().token(BOT_TOKEN).build()

    # إعداد معالج المحادثة الرئيسي
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            States.MAIN_MENU: [
                CallbackQueryHandler(handle_main_menu, pattern=r'^(traditional_search|nlp_search|live_reports|submit_report|maps_view|admin_panel|main_menu)$'),
                CallbackQueryHandler(handle_report_submission, pattern=r'^report_(congestion|delay|detour|normal)$'),
                CallbackQueryHandler(cancel, pattern=r'^cancel_action$')
            ],
            States.SELECTING_START_NEIGHBORHOOD: [
                CallbackQueryHandler(select_start_neighborhood, pattern=r'^start_neighborhood:'),
                CallbackQueryHandler(handle_navigation, pattern=r'^back_to_'),
                CallbackQueryHandler(start, pattern=r'^main_menu$')
            ],
            States.SELECTING_START_CATEGORY: [
                CallbackQueryHandler(select_start_category, pattern=r'^start_category:'),
                CallbackQueryHandler(handle_navigation, pattern=r'^back_to_'),
                CallbackQueryHandler(start, pattern=r'^main_menu$')
            ],
            States.SELECTING_START_LANDMARK: [
                CallbackQueryHandler(select_start_landmark, pattern=r'^start_landmark:'),
                CallbackQueryHandler(handle_navigation, pattern=r'^back_to_'),
                CallbackQueryHandler(start, pattern=r'^main_menu$')
            ],
            States.SELECTING_END_NEIGHBORHOOD: [
                CallbackQueryHandler(select_end_neighborhood, pattern=r'^end_neighborhood:'),
                CallbackQueryHandler(handle_navigation, pattern=r'^back_to_'),
                CallbackQueryHandler(start, pattern=r'^main_menu$')
            ],
            States.SELECTING_END_CATEGORY: [
                CallbackQueryHandler(select_end_category, pattern=r'^end_category:'),
                CallbackQueryHandler(handle_navigation, pattern=r'^back_to_'),
                CallbackQueryHandler(start, pattern=r'^main_menu$')
            ],
            States.SELECTING_END_LANDMARK: [
                CallbackQueryHandler(select_end_landmark_and_find_route, pattern=r'^end_landmark:'),
                CallbackQueryHandler(handle_navigation, pattern=r'^back_to_'),
                CallbackQueryHandler(start, pattern=r'^main_menu$')
            ],
            States.NLP_SEARCH_MODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_nlp_search),
                CallbackQueryHandler(start, pattern=r'^main_menu$')
            ],
            States.REPORT_TYPE_SELECTION: [
                CallbackQueryHandler(handle_report_submission),
                CallbackQueryHandler(start, pattern=r'^main_menu$')
            ],
            States.REPORTING_MODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_report_text),
                CallbackQueryHandler(lambda u, c: handle_report_text(u, c), pattern=r'^send_report_no_details$'),
                CallbackQueryHandler(start, pattern=r'^main_menu$')
            ],
            States.ADMIN_MENU: [
                CallbackQueryHandler(handle_admin_actions),
                CallbackQueryHandler(show_admin_panel, pattern=r'^admin_panel$'),
                CallbackQueryHandler(start, pattern=r'^main_menu$')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(cancel, pattern=r'^cancel_action$'),
            CallbackQueryHandler(start, pattern=r'^main_menu$')
        ],
        per_message=False,
    )

    application.add_handler(conv_handler)
    
    # أوامر إضافية
    application.add_handler(CommandHandler('help', lambda u, c: u.message.reply_text(
        """
🚌 **دليل استخدام بوت مواصلات بورسعيد**

**الأوامر:**
/start - بدء المحادثة
/help - هذه المساعدة
/cancel - إلغاء العملية الحالية

**الميزات:**
🔍 بحث ذكي بالنص الحر
📊 تقارير مرور مباشرة
🗺️ خرائط تفاعلية
⚙️ نظام إدارة متقدم

**أمثلة للبحث الذكي:**
• "إزاي أروح من سوبر ماركت بكير للمستشفى؟"
• "من الجامعة للمحطة"
• "طريقة الوصول للمول من البنك"
        """
    )))

    logger.info("✅ تم تهيئة البوت بنجاح مع جميع الميزات المتقدمة!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()