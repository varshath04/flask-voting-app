from flask import Flask, render_template, request, redirect, session, url_for, flash
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from pymongo import MongoClient
import bcrypt

app = Flask(__name__)
app.secret_key = 'supersecretkey'
client = MongoClient("mongodb+srv://flaskvotinguser:QevsWN3bxQJqMedI@voting-app.kitpt2k.mongodb.net/VotingDB?retryWrites=true&w=majority&appName=voting-app")
db = client["voting_app"]

# Collections
users = db.users
polls = db.polls
votes = db.votes

# Helper
def current_user():
    return session.get("username")

@app.route('/')
def home():
    return redirect(url_for('login'))

# ---------------- User Auth ----------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'].encode('utf-8')
        if users.find_one({'username': username}):
            flash("Username already exists!")
            return redirect(url_for('register'))
        hash_pw = bcrypt.hashpw(password, bcrypt.gensalt())
        users.insert_one({'username': username, 'password': hash_pw})
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        user = users.find_one({'username': username})
        if user and bcrypt.checkpw(request.form['password'].encode('utf-8'), user['password']):
            session['username'] = username
            return redirect(url_for('dashboard'))
        flash("Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------------- Dashboard ----------------

@app.route('/dashboard')
def dashboard():
    if not current_user():
        return redirect(url_for('login'))
    all_polls = list(polls.find())
    current_time = datetime.utcnow()
    for poll in all_polls:
        poll['_id'] = str(poll['_id'])  # Convert ObjectId to string
        poll['expired'] = current_time > poll['end_time']
        if poll['expired']:
            results = {opt: 0 for opt in poll['options']}
            for vote in votes.find({'poll_id': poll['_id']}):
                results[vote['option']] += 1
            poll['results'] = results
            max_votes = max(results.values())
            winners = [opt for opt, v in results.items() if v == max_votes]
            poll['winner'] = ", ".join(winners) if winners else "No votes"
        else:
            remaining_time = (poll['end_time'] - current_time).total_seconds()
            minutes, seconds = divmod(int(remaining_time), 60)
            poll['remaining'] = f"{minutes} minutes {seconds} seconds"
    return render_template('dashboard.html', polls=all_polls, username=current_user())

@app.route('/winner/<poll_id>')
def winner_page(poll_id):
    if not current_user():
        return redirect(url_for('login'))
    poll = polls.find_one({'_id': ObjectId(poll_id)})
    current_time = datetime.utcnow()
    if not poll:
        flash("Poll not found!")
        return redirect(url_for('dashboard'))
    poll['_id'] = str(poll['_id'])
    if current_time < poll['end_time']:
        flash("The poll is still live. Wait until the timer ends!")
        return redirect(url_for('dashboard'))
    results = {opt: 0 for opt in poll['options']}
    for vote in votes.find({'poll_id': poll['_id']}):
        results[vote['option']] += 1
    max_votes = max(results.values())
    winners = [opt for opt, v in results.items() if v == max_votes]
    winner = ", ".join(winners) if winners else "No votes"
    return render_template('winner.html', poll=poll, winner=winner, results=results)

# ---------------- Poll Management ----------------

@app.route('/create_poll', methods=['GET', 'POST'])
def create_poll():
    if not current_user():
        return redirect(url_for('login'))
    if request.method == 'POST':
        question = request.form['question']
        options = request.form.getlist('options')
        timer_minutes = int(request.form['timer'])
        end_time = datetime.utcnow() + timedelta(minutes=timer_minutes)
        polls.insert_one({
            'question': question,
            'options': options,
            'creator': current_user(),
            'end_time': end_time
        })
        flash("Poll created successfully!")
        return redirect(url_for('dashboard'))
    return render_template('create_poll.html')

@app.route('/delete_poll/<poll_id>')
def delete_poll(poll_id):
    poll = polls.find_one({'_id': ObjectId(poll_id)})
    if poll and poll['creator'] == current_user():
        polls.delete_one({'_id': ObjectId(poll_id)})
        votes.delete_many({'poll_id': poll_id})
        flash("Poll deleted successfully!")
    return redirect(url_for('dashboard'))

@app.route('/vote/<poll_id>', methods=['GET', 'POST'])
def vote(poll_id):
    if not current_user():
        return redirect(url_for('login'))
    poll = polls.find_one({'_id': ObjectId(poll_id)})
    if not poll:
        return redirect(url_for('dashboard'))
    poll['_id'] = str(poll['_id'])
    if votes.find_one({'poll_id': poll['_id'], 'username': current_user()}):
        flash("You cannot vote more than once in this poll!")
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        selected_option = request.form['option']
        votes.insert_one({
            'poll_id': poll['_id'],
            'username': current_user(),
            'option': selected_option
        })
        flash("Your vote has been recorded!")
        return redirect(url_for('dashboard'))
    return render_template('vote.html', poll=poll)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

