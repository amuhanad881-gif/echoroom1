from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
import json
import os
from datetime import datetime
import uuid
import hashlib

app = Flask(__name__, static_folder='.')
# Configure SocketIO without eventlet
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', ping_timeout=60, ping_interval=25)

# Add CORS headers manually
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Simple file-based database
DATA_DIR = 'data'
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
MESSAGES_FILE = os.path.join(DATA_DIR, 'messages.json')
SERVERS_FILE = os.path.join(DATA_DIR, 'servers.json')
CHANNELS_FILE = os.path.join(DATA_DIR, 'channels.json')
FRIENDS_FILE = os.path.join(DATA_DIR, 'friends.json')
EMOJIS_FILE = os.path.join(DATA_DIR, 'emojis.json')
SESSIONS_FILE = os.path.join(DATA_DIR, 'sessions.json')

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize data files
def init_data_files():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump({}, f)
    
    if not os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, 'w') as f:
            json.dump({}, f)
    
    if not os.path.exists(SERVERS_FILE):
        default_servers = {
            "welcome-server": {
                "id": "welcome-server",
                "name": "Welcome Server",
                "owner": "system",
                "icon": "🎮",
                "created_at": datetime.now().isoformat(),
                "members": []
            }
        }
        with open(SERVERS_FILE, 'w') as f:
            json.dump(default_servers, f)
    
    if not os.path.exists(CHANNELS_FILE):
        default_channels = {
            "welcome-server": {
                "general": {
                    "id": "general",
                    "name": "General",
                    "type": "text",
                    "server_id": "welcome-server",
                    "created_at": datetime.now().isoformat()
                },
                "voice-general": {
                    "id": "voice-general",
                    "name": "Voice Chat",
                    "type": "voice",
                    "server_id": "welcome-server",
                    "created_at": datetime.now().isoformat()
                }
            }
        }
        with open(CHANNELS_FILE, 'w') as f:
            json.dump(default_channels, f)
    
    if not os.path.exists(FRIENDS_FILE):
        with open(FRIENDS_FILE, 'w') as f:
            json.dump({}, f)
    
    if not os.path.exists(EMOJIS_FILE):
        default_emojis = {
            "smile": "😊",
            "laugh": "😂",
            "heart": "❤️",
            "thumbsup": "👍",
            "rocket": "🚀"
        }
        with open(EMOJIS_FILE, 'w') as f:
            json.dump(default_emojis, f)
    
    if not os.path.exists(SESSIONS_FILE):
        with open(SESSIONS_FILE, 'w') as f:
            json.dump({}, f)

init_data_files()

# Helper functions
def read_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Routes
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

# Session endpoints
@app.route('/api/auth/session', methods=['POST', 'OPTIONS'])
def save_session():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.json
        email = data.get('email')
        session_token = data.get('session_token')
        
        sessions = read_json(SESSIONS_FILE)
        sessions[session_token] = {
            "email": email,
            "created_at": datetime.now().isoformat()
        }
        write_json(SESSIONS_FILE, sessions)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/session/<token>', methods=['GET', 'OPTIONS'])
