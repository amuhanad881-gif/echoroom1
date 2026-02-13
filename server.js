const express = require('express');
const http = require('http');
const socketIO = require('socket.io');
const path = require('path');
const cors = require('cors');
require('dotenv').config();

const app = express();
const server = http.createServer(app);
const io = socketIO(server, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  },
  transports: ['websocket', 'polling']
});

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Store active rooms and users
const rooms = new Map(); // roomId -> Set of socket ids
const userStreams = new Map(); // socketId -> { roomId, username }

// Serve the main page
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Health check endpoint for Railway
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'OK', timestamp: new Date().toISOString() });
});

// API endpoint to get active rooms (optional)
app.get('/api/rooms', (req, res) => {
  const activeRooms = Array.from(rooms.entries()).map(([roomId, users]) => ({
    roomId,
    userCount: users.size,
    users: Array.from(users)
  }));
  res.json(activeRooms);
});

io.on('connection', (socket) => {
  console.log(`New client connected: ${socket.id}`);

  // Handle joining a room
  socket.on('join-room', async ({ roomId, username }) => {
    try {
      // Leave previous room if any
      if (userStreams.has(socket.id)) {
        const prevRoom = userStreams.get(socket.id).roomId;
        socket.leave(prevRoom);
        rooms.get(prevRoom)?.delete(socket.id);
        
        // Notify others in previous room
        socket.to(prevRoom).emit('user-left', {
          userId: socket.id,
          username: userStreams.get(socket.id).username
        });
      }

      // Join new room
      socket.join(roomId);
      
      // Store user info
      userStreams.set(socket.id, { roomId, username });
      
      // Add to rooms map
      if (!rooms.has(roomId)) {
        rooms.set(roomId, new Set());
      }
      rooms.get(roomId).add(socket.id);

      // Get existing users in the room
      const existingUsers = Array.from(rooms.get(roomId))
        .filter(id => id !== socket.id)
        .map(id => ({
          userId: id,
          username: userStreams.get(id)?.username || 'Anonymous'
        }));

      // Send confirmation to the new user
      socket.emit('room-joined', {
        roomId,
        userId: socket.id,
        username,
        existingUsers
      });

      // Notify other users in the room
      socket.to(roomId).emit('user-joined', {
        userId: socket.id,
        username
      });

      console.log(`User ${username} (${socket.id}) joined room: ${roomId}`);
      console.log(`Room ${roomId} now has ${rooms.get(roomId).size} users`);

    } catch (error) {
      console.error('Error joining room:', error);
      socket.emit('error', { message: 'Failed to join room' });
    }
  });

  // Handle WebRTC signaling
  socket.on('signal', ({ to, signal }) => {
    io.to(to).emit('signal', {
      from: socket.id,
      signal
    });
  });

  // Handle screen share signaling
  socket.on('screen-signal', ({ to, signal }) => {
    io.to(to).emit('screen-signal', {
      from: socket.id,
      signal
    });
  });

  // Handle user leaving room
  socket.on('leave-room', () => {
    handleUserDisconnect(socket);
  });

  // Handle disconnection
  socket.on('disconnect', () => {
    handleUserDisconnect(socket);
  });

  // Handle room locking/unlocking (optional)
  socket.on('toggle-room-lock', ({ roomId, lock }) => {
    // Implement room locking logic if needed
    socket.to(roomId).emit('room-lock-changed', { locked: lock });
  });

  // Handle chat messages (optional enhancement)
  socket.on('chat-message', ({ roomId, message }) => {
    const userInfo = userStreams.get(socket.id);
    if (userInfo) {
      io.to(roomId).emit('chat-message', {
        userId: socket.id,
        username: userInfo.username,
        message,
        timestamp: new Date().toISOString()
      });
    }
  });
});

function handleUserDisconnect(socket) {
  const userInfo = userStreams.get(socket.id);
  
  if (userInfo) {
    const { roomId, username } = userInfo;
    
    // Remove from room
    socket.leave(roomId);
    rooms.get(roomId)?.delete(socket.id);
    
    // Clean up empty rooms
    if (rooms.get(roomId)?.size === 0) {
      rooms.delete(roomId);
    }
    
    // Notify others
    socket.to(roomId).emit('user-left', {
      userId: socket.id,
      username
    });
    
    // Remove from userStreams
    userStreams.delete(socket.id);
    
    console.log(`User ${username} (${socket.id}) left room ${roomId}`);
  }
}

// Error handling
io.on('error', (error) => {
  console.error('Socket.IO error:', error);
});

// Start server with Railway's PORT
const PORT = process.env.PORT || 3000;
server.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running on port ${PORT}`);
  console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
});