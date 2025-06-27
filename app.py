from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import os
from datetime import datetime

app = Flask(__name__)

# In-memory storage (replace with database in production)
feedback_data = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['GET', 'POST'])
def submit_feedback():
    if request.method == 'POST':
        feedback = {
            'id': len(feedback_data) + 1,
            'name': request.form.get('name', 'Anonymous'),
            'email': request.form.get('email', ''),
            'rating': int(request.form.get('rating', 0)),
            'category': request.form.get('category', 'General'),
            'message': request.form.get('message', ''),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        feedback_data.append(feedback)
        return render_template('submit.html', success=True)
    
    return render_template('submit.html')

@app.route('/view')
def view_feedback():
    return render_template('view.html', feedback_list=feedback_data)

@app.route('/api/feedback')
def api_feedback():
    return jsonify(feedback_data)

@app.route('/api/stats')
def api_stats():
    if not feedback_data:
        return jsonify({'total': 0, 'average_rating': 0})
    
    total = len(feedback_data)
    avg_rating = sum(f['rating'] for f in feedback_data) / total
    
    return jsonify({
        'total': total,
        'average_rating': round(avg_rating, 2)
    })

if __name__ == '__main__':
    app.run(debug=True)
