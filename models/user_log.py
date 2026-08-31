from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize the SQLAlchemy instance (app.py will bind this to your Flask app)
db = SQLAlchemy()

class MasterCatalog(db.Model):
    __tablename__ = 'master_catalog'
    catalog_id = db.Column(db.Integer, primary_key=True)
    subject_name = db.Column(db.String(100), nullable=False)
    topic_name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)

    # This creates the relationship so we can pull the topic name from the catalog
    syllabus_links = db.relationship('MySyllabus', backref='catalog_item', lazy=True)

class MySyllabus(db.Model):
    __tablename__ = 'my_syllabus'
    id = db.Column(db.Integer, primary_key=True)
    catalog_id = db.Column(db.Integer, db.ForeignKey('master_catalog.catalog_id'), nullable=False)
    status = db.Column(db.String(50), default='Pending')
    priority = db.Column(db.String(50), default='Medium')

class DailyLog(db.Model):
    __tablename__ = 'daily_logs'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.utcnow().date, unique=True, nullable=False)
    
    # Morning Check-in Inputs
    sleep_hours = db.Column(db.Float, nullable=False)
    sleep_quality_flag = db.Column(db.Boolean, nullable=False)
    difficulty_rating_prev = db.Column(db.Integer, nullable=False)
    quiz_score = db.Column(db.Integer, nullable=False)
    days_to_exam = db.Column(db.Integer, nullable=False)
    energy_level = db.Column(db.Integer, nullable=False)
    
    # AI Outputs
    xgboost_mode_label = db.Column(db.String(50), nullable=False)
    actual_plan_heuristic = db.Column(db.Text, nullable=False)