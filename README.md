# ChatApp — Multi-Client Chat System

A simple, multi-client chat application built with Python sockets, threading, and SQLite. Supports individual and group messaging, message deletion, online status, timezones, and persistent message storage.

## Features

- **Multi-client support**: Multiple users can connect simultaneously via TCP sockets.
- **User registration**: Pick an alias and timezone on connect; unique usernames enforced.
- **Online status**: See who is online with their timezone.
- **Individual chat**: Send private messages to specific users.
- **Group chat**: Broadcast messages to all connected users.
- **Message deletion**: Delete your own messages; deletion is broadcast to all affected parties.
- **Message persistence**: All messages stored in SQLite database (`chatapp.db`).
- **Clean disconnect**: Graceful exit with immediate online list updates.
- **Human-readable timestamps**: Messages show formatted date/time (YYYY-MM-DD HH:MM:SS).
- **Newline-delimited JSON protocol**: Robust handling of partial and multiple messages per socket recv.

## Requirements

- Python 3.8 or higher
- No external dependencies (uses only Python standard library: `socket`, `threading`, `json`, `time`, `sqlite3`).

## Project Structure

```
ChatApp/
├── README.md           # This file
├── requirements.txt    # Dependency documentation
├── Server.py           # TCP server; handles clients, routing, persistence
├── Client.py           # Console client; user interface and messaging
└── chatapp.db          # SQLite database (created on first server start)
```

## Setup

### 1. Clone or download the project
```bash
cd ChatApp
```

### 2. (Optional) Create a virtual environment
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

### 3. Install dependencies (if any)
```bash
pip install -r requirements.txt
```
Currently, `requirements.txt` documents that only Python standard library is needed. No pip install required.

## Running the Application

### Start the Server

Open a terminal and run:
```powershell
python Server.py
```

Expected output:
```
Server is running and listening ...
Server is running and listening ...
Server is running and listening ...
...
```
The server listens on `127.0.0.1:59394` and accepts client connections.

### Start Clients

Open a new terminal (one per client) and run:
```powershell
python Client.py
```

You'll be prompted:
```
Choose an alias: alice
Timezone (e.g. UTC+06:00) [UTC+06:00]: 
```
- Enter an alias (username) — must be unique.
- Press Enter to accept default timezone or enter your own (e.g., `UTC+05:00`).

After registration, you'll see a help menu and the command prompt:
```
Commands:
  send   - send a message. You'll be asked for recipient (blank=group) and message text.
  delete - delete a message you sent. You need the numeric message ID shown in [id].
  chats  - request the list of users you've chatted with from the server.
  online - show current online users and their timezones.
  quit   - disconnect and exit the client.
To delete: look at messages' [id] printed in the chat view, then use the delete command and enter that id.

[send|delete|chats|online|quit]> 
```

## Usage Examples

### Example 1: Send a group message
```
[send|delete|chats|online|quit]> send
To (blank=all): 
Message: Hello everyone!

--- Chat ---
[1] 2025-11-17 14:23:45 you: Hello everyone!
```
All online users will see this message with the same ID.

### Example 2: Send a private message
```
[send|delete|chats|online|quit]> send
To (blank=all): bob
Message: Hi Bob, how are you?

--- Chat ---
[2] 2025-11-17 14:24:10 you -> bob: Hi Bob, how are you?
```
Only the sender and recipient see the message.

### Example 3: View online users
```
[send|delete|chats|online|quit]> online

Online:
  alice (UTC+06:00)
  bob (UTC+05:00)
  charlie (UTC+06:00)
```

### Example 4: Delete a message
Look at a message ID in the chat (e.g., `[2]`), then:
```
[send|delete|chats|online|quit]> delete
Message ID to delete: 2
Message 2 was deleted by you
```
The deletion is broadcast to all relevant users and messages are re-rendered without the deleted entry.

### Example 5: View your chat history
```
[send|delete|chats|online|quit]> chats

Chats:
  alice
  bob
  charlie
```
Shows users you've sent or received messages from (includes group chats if any).

### Example 6: Quit cleanly
```
[send|delete|chats|online|quit]> quit
```
Or press `Ctrl+C`. The client sends a disconnect message, the server removes you from the online list, and all clients are notified of the status change.

## Protocol Overview

The client and server communicate using **newline-delimited JSON** over TCP. Each message is a JSON object followed by a newline (`\n`).

### Message Types

#### Client → Server

- **register**: User joins
  ```json
  {"type":"register","user":"alice","timezone":"UTC+06:00"}
  ```

- **chat**: Send message
  ```json
  {"type":"chat","text":"Hello","group":true}
  ```
  or (private):
  ```json
  {"type":"chat","text":"Hello Bob","to":"bob","group":false}
  ```

- **delete_request**: Delete a message
  ```json
  {"type":"delete_request","id":"5"}
  ```

