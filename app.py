from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_file
import json, os, csv
from datetime import datetime
from functools import wraps
from io import StringIO, BytesIO

app = Flask(__name__)
app.secret_key = 'your-secret-key'

STUDENTS_FILE = 'data/students.json'
TEACHERS_FILE = 'data/teachers.json'
FEEDBACK_FILE = 'data/feedback.json'
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"
PHASES_FILE = 'data/phases.json'

def init_data_files():
    os.makedirs('data', exist_ok=True)
    if not os.path.exists(STUDENTS_FILE):
        with open(STUDENTS_FILE, 'w') as f:
            json.dump({}, f)
    if not os.path.exists(TEACHERS_FILE):
        with open(TEACHERS_FILE, 'w') as f:
            json.dump({}, f)
    if not os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, 'w') as f:
            json.dump([], f)

def load_data(file): return json.load(open(file)) if os.path.exists(file) else {}
def save_data(file, data): json.dump(data, open(file, 'w'), indent=2)

def load_phases():
    try:
        with open(PHASES_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"phases": {}, "current_phase": None}

def save_phases(data):
    with open(PHASES_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'student_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_logged_in' not in session: return redirect(url_for('admin'))
        return f(*args, **kwargs)
    return decorated

init_data_files()

@app.route('/')
def index():
    if 'student_id' in session: return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        sid, pwd = request.form.get('student_id'), request.form.get('password')
        students = load_data(STUDENTS_FILE)
        if sid in students and students[sid]['password'] == pwd:
            session.update({'student_id': sid, 'student_name': students[sid]['name'], 'student_class': students[sid]['class']})
            return redirect(url_for('dashboard'))
        flash("Invalid credentials")
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    students, teachers, feedback = load_data(STUDENTS_FILE), load_data(TEACHERS_FILE), load_data(FEEDBACK_FILE)
    sid = session['student_id']
    assigned = students[sid]['teachers']
    teacher_details = []
    phases = load_phases()
    current_phase = phases.get("current_phase")

    for code in assigned:
        if code in teachers:
            info = teachers[code].copy()
            info['code'] = code
            info['feedback_submitted'] = any(
                f['student_id'] == sid and f['teacher_code'] == code and f.get('phase') == current_phase for f in feedback
            )
            teacher_details.append(info)

    return render_template("dashboard.html", teachers=teacher_details, current_phase=current_phase)


@app.route('/feedback/<teacher_code>', methods=['GET', 'POST'])
@login_required
def submit_feedback(teacher_code):
    students = load_data(STUDENTS_FILE)
    teachers = load_data(TEACHERS_FILE)
    feedback = load_data(FEEDBACK_FILE)
    phases = load_phases()
    current_phase = phases.get("current_phase")

    if not current_phase:
        flash("No active feedback phase. Please try later.", "error")
        return redirect(url_for('dashboard'))

    sid = session['student_id']

    if teacher_code not in students[sid]['teachers']:
        flash("You are not authorized to give feedback")
        return redirect(url_for('dashboard'))

    # Restrict: only allow one feedback per phase per teacher
    if any(f['student_id'] == sid and f['teacher_code'] == teacher_code and f.get('phase') == current_phase for f in feedback):
        flash("Feedback already submitted for this phase")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        responses = {f'q{i}': int(request.form[f'q{i}']) for i in range(1, 21)}
        feedback.append({
            'id': len(feedback) + 1,
            'student_id': sid,
            'teacher_code': teacher_code,
            'responses': responses,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'phase': current_phase
        })
        save_data(FEEDBACK_FILE, feedback)
        flash("Feedback submitted")
        return redirect(url_for('dashboard'))

    return render_template("feedback.html", teacher=teachers.get(teacher_code, {}), teacher_code=teacher_code)

@app.route('/view_feedback')
@login_required
def view_feedback():
    feedback = load_data(FEEDBACK_FILE)
    teachers = load_data(TEACHERS_FILE)
    sid = session['student_id']
    student_feedback = [f for f in feedback if f['student_id'] == sid]
    for f in student_feedback:
        tcode = f['teacher_code']
        if tcode in teachers:
            f['teacher_name'] = teachers[tcode]['name']
            f['subject'] = teachers[tcode]['subject']
    return render_template('view_feedback.html', feedback_list=student_feedback)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USERNAME and request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash("Invalid admin credentials", "danger")
    return render_template("admin_login.html")

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    feedback = load_data(FEEDBACK_FILE)
    teachers = load_data(TEACHERS_FILE)
    stats = {}
    phases = load_phases()
    current_phase = phases.get('current_phase')

    for code, info in teachers.items():
        entries = [f for f in feedback if f['teacher_code'] == code]
        if entries:
            avg = {f'q{i}': sum(f['responses'].get(f'q{i}', 0) for f in entries)/len(entries) for i in range(1, 21)}
            stats[code] = {
                'name': info['name'],
                'subject': info['subject'],
                'total_responses': len(entries),
                'overall_average': round(sum(avg.values())/20, 2),
                'detailed_ratings': avg
            }
    return render_template('admin.html', stats=stats, current_phase=current_phase)


@app.route('/admin/feedbacks')
@admin_required
def all_feedbacks():
    sort_by = request.args.get('sort', 'time')
    filter_value = request.args.get('filter', '').strip()

    feedback = load_data(FEEDBACK_FILE)
    students = load_data(STUDENTS_FILE)
    teachers = load_data(TEACHERS_FILE)

    for fb in feedback:
        sid = fb['student_id']
        tcode = fb['teacher_code']
        fb['student_name'] = students.get(sid, {}).get('name', 'Unknown')
        fb['student_class'] = students.get(sid, {}).get('class', 'N/A')
        fb['teacher_name'] = teachers.get(tcode, {}).get('name', 'Unknown')
        fb['phase'] = fb.get('phase', 'N/A')

    if sort_by == 'student' and filter_value:
        feedback = [f for f in feedback if f['student_id'] == filter_value]
    elif sort_by == 'teacher' and filter_value:
        feedback = [f for f in feedback if f['teacher_code'] == filter_value]
    elif sort_by == 'phase' and filter_value:
        feedback = [f for f in feedback if f.get('phase') == filter_value]
    elif sort_by == 'class' and filter_value:
        feedback = [f for f in feedback if students.get(f['student_id'], {}).get('class') == filter_value]

    if sort_by == 'student':
        feedback.sort(key=lambda f: f['student_name'])
    elif sort_by == 'teacher':
        feedback.sort(key=lambda f: f['teacher_name'])
    elif sort_by == 'phase':
        feedback.sort(key=lambda f: f['phase'])
    elif sort_by == 'class':
        feedback.sort(key=lambda f: f['student_class'])
    else:
        feedback.sort(key=lambda f: f['timestamp'], reverse=True)

    all_phases = sorted(set(f.get('phase', 'N/A') for f in feedback if f.get('phase')))
    all_classes = sorted(set(students.get(f['student_id'], {}).get('class', 'N/A') for f in feedback))

    return render_template(
        'admin_feedbacks.html',
        feedbacks=feedback,
        sort_by=sort_by,
        filter_value=filter_value,
        student_list=students,
        teacher_list=teachers,
        all_phases=all_phases,
        all_classes=all_classes
    )


@app.route('/admin/export')
@admin_required
def export_csv():
    feedback = load_data(FEEDBACK_FILE)
    students = load_data(STUDENTS_FILE)

    # Step 1: Write to StringIO (text)
    text_stream = StringIO()
    writer = csv.writer(text_stream)
    writer.writerow(['ID', 'Student ID', 'Teacher Code', 'Timestamp', 'Phase', 'Class'] + [f'Q{i}' for i in range(1, 21)])

    for f in feedback:
        sid = f['student_id']
        row = [
            f['id'], sid, f['teacher_code'], f['timestamp'],
            f.get('phase', 'N/A'),
            students.get(sid, {}).get('class', 'N/A')
        ] + [f['responses'].get(f'q{i}', '') for i in range(1, 21)]
        writer.writerow(row)

    # Step 2: Convert to bytes for sending
    text_stream.seek(0)
    byte_stream = BytesIO(text_stream.getvalue().encode('utf-8'))

    return send_file(
        byte_stream,
        mimetype='text/csv',
        download_name='feedback_export.csv',
        as_attachment=True
    )
    
@app.route('/admin/manage-teachers', methods=['GET', 'POST'])
@admin_required
def manage_teachers():
    teachers = load_data(TEACHERS_FILE)
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        subject = request.form.get('subject')
        action = request.form.get('action')
        if action == 'add' and code and name and subject:
            teachers[code] = {'name': name, 'subject': subject}
        elif action == 'delete' and code in teachers:
            del teachers[code]
        save_data(TEACHERS_FILE, teachers)
        return redirect(url_for('manage_teachers'))
    return render_template('admin_manage_teachers.html', teachers=teachers)

@app.route('/admin/phases', methods=['GET', 'POST'])
@admin_required
def manage_phases():
    phases_data = load_phases()
    if request.method == 'POST':
        action = request.form.get('action')
        phase_name = request.form.get('phase_name')

        if action == 'create' and phase_name:
            phases_data['phases'][phase_name] = 'closed'
        elif action == 'activate' and phase_name in phases_data['phases']:
            for p in phases_data['phases']:
                phases_data['phases'][p] = 'closed'
            phases_data['phases'][phase_name] = 'active'
            phases_data['current_phase'] = phase_name
        elif action == 'end' and phase_name in phases_data['phases']:
            phases_data['phases'][phase_name] = 'closed'
            if phases_data['current_phase'] == phase_name:
                phases_data['current_phase'] = None

        save_phases(phases_data)
        return redirect(url_for('manage_phases'))

    return render_template('admin_phases.html', phases=phases_data.get('phases', {}), current_phase=phases_data.get('current_phase'))

@app.route('/admin/manage-students', methods=['GET', 'POST'])
@admin_required
def manage_students():
    students = load_data(STUDENTS_FILE)
    teachers = load_data(TEACHERS_FILE)
    if request.method == 'POST':
        sid = request.form.get('student_id')
        name = request.form.get('name')
        password = request.form.get('password')
        student_class = request.form.get('student_class')
        assigned_teachers = request.form.getlist('teachers')
        action = request.form.get('action')
        if action == 'add' and sid and name and password:
            students[sid] = {
                'name': name,
                'password': password,
                'class': student_class,
                'teachers': assigned_teachers
            }
        elif action == 'delete' and sid in students:
            del students[sid]
        save_data(STUDENTS_FILE, students)
        return redirect(url_for('manage_students'))
    return render_template('admin_manage_students.html', students=students, teachers=teachers)

@app.route('/admin/logout')
@admin_required
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)
