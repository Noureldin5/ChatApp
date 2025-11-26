# ChatApp

A multi-client chat application built with Python. Supports user authentication, private messaging, group chats, and a GUI interface.

## Features

- User authentication (login/signup) with bcrypt password hashing
- Private messaging between users
- Group chat functionality (create, manage, and delete groups)
- Console and GUI clients
- Message persistence with SQLite
- Online user status
- Message deletion
- Unread message counts
- Chat history clearing
- Timezone support

## Requirements

- Python 3.8 or higher
- bcrypt
- PyQt5 (for GUI client)

## Installation

1. Clone the repository:
```powershell
cd ChatApp
```

2. Install dependencies:
```powershell
pip install -r requirements.txt
```

## Project Structure

```
ChatApp/
├── server/
│   ├── main.py          # Server entry point
│   ├── server.py        # Server logic
│   ├── handler.py       # Client request handler
│   ├── database.py      # Database operations
│   └── models.py        # User and Group models
├── client/
│   ├── main.py          # Console client entry point
│   ├── client.py        # Client logic
│   ├── messageHandler.py # Message handling
│   ├── hints.py         # Help/hints display
│   └── models.py        # Client models
├── gui/
│   ├── main.py          # GUI entry point
│   └── gui.py           # PyQt5 GUI interface
├── chatapp.db           # SQLite database (auto-created)
├── notif.wav            # Notification sound
└── requirements.txt     # Dependencies
```

## Usage

### Start the Server

```powershell
python -m server.main
```

The server will start on `127.0.0.1:59394`.

### Start Console Client

```powershell
python -m client.main
```

Choose login or signup, then use commands:
- `send` - Send a message
- `create_group` - Create a new group
- `delete_group` - Delete a group
- `add` - Add member to group
- `remove` - Remove member from group
- `groups` - List your groups
- `delete` - Delete a message
- `chats` - View chat list
- `history` - View message history
- `clear` - Clear chat history
- `online` - Show online users
- `quit` - Exit

### Start GUI Client

```powershell
python -m gui.main
```

The GUI provides a graphical interface for all chat features including login, messaging, and group management.

## Database Schema

### users
- username (TEXT PRIMARY KEY)
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

