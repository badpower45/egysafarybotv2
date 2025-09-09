# -*- coding: utf-8 -*-
"""
مساعد قاعدة البيانات لقراءة البيانات للبوت
"""

import sqlite3
import json

def get_routes_from_db():
    """قراءة جميع الخطوط من قاعدة البيانات"""
    try:
        conn = sqlite3.connect('admin_bot.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT name, fare, start_area, end_area, key_points, notes FROM route")
        routes = cursor.fetchall()
        
        routes_data = []
        for route in routes:
            name, fare, start_area, end_area, key_points_json, notes = route
            try:
                key_points = json.loads(key_points_json) if key_points_json else []
            except:
                key_points = []
            
            route_data = {
                'routeName': name,
                'fare': f"{fare} جنيه مصري",
                'startArea': start_area or '',
                'endArea': end_area or '',
                'keyPoints': key_points,
                'notes': notes or ''
            }
            routes_data.append(route_data)
        
        conn.close()
        return routes_data
    except Exception as e:
        print(f"خطأ في قراءة الخطوط من قاعدة البيانات: {e}")
        return []

def get_neighborhoods_from_db():
    """قراءة جميع الأحياء والأماكن من قاعدة البيانات"""
    try:
        conn = sqlite3.connect('admin_bot.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT neighborhood, category, name FROM location ORDER BY neighborhood, category, name")
        locations = cursor.fetchall()
        
        neighborhood_data = {}
        for location in locations:
            neighborhood, category, name = location
            
            if neighborhood not in neighborhood_data:
                neighborhood_data[neighborhood] = {}
            
            if category not in neighborhood_data[neighborhood]:
                neighborhood_data[neighborhood][category] = []
            
            neighborhood_data[neighborhood][category].append(name)
        
        conn.close()
        return neighborhood_data
    except Exception as e:
        print(f"خطأ في قراءة الأماكن من قاعدة البيانات: {e}")
        return {}

def update_bot_data():
    """تحديث ملف البيانات للبوت"""
    try:
        routes_data = get_routes_from_db()
        neighborhood_data = get_neighborhoods_from_db()
        
        # كتابة البيانات في ملف data_dynamic.py
        with open('data_dynamic.py', 'w', encoding='utf-8') as f:
            f.write('# -*- coding: utf-8 -*-\n')
            f.write('"""\n')
            f.write('ملف البيانات المتغير - يتم تحديثه تلقائياً من قاعدة البيانات\n')
            f.write('"""\n\n')
            
            f.write('# بيانات الخطوط من قاعدة البيانات\n')
            f.write(f'routes_data = {repr(routes_data)}\n\n')
            
            f.write('# بيانات الأحياء من قاعدة البيانات\n')
            f.write(f'neighborhood_data = {repr(neighborhood_data)}\n')
        
        print("✅ تم تحديث بيانات البوت بنجاح!")
        return True
    except Exception as e:
        print(f"❌ خطأ في تحديث بيانات البوت: {e}")
        return False

if __name__ == "__main__":
    update_bot_data()