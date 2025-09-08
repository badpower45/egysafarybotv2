# -*- coding: utf-8 -*-
"""
تكامل خرائط جوجل للحصول على الإحداثيات والروابط
"""

import requests
from urllib.parse import quote
import folium
from typing import Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)

class GoogleMapsIntegration:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://maps.googleapis.com/maps/api"
    
    def get_location_coordinates(self, place_name: str, city: str = "Port Said") -> Optional[Dict]:
        """الحصول على إحداثيات مكان معين"""
        if not self.api_key:
            logger.warning("Google Maps API key not provided, using fallback method")
            return self._generate_fallback_data(place_name, city)
        
        try:
            query = f"{place_name}, {city}, Egypt"
            url = f"{self.base_url}/geocode/json"
            params = {
                'address': query,
                'key': self.api_key
            }
            
            response = requests.get(url, params=params)
            data = response.json()
            
            if data['status'] == 'OK' and data['results']:
                result = data['results'][0]
                location = result['geometry']['location']
                
                return {
                    'name': result['formatted_address'],
                    'lat': location['lat'],
                    'lng': location['lng'],
                    'place_id': result.get('place_id'),
                    'maps_url': f"https://www.google.com/maps/place/?q=place_id:{result.get('place_id')}"
                }
        except Exception as e:
            logger.error(f"Error getting coordinates for {place_name}: {e}")
        
        return self._generate_fallback_data(place_name, city)
    
    def _generate_fallback_data(self, place_name: str, city: str) -> Dict:
        """إنشاء بيانات احتياطية عند عدم توفر API"""
        encoded_query = quote(f"{place_name}, {city}, Egypt")
        return {
            'name': f"{place_name}, {city}",
            'lat': 31.2565,  # إحداثيات عامة لبورسعيد
            'lng': 32.2842,
            'place_id': None,
            'maps_url': f"https://www.google.com/maps/search/{encoded_query}"
        }
    
    def generate_route_map(self, start_location: Dict, end_location: Dict, 
                          route_points: list = None) -> str:
        """إنشاء خريطة تفاعلية للمسار"""
        try:
            # إنشاء خريطة بـ Folium
            center_lat = (start_location['lat'] + end_location['lat']) / 2
            center_lng = (start_location['lng'] + end_location['lng']) / 2
            
            m = folium.Map(location=[center_lat, center_lng], zoom_start=13)
            
            # إضافة نقطة البداية
            folium.Marker(
                [start_location['lat'], start_location['lng']],
                popup=f"البداية: {start_location['name']}",
                icon=folium.Icon(color='green', icon='play')
            ).add_to(m)
            
            # إضافة نقطة النهاية
            folium.Marker(
                [end_location['lat'], end_location['lng']],
                popup=f"الوجهة: {end_location['name']}",
                icon=folium.Icon(color='red', icon='stop')
            ).add_to(m)
            
            # إضافة نقاط المسار إذا كانت متوفرة
            if route_points:
                for point in route_points:
                    if isinstance(point, dict) and 'lat' in point and 'lng' in point:
                        folium.Marker(
                            [point['lat'], point['lng']],
                            popup=point.get('name', 'نقطة في المسار'),
                            icon=folium.Icon(color='blue', icon='info-sign')
                        ).add_to(m)
            
            # حفظ الخريطة
            map_filename = f"route_map_{start_location['name']}_{end_location['name']}.html".replace(' ', '_')
            m.save(map_filename)
            
            return map_filename
        except Exception as e:
            logger.error(f"Error generating route map: {e}")
            return None

class WebsiteIntegration:
    def __init__(self, base_url: str = "https://egy-safari.com"):
        self.base_url = base_url
    
    def get_location_info(self, location_name: str) -> Optional[Dict]:
        """الحصول على معلومات إضافية عن مكان من الموقع"""
        try:
            # محاكاة طلب API للموقع
            # في التطبيق الحقيقي، ستكون هناك طلبات HTTP فعلية
            
            # بيانات تجريبية للتوضيح
            location_info = {
                'description': f"معلومات مفصلة عن {location_name}",
                'website_url': f"{self.base_url}/locations/{quote(location_name)}",
                'services': ['مواصلات عامة', 'تاكسي', 'خدمات توصيل'],
                'nearby_attractions': ['معالم سياحية قريبة', 'مطاعم', 'فنادق'],
                'tips': ['نصائح للزيارة', 'أوقات الذروة', 'وسائل المواصلات المناسبة']
            }
            
            return location_info
        except Exception as e:
            logger.error(f"Error getting website info for {location_name}: {e}")
            return None
    
    def get_live_updates(self, route_name: str) -> Optional[Dict]:
        """الحصول على تحديثات مباشرة عن حالة المرور"""
        try:
            # محاكاة نظام التحديثات المباشرة
            updates = {
                'route_status': 'normal',  # normal, crowded, delayed
                'estimated_time': '15-20 دقيقة',
                'last_updated': '2025-09-08 19:30:00',
                'user_reports': [
                    {'time': '19:25', 'message': 'الخط يعمل بانتظام'},
                    {'time': '19:20', 'message': 'زحمة خفيفة عند المحطة الرئيسية'}
                ]
            }
            
            return updates
        except Exception as e:
            logger.error(f"Error getting live updates for {route_name}: {e}")
            return None

# إنشاء مثيلات عامة
maps_integration = GoogleMapsIntegration()
website_integration = WebsiteIntegration()