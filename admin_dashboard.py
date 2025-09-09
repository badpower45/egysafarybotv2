# -*- coding: utf-8 -*-
"""
Admin Dashboard للتحكم في بيانات البوت
"""

import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from data import routes_data, neighborhood_data

# إعداد Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///admin_bot.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# إضافة مرشح JSON للقوالب
@app.template_filter('from_json')
def from_json_filter(value):
    """تحويل JSON string إلى Python object"""
    try:
        return json.loads(value)
    except:
        return []

# Models قاعدة البيانات
class Location(db.Model):
    """جدول الأماكن والمعالم"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    neighborhood = db.Column(db.String(100), nullable=False)
    coordinates = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Location {self.name}>'

class Route(db.Model):
    """جدول الخطوط"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    fare = db.Column(db.Float, nullable=False)
    start_area = db.Column(db.String(200), nullable=True)
    end_area = db.Column(db.String(200), nullable=True)
    key_points = db.Column(db.Text, nullable=False)  # JSON string
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Route {self.name}>'

def init_database():
    """تهيئة قاعدة البيانات بالبيانات الحالية"""
    with app.app_context():
        db.create_all()
        
        # تحقق إذا كانت البيانات موجودة بالفعل
        if Location.query.count() == 0:
            print("🔄 جاري تحميل البيانات الحالية...")
            
            # إضافة الأماكن من neighborhood_data
            for neighborhood, categories in neighborhood_data.items():
                for category, locations in categories.items():
                    for location in locations:
                        # التعامل مع البيانات المعقدة
                        location_name = location
                        if isinstance(location, dict):
                            location_name = location.get('name', str(location))
                        
                        new_location = Location(
                            name=str(location_name),
                            category=str(category),
                            neighborhood=str(neighborhood)
                        )
                        db.session.add(new_location)
            
            # إضافة الخطوط من routes_data
            for route in routes_data:
                new_route = Route(
                    name=route['routeName'],
                    fare=float(route['fare'].split()[0]) if 'fare' in route else 4.5,
                    start_area=route.get('startArea', ''),
                    end_area=route.get('endArea', ''),
                    key_points=json.dumps(route['keyPoints'], ensure_ascii=False),
                    notes=route.get('notes', '')
                )
                db.session.add(new_route)
            
            db.session.commit()
            print("✅ تم تحميل البيانات بنجاح!")

# Routes الصفحات
@app.route('/')
def index():
    """الصفحة الرئيسية"""
    routes_count = Route.query.count()
    locations_count = Location.query.count()
    neighborhoods = db.session.query(Location.neighborhood.distinct()).all()
    
    return render_template('index.html', 
                         routes_count=routes_count,
                         locations_count=locations_count,
                         neighborhoods_count=len(neighborhoods))

@app.route('/routes')
def routes_list():
    """عرض جميع الخطوط"""
    routes = Route.query.order_by(Route.created_at.desc()).all()
    return render_template('routes_list.html', routes=routes)

@app.route('/routes/add', methods=['GET', 'POST'])
def add_route():
    """إضافة خط جديد"""
    if request.method == 'POST':
        name = request.form.get('name')
        fare = float(request.form.get('fare', 4.5))
        start_area = request.form.get('start_area', '')
        end_area = request.form.get('end_area', '')
        selected_locations = request.form.getlist('locations')
        notes = request.form.get('notes', '')
        
        # إنشاء الخط الجديد
        new_route = Route(
            name=name,
            fare=fare,
            start_area=start_area,
            end_area=end_area,
            key_points=json.dumps(selected_locations, ensure_ascii=False),
            notes=notes
        )
        
        db.session.add(new_route)
        db.session.commit()
        
        flash(f'تم إضافة الخط "{name}" بنجاح!', 'success')
        return redirect(url_for('routes_list'))
    
    # جلب جميع الأماكن مرتبة حسب الحي والتصنيف
    locations = Location.query.order_by(Location.neighborhood, Location.category, Location.name).all()
    neighborhoods = {}
    
    for location in locations:
        if location.neighborhood not in neighborhoods:
            neighborhoods[location.neighborhood] = {}
        if location.category not in neighborhoods[location.neighborhood]:
            neighborhoods[location.neighborhood][location.category] = []
        neighborhoods[location.neighborhood][location.category].append(location)
    
    return render_template('add_route.html', neighborhoods=neighborhoods)

@app.route('/locations')
def locations_list():
    """عرض جميع الأماكن"""
    locations = Location.query.order_by(Location.neighborhood, Location.category, Location.name).all()
    return render_template('locations_list.html', locations=locations)

@app.route('/locations/add', methods=['GET', 'POST'])
def add_location():
    """إضافة مكان جديد"""
    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        neighborhood = request.form.get('neighborhood')
        coordinates = request.form.get('coordinates', '')
        
        new_location = Location(
            name=name,
            category=category,
            neighborhood=neighborhood,
            coordinates=coordinates
        )
        
        db.session.add(new_location)
        db.session.commit()
        
        flash(f'تم إضافة المكان "{name}" بنجاح!', 'success')
        return redirect(url_for('locations_list'))
    
    # جلب الأحياء والتصنيفات الموجودة
    neighborhoods = db.session.query(Location.neighborhood.distinct()).all()
    categories = db.session.query(Location.category.distinct()).all()
    
    return render_template('add_location.html', 
                         neighborhoods=[n[0] for n in neighborhoods],
                         categories=[c[0] for c in categories])

@app.route('/api/export')
def export_data():
    """تصدير البيانات للبوت"""
    routes = Route.query.all()
    locations = Location.query.all()
    
    # تجهيز بيانات الخطوط
    routes_export = []
    for route in routes:
        routes_export.append({
            'routeName': route.name,
            'fare': f"{route.fare} جنيه مصري",
            'startArea': route.start_area,
            'endArea': route.end_area,
            'keyPoints': json.loads(route.key_points),
            'notes': route.notes
        })
    
    # تجهيز بيانات الأماكن
    neighborhoods_export = {}
    for location in locations:
        if location.neighborhood not in neighborhoods_export:
            neighborhoods_export[location.neighborhood] = {}
        if location.category not in neighborhoods_export[location.neighborhood]:
            neighborhoods_export[location.neighborhood][location.category] = []
        
        neighborhoods_export[location.neighborhood][location.category].append(location.name)
    
    return jsonify({
        'routes_data': routes_export,
        'neighborhood_data': neighborhoods_export
    })

@app.route('/api/update_bot')
def update_bot_data():
    """تحديث بيانات البوت"""
    try:
        from database_helper import update_bot_data
        success = update_bot_data()
        
        if success:
            flash('تم تحديث بيانات البوت بنجاح!', 'success')
            return jsonify({'status': 'success', 'message': 'تم تحديث البيانات بنجاح'})
        else:
            flash('حدث خطأ أثناء تحديث بيانات البوت', 'error')
            return jsonify({'status': 'error', 'message': 'فشل في تحديث البيانات'})
    except Exception as e:
        flash(f'خطأ: {str(e)}', 'error')
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    init_database()
    app.run(host='0.0.0.0', port=5000, debug=True)