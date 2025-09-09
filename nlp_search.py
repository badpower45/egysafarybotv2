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
        # أولاً البحث عن المناطق السكنية المبسطة
        residential_match = self.parse_residential_areas(text)
        if residential_match:
            return residential_match
        
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
                result['status'] = 'success'
                result['message'] = f"✅ تم العثور على مسار من {result['start_location']['name']} إلى {result['end_location']['name']}"
            elif result['start_location']:
                result['message'] = f"✅ تم العثور على نقطة البداية: {result['start_location']['name']}. يرجى تحديد الوجهة."
            else:
                result['message'] = f"✅ تم العثور على الوجهة: {result['end_location']['name']}. يرجى تحديد نقطة البداية."
        
        return result

    def get_suggestions_for_text(self, text: str, limit: int = 5) -> List[str]:
        """الحصول على اقتراحات للنص المدخل"""
        text = text.lower().strip()
        suggestions = []
        
        for landmark_name, landmark_info in self.landmarks_index.items():
            if text in landmark_name:
                suggestion = f"{landmark_info['data'].get('name', landmark_name)} - {landmark_info['neighborhood']}"
                if suggestion not in suggestions:
                    suggestions.append(suggestion)
            
            if len(suggestions) >= limit:
                break
        
        return suggestions

    def parse_residential_areas(self, query: str) -> Dict:
        """تحليل المناطق السكنية المبسطة"""
        # إزالة كلمات مثل "السكنية"، "منطقة"
        query = re.sub(r'\b(السكنية|السكنيه|منطقة|منطقه)\b', '', query)
        query = query.strip()
        
        # البحث عن نمط "من X لـ Y" أو "X للـ Y" أو "X لـ Y"
        patterns = [
            r'من\s+(.+?)\s+(?:لـ|ل|إلى|الى)\s+(.+)',
            r'(.+?)\s+(?:للـ|للـ|لـ|ل)\s+(.+)',
            r'(.+?)\s+إلى\s+(.+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                start_area = match.group(1).strip()
                end_area = match.group(2).strip()
                
                # البحث عن أقرب مطابقة للمناطق السكنية
                start_match = self.find_residential_area(start_area)
                end_match = self.find_residential_area(end_area)
                
                if start_match and end_match:
                    return {
                        'status': 'success',
                        'type': 'residential_route',
                        'start_area': start_match,
                        'end_area': end_match,
                        'message': f'🚌 البحث عن مسار من منطقة {start_match} إلى منطقة {end_match}',
                        'confidence': 0.85
                    }
        
        return None
    
    def find_residential_area(self, area_name: str) -> str:
        """البحث عن المنطقة السكنية الأقرب"""
        area_name = area_name.lower().strip()
        
        # قائمة المناطق السكنية الشائعة
        residential_areas = [
            "بوروتكس", "السلام", "المناخ", "الشرق", "العرب",
            "الزهور", "المنطقة الأولى", "المنطقة الثانية", 
            "المنطقة الثالثة", "المنطقة الرابعة", "المنطقة الخامسة", "المنطقة السادسة",
            "منطقة شمال الحرية", "قشلاق السواحل", "حي ناصر"
        ]
        
        # البحث المباشر
        for area in residential_areas:
            if area_name == area.lower():
                return area
        
        # البحث الجزئي
        for area in residential_areas:
            if area_name in area.lower() or area.lower() in area_name:
                return area
        
        # البحث بالتشابه
        best_match = None
        best_ratio = 0.6
        
        for area in residential_areas:
            ratio = SequenceMatcher(None, area_name, area.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = area
        
        return best_match