- **chatlist**: Request list of past chatters
  ```json
  {"type":"chatlist"}
  ```

- **online**: Request online user list
  ```json
  {"type":"online"}
  ```

- **disconnect**: Gracefully disconnect
  ```json
  {"type":"disconnect"}
  ```

#### Server → Client

- **online**: Broadcast online users
  ```json
  {"type":"online","users":["alice","bob"],"timezones":["UTC+06:00","UTC+05:00"]}
  ```

- **message**: Incoming message
  ```json
  {"type":"message","id":"5","from":"alice","to":"group","text":"Hello","ts":1700000000,"group":true}
  ```

- **delete**: Notification of deleted message
  ```json
  {"type":"delete","id":"5","deleted_by":"alice"}
  ```

- **chatlist**: List of users you've chatted with
  ```json
  {"type":"chatlist","users":["alice","bob"]}
  ```

- **error**: Error response
  ```json
  {"type":"error","what":"not_found","id":"5"}
  ```

## Database Schema

SQLite table: `messages`

```sql
CREATE TABLE messages (
  id INTEGER PRIMARY KEY,
  sender TEXT,
  receiver TEXT,
  text TEXT,
  ts INTEGER,
  deleted INTEGER DEFAULT 0,
  groupchat INTEGER DEFAULT 0
)
```

- **id**: Auto-incremented message ID.
- **sender**: Username of message author.
- **receiver**: Recipient username or 'group'.
- **text**: Message content.
- **ts**: Unix timestamp (seconds since epoch).
- **deleted**: 1 if deleted, 0 otherwise.
- **groupchat**: 1 if group message, 0 if private.

## Troubleshooting

### Issue: "Could not connect to server"
- **Cause**: Server is not running or listening on the expected host/port.
- **Fix**: Start `Server.py` first. Ensure it prints "Server is running and listening ...".

### Issue: "duplicate_user" error
- **Cause**: You tried to register with an alias already in use.
- **Fix**: Pick a different alias. Quit an existing session if needed (wait a few seconds for cleanup).

### Issue: Private message not received
- **Cause**: Recipient is not online or typo in recipient name (case-sensitive).
- **Fix**: Use `online` to see current users. Type the exact alias.

### Issue: Group message not showing on other clients
- **Cause**: Left "To (blank=all):" field blank but the client didn't mark it as group.
- **Fix**: Press Enter to leave it blank; the client sets `"group": true`.

### Issue: Cannot delete a message
- **Cause**: Message not found (wrong ID or message is from another user).
- **Fix**: Only senders can delete their own messages. Use the exact numeric ID from the chat view.

### Issue: Old messages not showing when a new client joins
- **Cause**: Client doesn't request message history on startup.
- **Fix**: This is by design; only messages sent *after* you join are shown. (Message history on join can be added as a future feature.)

## Architecture

### Server (`Server.py`)

- **Single-threaded accept loop** (`receive()`): Waits for new connections.
- **Per-client handler** (`handle_client(client)`): Runs in a thread for each connected client.
  - Reads and parses newline-delimited JSON.
  - Maintains per-client buffer to handle partial messages.
  - Handles registration, chat, deletion, and query requests.
  - Cleans up on disconnect (exception or explicit disconnect message).
- **Global state**:
  - `clients`: List of all socket connections.
  - `users`: List of online usernames.
  - `online`: Dict mapping username -> socket (for quick lookups).
  - `group_chats['group']`: Set of users in the default group.
  - `messages`: In-memory message list.
  - `db`, `cur`: SQLite connection for persistence.

### Client (`Client.py`)

- **Main thread**: Prompts user for commands and sends requests to server.
- **Receiver thread** (daemon): Listens for incoming messages, updates, and deletions; re-renders chat view.
- **Local state**:
  - `chat`: List of message objects (sender, receiver, text, timestamp, id, deleted flag).
  - `online`: List of online users with timezones.
  - `chatlist`: List of users you've interacted with.
  - `lock`: Thread-safe access to shared state between main and receiver threads.

## Future Enhancements

- **Persistent chat history on join**: Send recent messages to a new client on registration.
- **Named group channels**: Support multiple named groups (e.g., "team1", "projectX") beyond the single global group.
- **User authentication**: Add password or token-based login.
- **TLS/SSL encryption**: Secure socket connections.
- **Logging**: Server-side logging with configurable levels.
- **CLI flags**: `--host`, `--port`, `--log-level` for flexible configuration.
- **Message search**: Query messages by sender, receiver, or content.
- **Typing indicators**: Show when users are typing.
- **Unit tests**: Pytest-based tests for protocol parsing, message routing, deletion, etc.

## License

This project is open-source and available for educational and personal use.

## Author

Noureldin

---

**Enjoy your chat app!** Start the server, open multiple clients, and begin messaging.
