# -*- coding: utf-8 -*-
"""
نظام معالجة اللغة الطبيعية للبحث المباشر في المواصلات
"""

import re
from typing import List, Dict, Tuple, Optional
from difflib import SequenceMatcher

class NLPSearchSystem:
    def __init__(self, neighborhood_data: Dict):
        self.neighborhood_data = neighborhood_data
        self.landmarks_index = self._build_landmarks_index()
        
        # كلمات ربط عربية شائعة
        self.from_keywords = ['من', 'من عند', 'بدءاً من', 'انطلاقاً من', 'ابتداءً من']
        self.to_keywords = ['إلى', 'الى', 'لـ', 'ل', 'حتى', 'وصولاً إلى', 'باتجاه']
        self.question_keywords = ['إزاي', 'ازاي', 'كيف', 'طريقة', 'أروح', 'اروح', 'أوصل', 'اوصل']
    
    def _build_landmarks_index(self) -> Dict[str, Dict]:
        """بناء فهرس لجميع المعالم للبحث السريع"""
        index = {}
        for neighborhood, categories in self.neighborhood_data.items():
            for category, landmarks in categories.items():
                for landmark in landmarks:
                    if isinstance(landmark, dict):
                        name = landmark.get('name', '').lower()
                        index[name] = {
                            'neighborhood': neighborhood,
                            'category': category,
                            'data': landmark
                        }
                    elif isinstance(landmark, str):
                        name = landmark.lower()
                        index[name] = {
                            'neighborhood': neighborhood,
                            'category': category,
                            'data': {'name': landmark, 'served_by': {}}
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
                    'name': landmark_name,
                    'score': score,
                    'info': landmark_info
                }
        
        return best_match
    
    def extract_locations_from_text(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """استخراج نقطتي البداية والوجهة من النص"""
        text = text.replace('؟', '').replace('?', '').strip()
        
        # البحث عن أنماط "من X إلى Y"
        from_to_pattern = r'(?:من|من عند)\s+(.+?)\s+(?:إلى|الى|لـ|ل|حتى)\s+(.+?)(?:\s|$)'
        match = re.search(from_to_pattern, text)
        
        if match:
            start_location = match.group(1).strip()
            end_location = match.group(2).strip()
            return start_location, end_location
        
        # البحث عن أنماط "إزاي أروح X"
        how_to_go_pattern = r'(?:إزاي|ازاي|كيف)\s+(?:أروح|اروح|أوصل|اوصل)\s+(.+?)(?:\s|$)'
        match = re.search(how_to_go_pattern, text)
        
        if match:
            destination = match.group(1).strip()
            return None, destination  # البداية غير محددة
        
        # البحث عن مواقع بكلمات ربط
        parts = []
        for keyword in self.from_keywords + self.to_keywords:
            if keyword in text:
                parts = text.split(keyword)
                break
        
        if len(parts) >= 2:
            potential_start = parts[0].strip()
            potential_end = parts[1].strip()
            
            # تنظيف النص من كلمات الاستفهام
            for q_word in self.question_keywords:
                potential_start = potential_start.replace(q_word, '').strip()
                potential_end = potential_end.replace(q_word, '').strip()
            
            return potential_start or None, potential_end or None
        
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
        
        # إذا تم العثور على موقع واحد على الأقل
        if result['start_location'] or result['end_location']:
            result['status'] = 'partial_match'
            if result['start_location'] and result['end_location']:
                result['status'] = 'full_match'
                result['message'] = f"تم العثور على: {result['start_location']['name']} → {result['end_location']['name']}"
            elif result['start_location']:
                result['message'] = f"تم العثور على نقطة البداية: {result['start_location']['name']}. من فضلك حدد الوجهة."
            else:
                result['message'] = f"تم العثور على الوجهة: {result['end_location']['name']}. من فضلك حدد نقطة البداية."
        
        # إضافة اقتراحات
        if not result['start_location'] and start_text:
            suggestions = self._get_suggestions(start_text)
            result['suggestions'].extend([f"هل قصدت '{s}' كنقطة بداية؟" for s in suggestions])
        
        if not result['end_location'] and end_text:
            suggestions = self._get_suggestions(end_text)
            result['suggestions'].extend([f"هل قصدت '{s}' كوجهة؟" for s in suggestions])
        
        return result
    
    def _get_suggestions(self, query: str, limit: int = 3) -> List[str]:
        """الحصول على اقتراحات لأسماء مشابهة"""
        suggestions = []
        query = query.lower()
        
        for landmark_name in self.landmarks_index.keys():
            score = self.similarity_score(query, landmark_name)
            if 0.3 <= score < 0.6:  # تشابه متوسط
                suggestions.append((landmark_name, score))
        
        # ترتيب حسب النتيجة وإرجاع الأفضل
        suggestions.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in suggestions[:limit]]
    
    def is_natural_language_query(self, text: str) -> bool:
        """التحقق مما إذا كان النص استفهام طبيعي"""
        text = text.lower()
        
        # البحث عن كلمات استفهام
        question_indicators = ['إزاي', 'ازاي', 'كيف', 'من', 'إلى', 'الى', '؟', '?']
        
        return any(indicator in text for indicator in question_indicators)

# إنشاء مثيل عام - سيتم تهيئته عند تشغيل البوت
nlp_system = None

def initialize_nlp_system(neighborhood_data):
    """تهيئة نظام معالجة اللغة الطبيعية"""
    global nlp_system
    nlp_system = NLPSearchSystem(neighborhood_data)
    return nlp_system