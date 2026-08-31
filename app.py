from flask import Flask, render_template, request, redirect, url_for, flash
from models.user_log import db, MasterCatalog, MySyllabus, DailyLog
import joblib
import os
import pandas as pd
import threading
import webbrowser
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_flash_messages' # Required for error tracking notifications

# 1. Database Configuration
db_path = os.path.join(os.getcwd(), 'study_companion.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# 2. Load the AI Model securely
model_path = os.path.join(os.getcwd(), 'xgboost_v1.pkl')
if os.path.exists(model_path):
    ai_model = joblib.load(model_path)
else:
    ai_model = None
    print("⚠️ WARNING: xgboost_v1.pkl not found. App running in Heuristic-Only safety fallback mode.")

# --- HELPER LOGIC ---
def generate_tasks(mode_label):
    # Mapping numbers back to text labels
    mode_map = {0: "Recovery", 1: "Revision", 2: "Standard", 3: "Deep Work"}
    mode_text = mode_map.get(mode_label, "Standard")
    
    if mode_text == "Deep Work":
        topics = MySyllabus.query.filter_by(status='Pending').limit(2).all()
        if not topics:
            topics = MySyllabus.query.limit(2).all() # Fallback if none are Pending
        tasks = [f"🚀 {t.catalog_item.topic_name}: Deep dive for 2 hours." for t in topics if t.catalog_item]
        return "New topic learning recommended", tasks if tasks else ["🚀 Advance your selected subjects for 2 hours!"], "success"
        
    elif mode_text == "Recovery":
        tasks = ["🧘 Light review for 30 mins. Focus on rest today."]
        return "Recovery and light rest recommended", tasks, "warning"
        
    elif mode_text == "Revision":
        topic = MySyllabus.query.filter_by(status='Completed').first()
        if not topic:
            topic = MySyllabus.query.first()
        topic_name = topic.catalog_item.topic_name if (topic and topic.catalog_item) else "Recent Topics"
        tasks = [f"🔄 {topic_name}: Revise critical concepts and flashcards for 45 mins."]
        return "Light revision and practice recommended", tasks, "info"
        
    else:  # Standard
        topic = MySyllabus.query.filter_by(status='Pending').first()
        if not topic:
            topic = MySyllabus.query.first()
        topic_name = topic.catalog_item.topic_name if (topic and topic.catalog_item) else "General Engineering Studies"
        tasks = [f"📚 {topic_name}: Standard study session (1.5 hours)."]
        return "Balanced study day", tasks, "primary"


# --- WEB ROUTES ---

@app.route('/')
def dashboard():
    """The Main Screen tracking daily study engine parameters."""
    # Break out of the loop defensively: check if Master Catalog is empty first
    if MasterCatalog.query.count() == 0:
        print("💡 Database is completely raw. Redirecting to onboarding to allow initial data pass.")
        return redirect(url_for('onboarding'))

    # If the user has zero custom subjects tracking, route directly to setup
    if MySyllabus.query.count() == 0:
        return redirect(url_for('onboarding'))
    
    # Query today's log entry using local date format
    today_date = datetime.utcnow().date()
    today_log = DailyLog.query.filter_by(date=today_date).first()
    
    if not today_log:
        return render_template('index.html', needs_checkin=True)
    
    # Convert saved text parameter or classification int back into integer safe format
    try:
        mode_val = int(today_log.xgboost_mode_label)
    except ValueError:
        mode_val = 2 # Default fallback to 'Standard' if string corruption occurs

    banner, tasks, color = generate_tasks(mode_val)
    return render_template('index.html', needs_checkin=False, log=today_log, banner=banner, tasks=tasks, color=color)


@app.route('/submit_checkin', methods=['POST'])
def submit_checkin():
    """Handles the morning metric validation form submission."""
    try:
        sleep = float(request.form['sleep'])
        quality = True if request.form.get('quality', 'Good') == 'Good' else False
        energy = int(request.form['energy'])
        quiz = int(request.form['quiz'])
        exam_days = int(request.form['exam_days'])
        
        # Format exact dataframe vector shape matching training notebook properties
        input_data = pd.DataFrame([[sleep, energy, exam_days, quiz]], 
                                  columns=['sleep_hours', 'energy_level', 'days_to_exam', 'quiz_score'])
        
        # Smart Prediction Fallback Layer
        if ai_model:
            predicted_mode = ai_model.predict(input_data)[0]
        else:
            # Algorithmic fallback rule matching notebook thresholds
            if energy <= 2 or sleep < 5:
                predicted_mode = 0  # Recovery
            elif quiz < 60:
                predicted_mode = 1  # Revision
            elif energy >= 4 and exam_days > 7:
                predicted_mode = 3  # Deep Work
            else:
                predicted_mode = 2  # Standard
        
        # Avoid duplicate primary key log drops if page refreshed on same calendar date
        today_date = datetime.utcnow().date()
        existing_log = DailyLog.query.filter_by(date=today_date).first()
        if existing_log:
            db.session.delete(existing_log)

        new_log = DailyLog(
            date=today_date,
            sleep_hours=sleep,
            sleep_quality_flag=quality,
            difficulty_rating_prev=3, 
            quiz_score=quiz,
            days_to_exam=exam_days,
            energy_level=energy,
            xgboost_mode_label=str(predicted_mode),
            actual_plan_heuristic="Generated dynamically via integrated pipeline"
        )
        db.session.add(new_log)
        db.session.commit()
        
    except Exception as e:
        print(f"❌ Error during state optimization calculation: {str(e)}")
        
    return redirect(url_for('dashboard'))


@app.route('/reset', methods=['POST'])
def reset_checkin():
    """Remove today's check-in so the dashboard shows the form again."""
    with app.app_context():
        db.create_all()
        today_date = datetime.utcnow().date()
        today_log = DailyLog.query.filter_by(date=today_date).first()
        if today_log:
            db.session.delete(today_log)
            db.session.commit()

    return redirect(url_for('dashboard'))


@app.route('/onboarding', methods=['GET', 'POST'])
def onboarding():
    if request.method == 'POST':
        selected_subjects = request.form.getlist('subjects')
        print(f"👉 Form processing activation. Subjects chosen: {selected_subjects}")
        
        # Critical Fallback Protection Layer: If database master data was wiped, reconstruct on the fly
        if MasterCatalog.query.count() == 0:
            print("🚨 Master Catalog is empty! Injecting baseline operational records.")
            core_btech_data = [
                ('DBMS', 'Normalization', 'Theory'),
                ('DBMS', 'SQL Joins', 'Coding'),
                ('DSA', 'Binary Search Trees', 'Coding'),
                ('DSA', 'Asymptotic Notation', 'Theory'),
                ('OS', 'Process Scheduling', 'Theory')
            ]
            for sub, top, cat in core_btech_data:
                db.session.add(MasterCatalog(subject_name=sub, topic_name=top, category=cat))
            db.session.commit()

        # Allocate catalog tracks down to custom target profiles
        items_added_count = 0
        for sub in selected_subjects:
            topics = MasterCatalog.query.filter_by(subject_name=sub).all()
            for t in topics:
                if not MySyllabus.query.filter_by(catalog_id=t.catalog_id).first():
                    db.session.add(MySyllabus(catalog_id=t.catalog_id, status='Pending', priority='Medium'))
                    items_added_count += 1
        
        db.session.commit()
        print(f"🏁 System Commit Executed. Successfully loaded {items_added_count} records into MySyllabus.")
        return redirect(url_for('dashboard'))

    # GET REQUEST: Compile and process safe list profiles
    # Safety Check: Guarantee structural subjects show up on layout even on raw database initialize steps
    if MasterCatalog.query.count() == 0:
        print("🌱 Pre-seeding catalog to render checkbox components on screen layout views.")
        fallback_subjects = [
            ('DBMS', 'Normalization', 'Theory'), ('DBMS', 'SQL Joins', 'Coding'),
            ('DSA', 'Binary Search Trees', 'Coding'), ('OS', 'Process Scheduling', 'Theory')
        ]
        for sub, top, cat in fallback_subjects:
            db.session.add(MasterCatalog(subject_name=sub, topic_name=top, category=cat))
        db.session.commit()

    available_subjects = db.session.query(MasterCatalog.subject_name).distinct().all()
    subject_list = [s[0] for s in available_subjects]
    return render_template('onboarding.html', subjects=subject_list)


if __name__ == '__main__':
    with app.app_context():
        db.create_all() 
        print("⚙️ SQLite storage schema verified and online.")

    # Open the dashboard once the Flask development server is ready. The
    # reloader starts a second process, so only the serving process opens it.
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        threading.Timer(1.0, lambda: webbrowser.open_new('http://127.0.0.1:5000/')).start()

    app.run(debug=True)