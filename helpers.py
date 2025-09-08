# -*- coding: utf-8 -*-
"""
ملف الدوال المساعدة للبوت
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict, Any, Optional

def build_keyboard(items: List, prefix: str, back_target: Optional[str] = None) -> InlineKeyboardMarkup:
    """بناء لوحة المفاتيح التفاعلية"""
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
            # تقصير البيانات لتجنب خطأ Telegram (64 byte limit)
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
    nav_buttons.append(InlineKeyboardButton("❌ إلغاء", callback_data="cancel_action"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    return InlineKeyboardMarkup(keyboard)

def find_route_logic(start_landmark: str, end_landmark: str, routes_data: List[Dict]) -> str:
    """
    البحث عن أفضل مسار بين معلمين
    """
    
    # البحث عن المسارات المباشرة
    direct_routes = []
    transfer_routes = []
    
    for route in routes_data:
        key_points = route.get('keyPoints', [])
        if not key_points:
            continue
            
        # البحث عن النقاط في المسار (مطابقة جزئية)
        start_indices = []
        end_indices = []
        
        for i, point in enumerate(key_points):
            if isinstance(point, str):
                point_lower = point.lower()
                if start_landmark.lower() in point_lower:
                    start_indices.append(i)
                if end_landmark.lower() in point_lower:
                    end_indices.append(i)
        
        if start_indices and end_indices:
            # التحقق من الترتيب الصحيح
            valid_sequence = any(s_idx < e_idx for s_idx in start_indices for e_idx in end_indices)
            if valid_sequence:
                direct_routes.append({
                    'route': route,
                    'start_points': [key_points[i] for i in start_indices],
                    'end_points': [key_points[i] for i in end_indices]
                })
    
    if direct_routes:
        result = "🚌 **تم العثور على مسارات مباشرة:**\n\n"
        for i, route_info in enumerate(direct_routes, 1):
            route = route_info['route']
            result += f"{i}. **{route.get('routeName', 'خط غير محدد')}**\n"
            result += f"   🚏 نقاط الركوب: {', '.join(route_info['start_points'])}\n"
            result += f"   🛑 نقاط النزول: {', '.join(route_info['end_points'])}\n"
            result += f"   💰 التعريفة: {route.get('fare', 'غير محددة')}\n"
            if route.get('notes'):
                result += f"   📝 ملاحظات: {route.get('notes')}\n"
            result += "\n"
        
        result += "💡 **نصيحة:** تأكد من السائق للتأكيد من نقاط الركوب والنزول الصحيحة."
        return result
    
    else:
        # البحث عن مسارات بتبديل
        potential_connections = []
        
        for route1 in routes_data:
            for route2 in routes_data:
                if route1 == route2:
                    continue
                
                # البحث عن نقاط مشتركة للتبديل
                route1_points = route1.get('keyPoints', [])
                route2_points = route2.get('keyPoints', [])
                
                # هل يخدم route1 نقطة البداية؟
                route1_has_start = any(start_landmark.lower() in str(point).lower() 
                                     for point in route1_points)
                
                # هل يخدم route2 نقطة النهاية؟ 
                route2_has_end = any(end_landmark.lower() in str(point).lower() 
                                   for point in route2_points)
                
                if route1_has_start and route2_has_end:
                    # البحث عن نقاط التبديل المشتركة
                    common_points = []
                    for p1 in route1_points:
                        for p2 in route2_points:
                            if isinstance(p1, str) and isinstance(p2, str):
                                if p1.lower() == p2.lower() or \
                                   (len(p1) > 5 and len(p2) > 5 and 
                                    (p1.lower() in p2.lower() or p2.lower() in p1.lower())):
                                    common_points.append(p1)
                    
                    if common_points:
                        potential_connections.append({
                            'route1': route1,
                            'route2': route2,
                            'transfer_points': common_points
                        })
        
        if potential_connections:
            result = "🔄 **مسارات بتبديل متاحة:**\n\n"
            for i, conn in enumerate(potential_connections[:3], 1):  # أول 3 خيارات
                result += f"{i}. **{conn['route1'].get('routeName')}** ← **{conn['route2'].get('routeName')}**\n"
                result += f"   🔄 نقاط التبديل: {', '.join(conn['transfer_points'][:2])}\n"
                fare1 = conn['route1'].get('fare', 'غير محددة')
                fare2 = conn['route2'].get('fare', 'غير محددة') 
                result += f"   💰 التعريفة: {fare1} + {fare2}\n\n"
            
            result += "📝 **ملاحظة:** قد تحتاج لسؤال السائق عن أفضل نقاط التبديل."
            return result
        
        else:
            return f"""
❌ **عذراً، لم أجد مساراً مباشراً بين {start_landmark} و {end_landmark}**

💡 **اقتراحات:**
• تأكد من صحة أسماء الأماكن
• جرب البحث عن معالم قريبة من وجهتك
• استخدم البحث الذكي بكتابة السؤال مباشرة
• أو استخدم وسائل مواصلات أخرى (تاكسي، أوبر، إلخ)

🔍 **للمساعدة:** جرب البحث الذكي واكتب مثلاً "إزاي أروح من [مكان قريب من {start_landmark}] لـ [مكان قريب من {end_landmark}]؟"
            """

def validate_callback_data(callback_data: str) -> bool:
    """التحقق من صحة بيانات الCallback"""
    if not callback_data:
        return False
    
    # التحقق من الطول
    if len(callback_data.encode('utf-8')) > 64:
        return False
    
    # التحقق من التنسيق
    if ':' not in callback_data:
        return False
    
    return True

def format_time_ago(timestamp_str: str) -> str:
    """تنسيق الوقت النسبي"""
    try:
        from datetime import datetime
        
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        now = datetime.now(timestamp.tzinfo)
        
        diff = now - timestamp
        
        if diff.days > 0:
            return f"منذ {diff.days} يوم"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"منذ {hours} ساعة"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"منذ {minutes} دقيقة"
        else:
            return "الآن"
    except:
        return "غير معروف"