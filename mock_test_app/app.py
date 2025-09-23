from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, get_flashed_messages
import random
import fitz  # PyMuPDF
import re
import json
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this in production!

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

def load_users():
    if os.path.exists('users.json'):
        with open('users.json', 'r') as f:
            return json.load(f)
    return {}

def save_user(email, name, password):
    users = load_users()
    users[email] = {"name": name, "password": password}
    with open('users.json', 'w') as f:
        json.dump(users, f, indent=4)

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
        users = load_users()
        if email in users:
            return "User already exists. Try logging in."
        save_user(email, name, password)
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['POST'])
def do_login():
    email = request.form['email']
    password = request.form['password']
    users = load_users()
    user = users.get(email)
    if user and user['password'] == password:
        session['user'] = {"email": email, "name": user['name']}
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

    scores_file = "scores.json"
    if os.path.exists(scores_file):
        with open(scores_file, "r") as f:
            scores = json.load(f)
    else:
        scores = []

    scores.append(entry)

    with open(scores_file, "w") as f:
        json.dump(scores, f, indent=4)

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
        users = load_users()
        if email in users:
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
        users = load_users()
        users[email]['password'] = new_password
        with open('users.json', 'w') as f:
            json.dump(users, f, indent=4)

        session.pop('reset_email')
        flash("Password updated successfully. You can now login.")
        return redirect(url_for('login'))


    return render_template('reset_password.html')

# ---------------------------
# Run the App
# ---------------------------

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
