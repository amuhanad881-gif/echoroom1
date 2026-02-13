from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import sqlite3
import hashlib
import uuid
from datetime import datetime
import os

app = Flask(__name__, static_folder='.')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Database setup
DB_FILE = 'chat.db'

def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        avatar TEXT,
        bio TEXT,
        created_at TEXT
    )''')
    
    # Servers table
    c.execute('''CREATE TABLE IF NOT EXISTS servers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        owner TEXT NOT NULL,
        created_at TEXT
    )''')
    
    # Server members table
    c.execute('''CREATE TABLE IF NOT EXISTS server_members (
        server_id TEXT,
        user_email TEXT,
        joined_at TEXT,
        PRIMARY KEY (server_id, user_email)
    )''')
    
    # Channels table
    c.execute('''CREATE TABLE IF NOT EXISTS channels (
        id TEXT PRIMARY KEY,
        server_id TEXT NOT NULL,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        created_at TEXT
    )''')
    
    # Messages table
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        server_id TEXT NOT NULL,
        channel_id TEXT NOT NULL,
        user_email TEXT NOT NULL,
        username TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )''')
    
    # Friends table
    c.execute('''CREATE TABLE IF NOT EXISTS friends (
        user1 TEXT,
        user2 TEXT,
        status TEXT,
        created_at TEXT,
        PRIMARY KEY (user1, user2)
    )''')
    
    # Sessions table
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        email TEXT NOT NULL,
        created_at TEXT
    )''')
    
    # Create default server if not exists
    c.execute("SELECT COUNT(*) FROM servers WHERE id='welcome'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO servers VALUES (?, ?, ?, ?)",
                 ('welcome', 'Welcome Server', 'system', datetime.now().isoformat()))
        c.execute("INSERT INTO channels VALUES (?, ?, ?, ?, ?)",
                 ('general', 'welcome', 'general', 'text', datetime.now().isoformat()))
    
    conn.commit()
    conn.close()

init_db()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Routes
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# Auth
@app.route('/api/auth/signup', methods=['POST'])
def signup():
    data = request.json
    email = data.get('email')
    username = data.get('username')
    password = data.get('password')
    
    if not email or not username or not password:
        return jsonify({"error": "Missing fields"}), 400
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
                 (email, username, hash_password(password), '', '', datetime.now().isoformat()))
        
        # Add to welcome server
        c.execute("INSERT INTO server_members VALUES (?, ?, ?)",
                 ('welcome', email, datetime.now().isoformat()))
        
        # Create session
        token = str(uuid.uuid4())
        c.execute("INSERT INTO sessions VALUES (?, ?, ?)",
                 (token, email, datetime.now().isoformat()))
        
        conn.commit()
        
        return jsonify({
            "success": True,
            "session_token": token,
            "user": {"email": email, "username": username}
        })
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email or username already exists"}), 400
    finally:
        conn.close()

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT username, password FROM users WHERE email=?", (email,))
    result = c.fetchone()
    
    if result and result[1] == hash_password(password):
        token = str(uuid.uuid4())
        c.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?, ?)",
                 (token, email, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "session_token": token,
            "user": {"email": email, "username": result[0]}
        })
    
    conn.close()
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/auth/session/<token>')
def get_session(token):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT email FROM sessions WHERE token=?", (token,))
    result = c.fetchone()
    
    if result:
        email = result[0]
        c.execute("SELECT username, avatar, bio FROM users WHERE email=?", (email,))
        user = c.fetchone()
        conn.close()
        
        return jsonify({
            "success": True,
            "user": {
                "email": email,
                "username": user[0],
                "avatar": user[1] or '',
                "bio": user[2] or ''
            }
        })
    
    conn.close()
    return jsonify({"error": "Invalid session"}), 404

# Servers
@app.route('/api/servers/user/<email>')
def get_user_servers(email):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""
        SELECT s.id, s.name, s.owner 
        FROM servers s
        JOIN server_members sm ON s.id = sm.server_id
        WHERE sm.user_email = ?
    """, (email,))
    
    servers = [{"id": row[0], "name": row[1], "owner": row[2]} for row in c.fetchall()]
    conn.close()
    
    return jsonify(servers)

@app.route('/api/servers/<server_id>/channels')
def get_channels(server_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT id, name, type FROM channels WHERE server_id=?", (server_id,))
    channels = [{"id": row[0], "name": row[1], "type": row[2]} for row in c.fetchall()]
    
    conn.close()
    return jsonify(channels)

# Messages
@app.route('/api/messages/<server_id>/<channel_id>')
def get_messages(server_id, channel_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""
        SELECT id, username, content, timestamp 
        FROM messages 
        WHERE server_id=? AND channel_id=?
        ORDER BY timestamp ASC
        LIMIT 100
    """, (server_id, channel_id))
    
    messages = [{
        "id": row[0],
        "username": row[1],
        "content": row[2],
        "timestamp": row[3]
    } for row in c.fetchall()]
    
    conn.close()
    return jsonify(messages)

@app.route('/api/messages/send', methods=['POST'])
def send_message():
    data = request.json
    msg_id = str(uuid.uuid4())
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?)",
             (msg_id, data['server_id'], data['channel_id'], 
              data['user_email'], data['username'], data['content'],
              datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message_id": msg_id})

# SocketIO events
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('join_chat')
def handle_join_chat(data):
    room = f"{data['server_id']}_{data['channel_id']}"
    join_room(room)
    emit('user_joined', {"username": data['username']}, room=room, include_self=False)

@socketio.on('send_message')
def handle_message(data):
    room = f"{data['server_id']}_{data['channel_id']}"
    emit('new_message', data, room=room)

@socketio.on('voice_join')
def handle_voice_join(data):
    room = f"{data['server_id']}_{data['channel_id']}"
    emit('user_joined_voice', {
        "user_email": data['user_email'],
        "username": data['username']
    }, room=room, include_self=False)

@socketio.on('voice_leave')
def handle_voice_leave(data):
    room = f"{data['server_id']}_{data['channel_id']}"
    emit('user_left_voice', {"user_email": data['user_email']}, room=room)

# WebRTC signaling
@socketio.on('webrtc_offer')
def handle_offer(data):
    emit('webrtc_offer', {
        "offer": data['offer'],
        "from_user": data['from_user']
    }, room=data['target'])

@socketio.on('webrtc_answer')
def handle_answer(data):
    emit('webrtc_answer', {
        "answer": data['answer'],
        "from_user": data['from_user']
    }, room=data['target'])

@socketio.on('ice_candidate')
def handle_ice(data):
    emit('ice_candidate', {
        "candidate": data['candidate'],
        "from_user": data['from_user']
    }, room=data['target'])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
