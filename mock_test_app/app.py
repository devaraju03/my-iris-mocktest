from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import random
import fitz  # PyMuPDF
import re
import os
from pymongo import MongoClient

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this in production!

# ---------------------------
# MongoDB Setup
# ---------------------------

client = MongoClient(MONGO_URL)
db = client["mocktest"]  # Database name
users_col = db["users"]
scores_col = db["scores"]

# ---------------------------
# Utility Functions
# ---------------------------

def extract_questions_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    question_blocks = re.split(r'\n\d+\.\s+', full_text)[1:]

    questions = []
    for block in question_blocks:
        lines = block.strip().split('\n')
        if len(lines) < 5:
            continue
        q_text = lines[0].strip()
        options = [line.strip()[2:] for line in lines[1:5]]  # Strip A. B. etc.
        answer_line = [line for line in lines if "Answer" in line]
        if not answer_line:
            continue
        correct_letter = answer_line[0].split(":")[-1].strip().upper()
        idx = {"A": 0, "B": 1, "C": 2, "D": 3}.get(correct_letter, -1)
        if idx == -1 or idx >= len(options):
            continue
        questions.append({
            "question": q_text,
            "options": options,
            "answer": options[idx]
        })

    return questions

# ---------------------------
# Routes
# ---------------------------

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Check if user already exists
        if users_col.find_one({"email": email}):
            return "User already exists. Try logging in."

        users_col.insert_one({"name": name, "email": email, "password": password})
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['POST'])
def do_login():
    email = request.form['email']
    password = request.form['password']

    user = users_col.find_one({"email": email})
    if user and user['password'] == password:
        session['user'] = {"email": user['email'], "name": user['name']}
        return redirect(url_for('quiz'))

    return "Invalid credentials. Try again."

@app.route('/quiz')
def quiz():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('quiz.html', user=session['user'])

@app.route('/get_questions')
def get_questions():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    all_questions = extract_questions_from_pdf("questions.pdf")
    selected = random.sample(all_questions, min(10, len(all_questions)))
    return jsonify(selected)

@app.route('/save_score', methods=['POST'])
def save_score():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    entry = {
        "name": session['user']['name'],
        "email": session['user']['email'],
        "score": data.get("score"),
        "total": data.get("total")
    }

    scores_col.insert_one(entry)

    return jsonify({"status": "success", "message": "Score saved!"})

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# ---------------------------
# Forgot Password Flow
# ---------------------------

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = users_col.find_one({"email": email})
        if user:
            session['reset_email'] = email
            return redirect(url_for('reset_password'))
        else:
            return "Email not found. Please try again."
    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_email' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form['password']
        confirm_password = request.form['confirm_password']

        if new_password != confirm_password:
            return "Passwords do not match. Try again."

        email = session['reset_email']
        users_col.update_one({"email": email}, {"$set": {"password": new_password}})

        session.pop('reset_email')
        flash("Password updated successfully. You can now login.")
        return redirect(url_for('login'))

    return render_template('reset_password.html')

# ---------------------------
# Run the App
# ---------------------------

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