def get_session(token):
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        sessions = read_json(SESSIONS_FILE)
        if token in sessions:
            email = sessions[token]["email"]
            users = read_json(USERS_FILE)
            if email in users:
                return jsonify({
                    "success": True,
                    "user": {
                        "email": email,
                        "username": users[email].get('username', email.split('@')[0]),
                        "avatar": users[email].get('avatar', ''),
                        "bio": users[email].get('bio', ''),
                        "custom_status": users[email].get('custom_status', ''),
                        "joined_servers": users[email].get('joined_servers', [])
                    }
                })
        return jsonify({"error": "Session not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Auth endpoints
@app.route('/api/auth/signup', methods=['POST', 'OPTIONS'])
def signup():
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        username = data.get('username')
        bio = data.get('bio', '')
        
        if not email or not password or not username:
            return jsonify({"error": "Missing required fields"}), 400
        
        users = read_json(USERS_FILE)
        
        # Check if email already exists
        if email in users:
            return jsonify({"error": "Email already registered"}), 400
        
        # Check if username already exists
        for user_email, user_data in users.items():
            if user_data.get('username') == username:
                return jsonify({"error": "Username already taken"}), 400
        
        # Create new user
        new_user = {
            "email": email,
            "password": hash_password(password),
            "username": username,
            "avatar": "",
            "bio": bio,
            "custom_status": "",
            "joined_servers": ["welcome-server"],
            "created_at": datetime.now().isoformat()
        }
        users[email] = new_user
        write_json(USERS_FILE, users)
        
        # Add user to welcome server
        servers = read_json(SERVERS_FILE)
        if "welcome-server" in servers:
            if "members" not in servers["welcome-server"]:
                servers["welcome-server"]["members"] = []
            if email not in servers["welcome-server"]["members"]:
                servers["welcome-server"]["members"].append(email)
            write_json(SERVERS_FILE, servers)
        
        # Create session token
        session_token = str(uuid.uuid4())
        sessions = read_json(SESSIONS_FILE)
        sessions[session_token] = {
            "email": email,
            "created_at": datetime.now().isoformat()
        }
        write_json(SESSIONS_FILE, sessions)
        
        return jsonify({
            "success": True,
            "session_token": session_token,
            "user": {
                "email": email,
                "username": username,
                "avatar": "",
                "bio": bio,
                "custom_status": "",
                "joined_servers": ["welcome-server"]
            }
        })
    except Exception as e:
        print(f"Signup error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({"error": "Missing email or password"}), 400
        
        users = read_json(USERS_FILE)
        
        if email in users and users[email]['password'] == hash_password(password):
            # Create session token
            session_token = str(uuid.uuid4())
            sessions = read_json(SESSIONS_FILE)
            sessions[session_token] = {
                "email": email,
                "created_at": datetime.now().isoformat()
            }
            write_json(SESSIONS_FILE, sessions)
            
            return jsonify({
                "success": True,
                "session_token": session_token,
                "user": {
                    "email": email,
                    "username": users[email].get('username', email.split('@')[0]),
                    "avatar": users[email].get('avatar', ''),
                    "bio": users[email].get('bio', ''),
                    "custom_status": users[email].get('custom_status', ''),
                    "joined_servers": users[email].get('joined_servers', [])
                }
            })
        
        return jsonify({"error": "Invalid email or password"}), 401
    except Exception as e:
        print(f"Login error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/logout', methods=['POST', 'OPTIONS'])
def logout():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.json
        session_token = data.get('session_token')
        
        sessions = read_json(SESSIONS_FILE)
        if session_token in sessions:
            del sessions[session_token]
            write_json(SESSIONS_FILE, sessions)
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/user/update', methods=['POST', 'OPTIONS'])
def update_user():
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.json
        email = data.get('email')
        users = read_json(USERS_FILE)
        
        if email in users:
            if 'username' in data and data['username']:
                # Check if username is taken
                for user_email, user_data in users.items():
                    if user_email != email and user_data.get('username') == data['username']:
                        return jsonify({"error": "Username already taken"}), 400
                users[email]['username'] = data['username']
            
            if 'bio' in data:
                users[email]['bio'] = data['bio']
            if 'custom_status' in data:
                users[email]['custom_status'] = data['custom_status']
            if 'avatar' in data:
                users[email]['avatar'] = data['avatar']
            
            write_json(USERS_FILE, users)
            return jsonify({"success": True})
        
        return jsonify({"error": "User not found"}), 404
    except Exception as e:
        print(f"Update error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Server endpoints
@app.route('/api/servers/user/<email>', methods=['GET', 'OPTIONS'])
def get_user_servers(email):
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        users = read_json(USERS_FILE)
        servers = read_json(SERVERS_FILE)
        
        if email not in users:
            return jsonify([])
        
        user_servers = []
        joined_servers = users[email].get('joined_servers', [])
        
        for server_id in joined_servers:
            if server_id in servers:
                server_data = servers[server_id].copy()
                # Add member count
                server_data['member_count'] = len(servers[server_id].get('members', []))
                user_servers.append(server_data)
        
        return jsonify(user_servers)
    except Exception as e:
        print(f"Get servers error: {str(e)}")
        return jsonify([])

@app.route('/api/servers/<server_id>/channels', methods=['GET', 'OPTIONS'])
def get_server_channels(server_id):
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        channels = read_json(CHANNELS_FILE)
        server_channels = list(channels.get(server_id, {}).values())
        return jsonify(server_channels)
    except Exception as e:
        print(f"Get channels error: {str(e)}")
        return jsonify([])

@app.route('/api/servers/create', methods=['POST', 'OPTIONS'])
def create_server():
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.json
        name = data.get('name')
        owner_email = data.get('owner_email')
        icon = data.get('icon', '🎮')
        
        servers = read_json(SERVERS_FILE)
        users = read_json(USERS_FILE)
        
        if owner_email not in users:
            return jsonify({"error": "User not found"}), 404
        
        server_id = str(uuid.uuid4())
        new_server = {
            "id": server_id,
            "name": name,
            "owner": owner_email,
            "icon": icon,
            "created_at": datetime.now().isoformat(),
            "members": [owner_email]
        }
        
        servers[server_id] = new_server
        write_json(SERVERS_FILE, servers)
        
        if 'joined_servers' not in users[owner_email]:
            users[owner_email]['joined_servers'] = []
        if server_id not in users[owner_email]['joined_servers']:
            users[owner_email]['joined_servers'].append(server_id)
        write_json(USERS_FILE, users)
        
        # Create default channels
        channels = read_json(CHANNELS_FILE)
        if server_id not in channels:
            channels[server_id] = {}
        
        general_id = str(uuid.uuid4())
        channels[server_id][general_id] = {
            "id": general_id,
            "name": "general",
            "type": "text",
            "server_id": server_id,
            "created_at": datetime.now().isoformat()
        }
        
        voice_id = str(uuid.uuid4())
        channels[server_id][voice_id] = {
            "id": voice_id,
            "name": "Voice Chat",
            "type": "voice",
            "server_id": server_id,
            "created_at": datetime.now().isoformat()
        }
        
        write_json(CHANNELS_FILE, channels)
        
        # Notify all users about new server
        socketio.emit('server_created', new_server)
        
        return jsonify({
            "success": True,
            "server": new_server,
            "channels": list(channels[server_id].values())
        })
    except Exception as e:
        print(f"Create server error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/servers/join', methods=['POST', 'OPTIONS'])
def join_server():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.json
        server_id = data.get('server_id')
        user_email = data.get('user_email')
        
        servers = read_json(SERVERS_FILE)
        users = read_json(USERS_FILE)
        
        if server_id not in servers:
            return jsonify({"error": "Server not found"}), 404
        
        if user_email not in users:
            return jsonify({"error": "User not found"}), 404
        
        if user_email not in servers[server_id]['members']:
            servers[server_id]['members'].append(user_email)
            write_json(SERVERS_FILE, servers)
            
            if 'joined_servers' not in users[user_email]:
                users[user_email]['joined_servers'] = []
            if server_id not in users[user_email]['joined_servers']:
                users[user_email]['joined_servers'].append(server_id)
            write_json(USERS_FILE, users)
        
        # Get server channels
        channels = read_json(CHANNELS_FILE)
        server_channels = list(channels.get(server_id, {}).values())
        
        return jsonify({
            "success": True,
            "server": servers[server_id],
            "channels": server_channels
        })
    except Exception as e:
        print(f"Join server error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/servers/leave', methods=['POST', 'OPTIONS'])
def leave_server():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.json
        server_id = data.get('server_id')
        user_email = data.get('user_email')
        
        servers = read_json(SERVERS_FILE)
        users = read_json(USERS_FILE)
        
        if server_id not in servers:
            return jsonify({"error": "Server not found"}), 404
        
        if user_email not in users:
            return jsonify({"error": "User not found"}), 404
        
        # Remove user from server members
        if user_email in servers[server_id]['members']:
            servers[server_id]['members'].remove(user_email)
            write_json(SERVERS_FILE, servers)
        
        # Remove server from user's joined servers
        if user_email in users and 'joined_servers' in users[user_email]:
            if server_id in users[user_email]['joined_servers']:
                users[user_email]['joined_servers'].remove(server_id)
                write_json(USERS_FILE, users)
        
        return jsonify({"success": True})
    except Exception as e:
        print(f"Leave server error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Channel endpoints
@app.route('/api/channels/create', methods=['POST', 'OPTIONS'])
def create_channel():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.json
        server_id = data.get('server_id')
        name = data.get('name')
        channel_type = data.get('type', 'text')
        
        channels = read_json(CHANNELS_FILE)
        
        if server_id not in channels:
            channels[server_id] = {}
        
        channel_id = str(uuid.uuid4())
        new_channel = {
            "id": channel_id,
            "name": name,
            "type": channel_type,
            "server_id": server_id,
            "created_at": datetime.now().isoformat()
        }
        
        channels[server_id][channel_id] = new_channel
        write_json(CHANNELS_FILE, channels)
        
        # Notify all users in the server
        socketio.emit('channel_created', {
            "server_id": server_id,
            "channel": new_channel
        })
        
        return jsonify({
            "success": True,
            "channel": new_channel
        })
    except Exception as e:
        print(f"Create channel error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Messages endpoints
@app.route('/api/messages/<server_id>/<channel_id>', methods=['GET', 'OPTIONS'])
def get_messages(server_id, channel_id):
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        messages = read_json(MESSAGES_FILE)
        key = f"{server_id}_{channel_id}"
        channel_messages = messages.get(key, [])
        return jsonify(channel_messages)
    except Exception as e:
        print(f"Get messages error: {str(e)}")
        return jsonify([])

@app.route('/api/messages/send', methods=['POST', 'OPTIONS'])
def send_message():
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.json
        messages = read_json(MESSAGES_FILE)
        
        server_id = data.get('server_id')
        channel_id = data.get('channel_id')
        key = f"{server_id}_{channel_id}"
        
        if key not in messages:
            messages[key] = []
        
        new_message = {
            "id": str(uuid.uuid4()),
            "user_email": data.get('user_email'),
            "username": data.get('username'),
            "content": data.get('content'),
            "type": data.get('type', 'text'),
            "avatar": data.get('avatar', ''),
            "timestamp": datetime.now().isoformat()
        }
        
        messages[key].append(new_message)
        
        # Keep only last 100 messages
        if len(messages[key]) > 100:
            messages[key] = messages[key][-100:]
        
        write_json(MESSAGES_FILE, messages)
        
        socketio.emit('new_message', {
            "server_id": server_id,
            "channel_id": channel_id,
            "message": new_message
        })
        
        return jsonify(new_message)
    except Exception as e:
        print(f"Send message error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Friend endpoints
@app.route('/api/friends/list/<email>', methods=['GET', 'OPTIONS'])
def get_friends(email):
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        users = read_json(USERS_FILE)
        friends = read_json(FRIENDS_FILE)
        
        if email not in friends:
            return jsonify({"friends": [], "requests": []})
        
        friend_list = []
        for friend_email in friends[email].get("friends", []):
            if friend_email in users:
                friend_list.append({
                    "email": friend_email,
                    "username": users[friend_email].get("username", friend_email),
                    "avatar": users[friend_email].get("avatar", ""),
                    "status": users[friend_email].get("custom_status", "Online")
                })
        
        return jsonify({
            "friends": friend_list,
            "requests": friends[email].get("requests", [])
        })
    except Exception as e:
        print(f"Get friends error: {str(e)}")
        return jsonify({"friends": [], "requests": []})

@app.route('/api/friends/request', methods=['POST', 'OPTIONS'])
def send_friend_request():
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.json
        from_email = data.get('from_email')
        to_username = data.get('to_username')
        
        users = read_json(USERS_FILE)
        friends = read_json(FRIENDS_FILE)
        
        # Find user by username
        to_email = None
        for email, user_data in users.items():
            if user_data.get('username') == to_username:
                to_email = email
                break
        
        if not to_email:
            return jsonify({"error": "User not found"}), 404
        
        if to_email == from_email:
            return jsonify({"error": "Cannot add yourself"}), 400
        
        if from_email not in friends:
            friends[from_email] = {"friends": [], "pending": [], "requests": []}
        
        if to_email not in friends:
            friends[to_email] = {"friends": [], "pending": [], "requests": []}
        
        if to_email in friends[from_email].get("friends", []):
            return jsonify({"error": "Already friends"}), 400
        
        if to_email in friends[from_email].get("pending", []):
            return jsonify({"error": "Request already sent"}), 400
        
        friends[from_email]["pending"] = friends[from_email].get("pending", []) + [to_email]
        friends[to_email]["requests"] = friends[to_email].get("requests", []) + [{
            "from_email": from_email,
            "from_username": users[from_email].get('username', from_email),
            "timestamp": datetime.now().isoformat()
        }]
        
        write_json(FRIENDS_FILE, friends)
        return jsonify({"success": True})
    except Exception as e:
        print(f"Send friend request error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/friends/accept', methods=['POST', 'OPTIONS'])
def accept_friend_request():
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.json
        user_email = data.get('user_email')
        request_email = data.get('request_email')
        
        users = read_json(USERS_FILE)
        friends = read_json(FRIENDS_FILE)
        
        if user_email not in friends or request_email not in friends:
            return jsonify({"error": "User not found"}), 404
        
        # Remove from requests
        friends[user_email]["requests"] = [
            r for r in friends[user_email].get("requests", []) 
            if r["from_email"] != request_email
        ]
        
        # Add to friends list for both users
        if "friends" not in friends[user_email]:
            friends[user_email]["friends"] = []
        if request_email not in friends[user_email]["friends"]:
            friends[user_email]["friends"].append(request_email)
        
        if "friends" not in friends[request_email]:
            friends[request_email]["friends"] = []
        if user_email not in friends[request_email]["friends"]:
            friends[request_email]["friends"].append(user_email)
        
        # Remove from pending for the requester
        if "pending" in friends[request_email] and user_email in friends[request_email]["pending"]:
            friends[request_email]["pending"].remove(user_email)
        
        write_json(FRIENDS_FILE, friends)
        return jsonify({"success": True})
    except Exception as e:
        print(f"Accept friend request error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/friends/reject', methods=['POST', 'OPTIONS'])
def reject_friend_request():
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.json
        user_email = data.get('user_email')
        request_email = data.get('request_email')
        
        friends = read_json(FRIENDS_FILE)
        
        if user_email in friends:
            friends[user_email]["requests"] = [
                r for r in friends[user_email].get("requests", []) 
                if r["from_email"] != request_email
            ]
            write_json(FRIENDS_FILE, friends)
        
        return jsonify({"success": True})
    except Exception as e:
        print(f"Reject friend request error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Emojis endpoints
@app.route('/api/emojis', methods=['GET', 'OPTIONS'])
def get_emojis():
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        emojis = read_json(EMOJIS_FILE)
        return jsonify(emojis)
    except Exception as e:
        print(f"Get emojis error: {str(e)}")
        return jsonify({})

@app.route('/api/emojis/add', methods=['POST', 'OPTIONS'])
def add_emoji():
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.json
        emojis = read_json(EMOJIS_FILE)
        
        name = data.get('name')
        emoji = data.get('emoji')
        
        if name and emoji:
            emojis[name] = emoji
            write_json(EMOJIS_FILE, emojis)
            socketio.emit('emoji_added', {"name": name, "emoji": emoji})
        
        return jsonify({"success": True})
    except Exception as e:
        print(f"Add emoji error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# SocketIO events
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('join_chat')
def handle_join_chat(data):
    try:
        room = f"{data.get('server_id')}_{data.get('channel_id')}"
        join_room(room)
        emit('user_joined_chat', {
            "username": data.get('username')
        }, room=room, include_self=False)
    except Exception as e:
        print(f"Join chat error: {str(e)}")

@socketio.on('leave_chat')
def handle_leave_chat(data):
    try:
        room = f"{data.get('server_id')}_{data.get('channel_id')}"
        leave_room(room)
    except Exception as e:
        print(f"Leave chat error: {str(e)}")

@socketio.on('typing')
def handle_typing(data):
    try:
        room = f"{data.get('server_id')}_{data.get('channel_id')}"
        emit('user_typing', {
            "username": data.get('username')
        }, room=room, include_self=False)
    except Exception as e:
        print(f"Typing error: {str(e)}")

# Voice/Video events
@socketio.on('voice_join')
def handle_voice_join(data):
    try:
        room = f"{data.get('server_id')}_{data.get('channel_id')}"
        join_room(room)
        user_email = data.get('user_email')
        username = data.get('username')
        
        # Notify others in the room
        emit('user_joined_voice', {
            "user_email": user_email,
            "username": username
        }, room=room, include_self=False)
        
        print(f"{username} joined voice in {room}")
    except Exception as e:
        print(f"Voice join error: {str(e)}")

@socketio.on('voice_leave')
def handle_voice_leave(data):
    try:
        room = f"{data.get('server_id')}_{data.get('channel_id')}"
        user_email = data.get('user_email')
        
        # Notify others in the room
        emit('user_left_voice', {
            "user_email": user_email
        }, room=room, include_self=False)
        
        print(f"{user_email} left voice from {room}")
    except Exception as e:
        print(f"Voice leave error: {str(e)}")

# WebRTC signaling for voice/video/screen share
@socketio.on('webrtc_offer')
def handle_webrtc_offer(data):
    try:
        target = data.get('target')
        offer = data.get('offer')
        from_user = data.get('from_user')
        
        emit('webrtc_offer', {
            "offer": offer,
            "from_user": from_user
        }, room=target)
    except Exception as e:
        print(f"WebRTC offer error: {str(e)}")

@socketio.on('webrtc_answer')
def handle_webrtc_answer(data):
    try:
        target = data.get('target')
        answer = data.get('answer')
        from_user = data.get('from_user')
        
        emit('webrtc_answer', {
            "answer": answer,
            "from_user": from_user
        }, room=target)
    except Exception as e:
        print(f"WebRTC answer error: {str(e)}")

@socketio.on('ice_candidate')
def handle_ice_candidate(data):
    try:
        target = data.get('target')
        candidate = data.get('candidate')
        from_user = data.get('from_user')
        
        emit('ice_candidate', {
            "candidate": candidate,
            "from_user": from_user
        }, room=target)
    except Exception as e:
        print(f"ICE candidate error: {str(e)}")

if __name__ == '__main__':
    print("="*50)
    print("Echo Room Server - Complete Version")
    print("="*50)
    print("Server running at: http://localhost:5000")
    print("\nFeatures:")
    print("- Session persistence (stay logged in)")
    print("- Message persistence (messages saved)")
    print("- Create channels")
    print("- Leave servers")
    print("- Voice/Video/Screen share ready")
    print("="*50)
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
