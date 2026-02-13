from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlite3
import hashlib
import uuid
from datetime import datetime
import os
import base64

app = Flask(__name__, static_folder='.')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', max_http_buffer_size=10*1024*1024)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

DB_FILE = 'chat.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        avatar TEXT,
        status TEXT DEFAULT 'online',
        created_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS servers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        icon TEXT,
        owner TEXT NOT NULL,
        created_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS server_members (
        server_id TEXT,
        user_email TEXT,
        joined_at TEXT,
        PRIMARY KEY (server_id, user_email)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS channels (
        id TEXT PRIMARY KEY,
        server_id TEXT NOT NULL,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        created_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        server_id TEXT NOT NULL,
        channel_id TEXT NOT NULL,
        user_email TEXT NOT NULL,
        username TEXT NOT NULL,
        content TEXT NOT NULL,
        message_type TEXT DEFAULT 'text',
        timestamp TEXT NOT NULL
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS friends (
        user_email TEXT,
        friend_email TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        PRIMARY KEY (user_email, friend_email)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        email TEXT NOT NULL,
        created_at TEXT
    )''')
    
    c.execute("SELECT COUNT(*) FROM servers WHERE id='welcome'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO servers VALUES (?, ?, ?, ?, ?)",
                 ('welcome', 'Welcome Server', '🎮', 'system', datetime.now().isoformat()))
        c.execute("INSERT INTO channels VALUES (?, ?, ?, ?, ?)",
                 ('general', 'welcome', 'general', 'text', datetime.now().isoformat()))
        c.execute("INSERT INTO channels VALUES (?, ?, ?, ?, ?)",
                 ('voice', 'welcome', 'Voice Chat', 'voice', datetime.now().isoformat()))
    
    conn.commit()
    conn.close()

init_db()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    data = request.json
    email = data.get('email')
    username = data.get('username')
    password = data.get('password')
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
                 (email, username, hash_password(password), '', 'online', datetime.now().isoformat()))
        c.execute("INSERT INTO server_members VALUES (?, ?, ?)",
                 ('welcome', email, datetime.now().isoformat()))
        token = str(uuid.uuid4())
        c.execute("INSERT INTO sessions VALUES (?, ?, ?)",
                 (token, email, datetime.now().isoformat()))
        conn.commit()
        return jsonify({"success": True, "session_token": token, "user": {"email": email, "username": username}})
    except:
        return jsonify({"error": "Email or username taken"}), 400
    finally:
        conn.close()

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT username, password FROM users WHERE email=?", (data.get('email'),))
    result = c.fetchone()
    
    if result and result[1] == hash_password(data.get('password')):
        token = str(uuid.uuid4())
        c.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?, ?)",
                 (token, data.get('email'), datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "session_token": token, "user": {"email": data.get('email'), "username": result[0]}})
    
    conn.close()
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/auth/session/<token>')
def get_session(token):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT email FROM sessions WHERE token=?", (token,))
    result = c.fetchone()
    
    if result:
        c.execute("SELECT username, avatar, status FROM users WHERE email=?", (result[0],))
        user = c.fetchone()
        conn.close()
        return jsonify({"success": True, "user": {"email": result[0], "username": user[0], "avatar": user[1] or '', "status": user[2]}})
    
    conn.close()
    return jsonify({"error": "Invalid session"}), 404

@app.route('/api/servers/user/<email>')
def get_user_servers(email):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""SELECT s.id, s.name, s.icon FROM servers s
                 JOIN server_members sm ON s.id = sm.server_id
                 WHERE sm.user_email = ?""", (email,))
    servers = [{"id": r[0], "name": r[1], "icon": r[2]} for r in c.fetchall()]
    conn.close()
    return jsonify(servers)

@app.route('/api/servers/<server_id>/channels')
def get_channels(server_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, name, type FROM channels WHERE server_id=?", (server_id,))
    channels = [{"id": r[0], "name": r[1], "type": r[2]} for r in c.fetchall()]
    conn.close()
    return jsonify(channels)

@app.route('/api/messages/<server_id>/<channel_id>')
def get_messages(server_id, channel_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""SELECT id, username, content, message_type, timestamp FROM messages 
                 WHERE server_id=? AND channel_id=? ORDER BY timestamp ASC LIMIT 100""",
              (server_id, channel_id))
    messages = [{"id": r[0], "username": r[1], "content": r[2], "type": r[3], "timestamp": r[4]} for r in c.fetchall()]
    conn.close()
    return jsonify(messages)

@app.route('/api/messages/send', methods=['POST'])
def send_message():
    data = request.json
    msg_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
             (msg_id, data['server_id'], data['channel_id'], data['user_email'], 
              data['username'], data['content'], data.get('type', 'text'), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message_id": msg_id})

@app.route('/api/friends/<email>')
def get_friends(email):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""SELECT u.email, u.username, u.avatar, u.status FROM users u
                 JOIN friends f ON (u.email = f.friend_email)
                 WHERE f.user_email = ? AND f.status = 'accepted'""", (email,))
    friends = [{"email": r[0], "username": r[1], "avatar": r[2], "status": r[3]} for r in c.fetchall()]
    conn.close()
    return jsonify({"friends": friends})

@app.route('/api/friends/request', methods=['POST'])
def friend_request():
    data = request.json
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO friends VALUES (?, ?, ?, ?)",
                 (data['from_email'], data['to_email'], 'pending', datetime.now().isoformat()))
        conn.commit()
        return jsonify({"success": True})
    except:
        return jsonify({"error": "Request failed"}), 400
    finally:
        conn.close()

@app.route('/api/friends/accept', methods=['POST'])
def accept_friend():
    data = request.json
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE friends SET status='accepted' WHERE user_email=? AND friend_email=?",
             (data['from_email'], data['user_email']))
    c.execute("INSERT OR IGNORE INTO friends VALUES (?, ?, ?, ?)",
             (data['user_email'], data['from_email'], 'accepted', datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('join_chat')
def handle_join_chat(data):
    room = f"{data['server_id']}_{data['channel_id']}"
    join_room(room)

@socketio.on('send_message')
def handle_message(data):
    room = f"{data['server_id']}_{data['channel_id']}"
    emit('new_message', data, room=room)

@socketio.on('voice_join')
def handle_voice_join(data):
    room = f"{data['server_id']}_{data['channel_id']}"
    emit('user_joined_voice', {"user_email": data['user_email'], "username": data['username']}, room=room, include_self=False)

@socketio.on('voice_leave')
def handle_voice_leave(data):
    room = f"{data['server_id']}_{data['channel_id']}"
    emit('user_left_voice', {"user_email": data['user_email']}, room=room)

@socketio.on('webrtc_offer')
def handle_offer(data):
    emit('webrtc_offer', {"offer": data['offer'], "from_user": data['from_user']}, room=data['target'])

@socketio.on('webrtc_answer')
def handle_answer(data):
    emit('webrtc_answer', {"answer": data['answer'], "from_user": data['from_user']}, room=data['target'])

@socketio.on('ice_candidate')
def handle_ice(data):
    emit('ice_candidate', {"candidate": data['candidate'], "from_user": data['from_user']}, room=data['target'])

@socketio.on('typing')
def handle_typing(data):
    room = f"{data['server_id']}_{data['channel_id']}"
    emit('user_typing', {"username": data['username']}, room=room, include_self=False)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
