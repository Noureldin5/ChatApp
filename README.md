# ChatApp

A multi-client chat application with user authentication, private messaging, and group chat features. Built with Python sockets, SQLite, and PyQt5.

## Features

- User authentication (login/signup) with bcrypt password hashing
- Private messaging between users
- Group chat functionality
- Real-time message delivery
- Message persistence with SQLite
- Online user status tracking
- Console and GUI clients
- Message deletion and chat history management
- Unread message notifications

## Requirements

- Python 3.8 or higher
- bcrypt (for password hashing)
- PyQt5 (for GUI client only)

## Installation

### Option 1: Local Installation

1. Clone or download the repository

2. Install dependencies:
```powershell
pip install -r requirements.txt
```

### Option 2: Docker (Server Only)

Build the Docker image:
```powershell
docker build -t chatapp .
```

## Usage

### Running Locally (Recommended for Development)

**1. Start the Server**

```powershell
python -m server.main
```

The server will start on `127.0.0.1:59394`.

**2. Start a Client**

Console Client:
```powershell
python -m client.main
```

GUI Client:
```powershell
python -m gui.main
```

### Running with Docker

Docker runs **only the server**. Clients must run on your host machine to connect.

**1. Start the Server in Docker**

```powershell
docker run -p 59394:59394 --name chatapp-server chatapp
```

This maps port 59394 from the container to your host machine.

**2. Start Clients on Host Machine**

On your Windows machine, install dependencies and run clients:

```powershell
# Install client dependencies (if not already installed)
pip install bcrypt PyQt5

# Run console client
python -m client.main

# Or run GUI client
python -m gui.main
```

The clients will connect to `127.0.0.1:59394` which is now forwarded from Docker.

**3. Stop the Server**

```powershell
docker stop chatapp-server
docker rm chatapp-server
```

### Docker Compose (Alternative)

Create a `docker-compose.yml`:

```yaml
version: '3.8'
services:
  server:
    build: .
    ports:
      - "59394:59394"
    volumes:
      - ./chatapp.db:/app/chatapp.db
```

Run:
```powershell
docker-compose up
```

## Client Commands

### Console Client

After logging in:
- `send` - Send a private message to a user
- `create_group` - Create a new group chat
- `delete_group` - Delete a group you own
- `add` - Add a member to your group
- `remove` - Remove a member from your group
- `groups` - List all your groups
- `delete` - Delete a message you sent
- `chats` - View your chat list with unread counts
- `history` - View message history with a user/group
- `clear` - Clear chat history
- `online` - Show online users
- `quit` - Exit the application

### GUI Client

The GUI provides buttons and forms for all features:
- Login/Signup dialog
- Chat list with unread counts
- Message history window
- Send messages
- Create/manage groups
- View online users

## Project Structure

```
ChatApp/
├── server/              # Server application
│   ├── main.py         # Server entry point
│   ├── server.py       # TCP server logic
│   ├── handler.py      # Client request handler
│   ├── database.py     # SQLite database operations
│   └── models.py       # Data models
├── client/              # Console client
│   ├── main.py         # Console client entry point
│   ├── client.py       # Client connection logic
│   ├── messageHandler.py # Message processing
│   ├── hints.py        # Help system
│   └── models.py       # Client data models
├── gui/                 # GUI client
│   ├── main.py         # GUI entry point
│   └── gui.py          # PyQt5 interface
├── Dockerfile          # Docker configuration for server
├── .dockerignore       # Docker ignore patterns
├── requirements.txt    # Python dependencies
├── chatapp.db          # SQLite database (auto-created)
└── README.md           # This file
```

## Database Schema

**users**
- username (TEXT PRIMARY KEY)
- password_hash (TEXT)

**messages**
- id (INTEGER PRIMARY KEY)
- sender (TEXT)
- receiver (TEXT)
- message (TEXT)
- timestamp (TEXT)
- is_group (INTEGER)

**groups**
- id (INTEGER PRIMARY KEY)
- name (TEXT)
- owner (TEXT)

**group_members**
- group_id (INTEGER)
- username (TEXT)

**read_receipts**
- message_id (INTEGER)
- username (TEXT)
- read_at (TEXT)

## Configuration

Default server settings (in `server/main.py` and `server/server.py`):
- Host: `127.0.0.1`
- Port: `59394`

To change the port, edit `server/main.py` and `client/client.py`.

## Troubleshooting

### "Connection refused" when using Docker

Make sure you:
1. Started the Docker container with `-p 59394:59394`
2. Are running the client on the **host machine** (not inside Docker)
3. The server is actually running (check `docker ps`)

### "Module not found" errors

Install dependencies:
```powershell
pip install -r requirements.txt
```

### Database locked errors

Only one server instance can run at a time. Stop any existing servers before starting a new one.

### GUI doesn't start

Make sure PyQt5 is installed:
```powershell
pip install PyQt5
```

Note: PyQt5 requires a desktop environment and won't work inside Docker containers.

## Notes

- The GUI client (`gui.main`) requires a desktop environment and cannot run in Docker
- Docker is only for running the server in a containerized environment
- Multiple clients can connect to one server simultaneously
- Passwords are hashed using bcrypt before storage
- Message history is preserved in the SQLite database

## Author

Noureldin

## License

This project is for educational purposes.
- password_hash (TEXT)
- salt (TEXT)
- timezone (TEXT)
- created_at (INTEGER)

### messages
- id (INTEGER PRIMARY KEY)
- sender (TEXT)
- receiver (TEXT)
- text (TEXT)
- ts (INTEGER)
- deleted (INTEGER)
- groupchat (INTEGER)

### cleared_history
- user (TEXT)
- other_user (TEXT)
- cleared_at (INTEGER)

### unread_counts
- user (TEXT)
- chat_with (TEXT)
- count (INTEGER)

## Author

Noureldin

