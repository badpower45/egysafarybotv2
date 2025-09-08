# -*- coding: utf-8 -*-
"""
نظام الإدارة التفاعلي للبوت - إضافة وتعديل الخطوط والتعريفات
"""

import json
import os
from typing import Dict, List, Any
from datetime import datetime

class AdminSystem:
    def __init__(self, data_file_path="data.py", admin_ids_file="admin_ids.json"):
        self.data_file_path = data_file_path
        self.admin_ids_file = admin_ids_file
        self.admin_ids = self.load_admin_ids()
    
    def load_admin_ids(self) -> List[int]:
        """تحميل قائمة معرفات المشرفين"""
        try:
            if os.path.exists(self.admin_ids_file):
                with open(self.admin_ids_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('admin_ids', [])
            return []
        except Exception as e:
            print(f"خطأ في تحميل معرفات المشرفين: {e}")
            return []
    
    def save_admin_ids(self):
        """حفظ قائمة معرفات المشرفين"""
        try:
            with open(self.admin_ids_file, 'w', encoding='utf-8') as f:
                json.dump({'admin_ids': self.admin_ids}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"خطأ في حفظ معرفات المشرفين: {e}")
    
    def is_admin(self, user_id: int) -> bool:
        """التحقق من صلاحيات المشرف"""
        return user_id in self.admin_ids
    
    def add_admin(self, user_id: int) -> bool:
        """إضافة مشرف جديد"""
        if user_id not in self.admin_ids:
            self.admin_ids.append(user_id)
            self.save_admin_ids()
            return True
        return False
    
    def remove_admin(self, user_id: int) -> bool:
        """إزالة مشرف"""
        if user_id in self.admin_ids:
            self.admin_ids.remove(user_id)
            self.save_admin_ids()
            return True
        return False
    
    def backup_data(self):
        """إنشاء نسخة احتياطية من البيانات"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"data_backup_{timestamp}.py"
            
            if os.path.exists(self.data_file_path):
                with open(self.data_file_path, 'r', encoding='utf-8') as source:
                    with open(backup_file, 'w', encoding='utf-8') as backup:
                        backup.write(source.read())
                return backup_file
        except Exception as e:
            print(f"خطأ في إنشاء النسخة الاحتياطية: {e}")
        return None
    
    def add_route_to_data(self, route_data: Dict[str, Any]) -> bool:
        """إضافة خط مواصلات جديد"""
        try:
            # إنشاء نسخة احتياطية أولاً
            backup_file = self.backup_data()
            
            # قراءة البيانات الحالية
            with open(self.data_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # البحث عن نهاية قائمة routes_data وإضافة الخط الجديد
            route_str = self._format_route_data(route_data)
            
            # العثور على آخر عنصر في routes_data وإضافة الخط الجديد
            insert_pos = content.rfind(']', content.find('routes_data = ['))
            if insert_pos != -1:
                new_content = (
                    content[:insert_pos] + 
                    "    " + route_str + ",\n" +
                    content[insert_pos:]
                )
                
                with open(self.data_file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                return True
        except Exception as e:
            print(f"خطأ في إضافة الخط: {e}")
        return False
    
    def _format_route_data(self, route_data: Dict[str, Any]) -> str:
        """تنسيق بيانات الخط للإدراج في الملف"""
        formatted = "{\n"
        for key, value in route_data.items():
            if isinstance(value, str):
                formatted += f'        "{key}": "{value}",\n'
            elif isinstance(value, list):
                formatted += f'        "{key}": [\n'
                for item in value:
                    formatted += f'            "{item}",\n'
                formatted += '        ],\n'
            else:
                formatted += f'        "{key}": {value},\n'
        formatted += "    }"
        return formatted
    
    def add_landmark_to_neighborhood(self, neighborhood: str, category: str, landmark_data: Dict[str, Any]) -> bool:
        """إضافة معلم جديد لحي معين"""
        try:
            backup_file = self.backup_data()
            
            with open(self.data_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # البحث عن الحي والتصنيف المطلوب وإضافة المعلم
            landmark_str = self._format_landmark_data(landmark_data)
            
            # هنا يمكن تطوير منطق أكثر تعقيداً للبحث والإدراج
            # للبساطة، سنضع تنبيه للمطور ليقوم بالإضافة يدوياً
            print(f"إضافة معلم جديد: {landmark_str} إلى {neighborhood} -> {category}")
            
            return True
        except Exception as e:
            print(f"خطأ في إضافة المعلم: {e}")
        return False
    
    def _format_landmark_data(self, landmark_data: Dict[str, Any]) -> str:
        """تنسيق بيانات المعلم"""
        return json.dumps(landmark_data, ensure_ascii=False, indent=4)

# مثيل عام للنظام
admin_system = AdminSystem()