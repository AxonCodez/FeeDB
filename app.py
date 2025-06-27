from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_file
import json, os, csv
from datetime import datetime
from functools import wraps
from io import StringIO

app = Flask(__name__)
app.secret_key = 'your-secret-key'

STUDENTS_FILE = 'data/students.json'
TEACHERS_FILE = 'data/teachers.json'
FEEDBACK_FILE = 'data/feedback.json'
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"

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
    for code in assigned:
        if code in teachers:
            info = teachers[code]
            info['code'] = code
            info['feedback_submitted'] = any(f['student_id'] == sid and f['teacher_code'] == code for f in feedback)
            teacher_details.append(info)
    return render_template("dashboard.html", teachers=teacher_details)

@app.route('/feedback/<teacher_code>', methods=['GET', 'POST'])
@login_required
def submit_feedback(teacher_code):
    students = load_data(STUDENTS_FILE)
    teachers = load_data(TEACHERS_FILE)
    feedback = load_data(FEEDBACK_FILE)
    sid = session['student_id']

    if teacher_code not in students[sid]['teachers']:
        flash("You are not authorized to give feedback")
        return redirect(url_for('dashboard'))

    if any(f['student_id'] == sid and f['teacher_code'] == teacher_code for f in feedback):
        flash("Feedback already submitted")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        responses = {f'q{i}': int(request.form[f'q{i}']) for i in range(1, 21)}
        feedback.append({
            'id': len(feedback) + 1,
            'student_id': sid,
            'teacher_code': teacher_code,
            'responses': responses,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
        flash("Invalid admin credentials")
    return '''<form method="POST">
                <input name="username" placeholder="Username"><br>
                <input name="password" placeholder="Password" type="password"><br>
                <button type="submit">Login</button>
              </form>'''

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    feedback = load_data(FEEDBACK_FILE)
    teachers = load_data(TEACHERS_FILE)
    stats = {}
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
    return render_template('admin.html', stats=stats)

@app.route('/admin/feedbacks')
@admin_required
def all_feedbacks():
    feedback = load_data(FEEDBACK_FILE)
    students = load_data(STUDENTS_FILE)
    teachers = load_data(TEACHERS_FILE)
    for fb in feedback:
        fb['student_name'] = students.get(fb['student_id'], {}).get('name', 'Unknown')
        fb['teacher_name'] = teachers.get(fb['teacher_code'], {}).get('name', 'Unknown')
    return render_template('admin_feedbacks.html', feedbacks=feedback)

@app.route('/admin/export')
@admin_required
def export_csv():
    feedback = load_data(FEEDBACK_FILE)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Student ID', 'Teacher Code', 'Timestamp'] + [f'Q{i}' for i in range(1, 21)])
    for f in feedback:
        row = [f['id'], f['student_id'], f['teacher_code'], f['timestamp']] + [f['responses'].get(f'q{i}', '') for i in range(1, 21)]
        writer.writerow(row)
    output.seek(0)
    return send_file(output, mimetype='text/csv', download_name='feedback_export.csv', as_attachment=True)

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
