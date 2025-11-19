import threading
import socket
import json
import time
import sqlite3

host = '127.0.0.1'
port = 59394
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((host, port))
server.listen()
clients = []
users = []
timezones = []
user_ids = []
online = {}
chats = {}
groups = {}  # Format: {'group_name': {'members': set(), 'created_by': 'user'}}
user_groups = {}  # Format: {'username': ['group1', 'group2']}
messages = []
next_msg_id = 1
msg_id_lock = threading.Lock()
db = sqlite3.connect('chatapp.db', check_same_thread=False)
cur = db.cursor()
cur.execute('''CREATE TABLE IF NOT EXISTS messages
               (
                   id
                   INTEGER
                   PRIMARY
                   KEY,
                   sender
                   TEXT,
                   receiver
                   TEXT,
                   text
                   TEXT,
                   ts
                   INTEGER,
                   deleted
                   INTEGER
                   DEFAULT
                   0,
                   groupchat
                   INTEGER
                   DEFAULT
                   0
               )''')
cur.execute('''CREATE TABLE IF NOT EXISTS cleared_history
(
    user
    TEXT,
    other_user
    TEXT,
    cleared_at
    INTEGER,
    PRIMARY
    KEY
               (
    user,
    other_user
               )
    )''')
db.commit()
aliases = []


def broadcast(message, targets=None):
    if isinstance(message, str):
        data = message.encode('utf-8')
    elif isinstance(message, bytes):
        data = message
    else:
        data = str(message).encode('utf-8')
    if not data.endswith(b"\n"):
        data = data + b"\n"
    if targets is None:
        targets = clients.copy()
    for client in targets:
        try:
            client.send(data)
        except:
            pass


def handle_client(client):
    user = None
    tz = None
    buffer = ""
    while True:
        try:
            raw = client.recv(4096)
            if not raw:
                raise ConnectionError()
            payload = raw.decode('utf-8')
            buffer += payload
            parts = buffer.split('\n')
            buffer = parts.pop()
            for part in parts:
                if not part.strip():
                    continue
                try:
                    obj = json.loads(part)
                except:
                    continue
                typ = obj.get('type')
                if typ == 'register':
                    user = obj.get('user')
                    tz = obj.get('timezone') or 'UTC+06:00'
                    if user in users:
                        client.send((json.dumps({'type': 'error', 'what': 'duplicate_user'}) + "\n").encode('utf-8'))
                        continue
                    users.append(user)
                    timezones.append(tz)
                    user_ids.append(user)
                    online[user] = client
                    user_groups[user] = []
                    broadcast(json.dumps({'type': 'online', 'users': users, 'timezones': timezones}))

                elif typ == 'chat':
                    to = obj.get('to')
                    text = obj.get('text', '')
                    group_field = obj.get('group')
                    broadcast_all = obj.get('broadcast', False)

                    global next_msg_id
                    with msg_id_lock:
                        mid = str(next_msg_id)
                        next_msg_id += 1
                    ts = int(time.time())

                    # broadcast to everyone
                    if broadcast_all:
                        cur.execute('INSERT INTO messages(sender,receiver,text,ts,groupchat) VALUES(?,?,?,?,0)',
                                    (user, 'ALL', text, ts))
                        db.commit()
                        msg = {'type': 'message', 'id': mid, 'from': user, 'to': 'ALL', 'text': text, 'ts': ts,
                               'group': False, 'broadcast': True}
                        messages.append(msg)
                        broadcast(json.dumps(msg))
                        continue

                    group_name = None
                    if isinstance(group_field, str) and group_field:
                        group_name = group_field
                    elif isinstance(group_field, bool) and group_field and isinstance(to, str):
                        group_name = to

                    if group_name:
                        if group_name not in groups:
                            client.send((json.dumps(
                                {'type': 'error', 'what': 'group_not_found', 'group': group_name}) + "\n").encode(
                                'utf-8'))
                            continue
                        cur.execute('INSERT INTO messages(sender,receiver,text,ts,groupchat) VALUES(?,?,?,?,1)',
                                    (user, group_name, text, ts))
                        db.commit()
                        msg = {'type': 'message', 'id': mid, 'from': user, 'to': group_name, 'text': text, 'ts': ts,
                               'group': True}
                        messages.append(msg)
                        targets = [online[u] for u in groups[group_name]['members'] if u in online]
                        broadcast(json.dumps(msg), targets)
                    else:
                        cur.execute('INSERT INTO messages(sender,receiver,text,ts,groupchat) VALUES(?,?,?,?,0)',
                                    (user, to, text, ts))
                        db.commit()
                        msg = {'type': 'message', 'id': mid, 'from': user, 'to': to, 'text': text, 'ts': ts,
                               'group': False}
                        messages.append(msg)
                        targets = []
                        if user in online:
                            targets.append(online[user])
                        if to in online:
                            targets.append(online[to])
                        if targets:
                            broadcast(json.dumps(msg), targets)

                elif typ == 'clear_history':
                    other_user = obj.get('with_user')
                    if not other_user:
                        client.send((json.dumps({'type': 'error', 'what': 'missing_user'}) + "\n").encode('utf-8'))
                        continue
                    clear_ts = int(time.time())
                    cur.execute('''INSERT OR REPLACE INTO cleared_history (user, other_user, cleared_at)
                                   VALUES (?, ?, ?)''', (user, other_user, clear_ts))
                    db.commit()
                    response = {
                        'type': 'history_cleared',
                        'with_user': other_user,
                        'cleared_at': clear_ts
                    }
                    client.send((json.dumps(response) + "\n").encode('utf-8'))

                elif typ == 'create_group':
                    group_name = obj.get('group_name', '').strip()
                    members = obj.get('members', [])
                    if not group_name:
                        client.send((json.dumps({'type': 'error', 'what': 'empty_group_name'}) + "\n").encode('utf-8'))
                        continue
                    if group_name in groups:
                        client.send((json.dumps({'type': 'error', 'what': 'group_exists'}) + "\n").encode('utf-8'))
                        continue
                    groups[group_name] = {
                        'members': set(members + [user]),
                        'created_by': user,
                        'created_at': int(time.time())
                    }
                    if user not in user_groups:
                        user_groups[user] = []
                    user_groups[user].append(group_name)
                    for member in members:
                        if member not in user_groups:
                            user_groups[member] = []
                        if group_name not in user_groups[member]:
                            user_groups[member].append(group_name)
                    response = {'type': 'group_created', 'group_name': group_name, 'created_by': user}
                    targets = [online[m] for m in groups[group_name]['members'] if m in online]
                    broadcast(json.dumps(response), targets)

                elif typ == 'modify_group':
                    group_name = obj.get('group_name')
                    action = obj.get('action')
                    member = obj.get('member')
                    if group_name not in groups:
                        client.send((json.dumps({'type': 'error', 'what': 'group_not_found'}) + "\n").encode('utf-8'))
                        continue
                    if groups[group_name]['created_by'] != user:
                        client.send((json.dumps({'type': 'error', 'what': 'not_group_owner'}) + "\n").encode('utf-8'))
                        continue
                    if action == 'add':
                        if member in groups[group_name]['members']:
                            client.send((json.dumps({'type': 'error', 'what': 'already_member'}) + "\n").encode('utf-8'))
                            continue
                        groups[group_name]['members'].add(member)
                        if member not in user_groups:
                            user_groups[member] = []
                        user_groups[member].append(group_name)
                    elif action == 'remove':
                        if member not in groups[group_name]['members']:
                            client.send((json.dumps({'type': 'error', 'what': 'not_member'}) + "\n").encode('utf-8'))
                            continue
                        groups[group_name]['members'].discard(member)
                        if member in user_groups and group_name in user_groups[member]:
                            user_groups[member].remove(group_name)
                    response = {'type': 'group_modified', 'group_name': group_name, 'action': action, 'member': member}
                    targets = [online[m] for m in groups[group_name]['members'] if m in online]
                    broadcast(json.dumps(response), targets)

                elif typ == 'list_groups':
                    user_group_list = user_groups.get(user, [])
                    response = {'type': 'groups_list', 'groups': user_group_list}
                    client.send((json.dumps(response) + "\n").encode('utf-8'))

                elif typ == 'delete_request':
                    mid = obj.get('id')
                    cur.execute('SELECT sender,receiver,groupchat FROM messages WHERE id=?', (mid,))
                    row = cur.fetchone()
                    if not row:
                        client.send(
                            (json.dumps({'type': 'error', 'what': 'not_found', 'id': mid}) + "\n").encode('utf-8'))
                        continue
                    sender_db, receiver_db, groupchat_db = row
                    if sender_db != user:
                        client.send(
                            (json.dumps({'type': 'error', 'what': 'permission_denied', 'id': mid}) + "\n").encode(
                                'utf-8'))
                        continue
                    cur.execute('UPDATE messages SET deleted=1 WHERE id=?', (mid,))
                    db.commit()
                    evt = {'type': 'delete', 'id': mid, 'deleted_by': user}
                    if groupchat_db:
                        if receiver_db in groups:
                            targets = [online[u] for u in groups[receiver_db]['members'] if u in online]
                            broadcast(json.dumps(evt), targets)
                    else:
                        targets = []
                        if user in online:
                            targets.append(online[user])
                        if receiver_db in online:
                            targets.append(online[receiver_db])
                        if targets:
                            broadcast(json.dumps(evt), targets)

                elif typ == 'chatlist':
                    chatlist = list(
                        set([m['from'] for m in messages] + [m['to'] for m in messages if m['to'] != 'group']))
                    client.send((json.dumps({'type': 'chatlist', 'users': chatlist}) + "\n").encode('utf-8'))

                elif typ == 'online':
                    client.send(
                        (json.dumps({'type': 'online', 'users': users, 'timezones': timezones}) + "\n").encode('utf-8'))

                elif typ == 'message_history':
                    chat_with = obj.get('with_user')
                    limit = obj.get('limit', 50)
                    cur.execute('''SELECT cleared_at
                                   FROM cleared_history
                                   WHERE user = ?
                                     AND other_user = ?''', (user, chat_with))
                    cleared_row = cur.fetchone()
                    cleared_at = cleared_row[0] if cleared_row else 0

                    if chat_with in groups:
                        cur.execute('''SELECT id, sender, receiver, text, ts, deleted
                                       FROM messages
                                       WHERE groupchat = 1 AND receiver = ?
                                         AND ts > ?
                                       ORDER BY ts DESC LIMIT ?''', (chat_with, cleared_at, limit))
                    else:
                        cur.execute('''SELECT id, sender, receiver, text, ts, deleted
                                       FROM messages
                                       WHERE groupchat = 0
                                         AND ((sender = ? AND receiver = ?) OR (sender = ? AND receiver = ?))
                                         AND ts > ?
                                       ORDER BY ts DESC LIMIT ?''',
                                    (user, chat_with, chat_with, user, cleared_at, limit))

                    rows = cur.fetchall()
                    history = []

                    for row in reversed(rows):
                        mid_db, sender_db, receiver_db, text_db, ts_db, deleted_db = row
                        history.append({
                            'type': 'message',
                            'id': str(mid_db),
                            'from': sender_db,
                            'to': receiver_db,
                            'text': text_db,
                            'ts': ts_db,
                            'deleted': bool(deleted_db),
                            'group': (receiver_db in groups)
                        })

                    response = {
                        'type': 'message_history',
                        'with_user': chat_with,
                        'messages': history,
                        'cleared': bool(cleared_row)
                    }
                    client.send((json.dumps(response) + "\n").encode('utf-8'))

                elif typ == 'disconnect':
                    if user and user in users:
                        try:
                            idx = users.index(user)
                            users.pop(idx)
                            timezones.pop(idx)
                            user_ids.pop(idx)
                        except:
                            pass
                        if user in online:
                            del online[user]
                        broadcast(json.dumps({'type': 'online', 'users': users, 'timezones': timezones}))
                    try:
                        clients.remove(client)
                    except:
                        pass
                    try:
                        client.close()
                    except:
                        pass
                    return
                else:
                    continue
        except:
            if user and user in users:
                try:
                    idx = users.index(user)
                    users.pop(idx)
                    timezones.pop(idx)
                    user_ids.pop(idx)
                except:
                    pass
                if user in online:
                    del online[user]
                broadcast(json.dumps({'type': 'online', 'users': users, 'timezones': timezones}))
            try:
                clients.remove(client)
            except:
                pass
            try:
                client.close()
            except:
                pass
            return


def receive():
    while True:
        print('Server is running and listening ...')
        client, address = server.accept()
        clients.append(client)
        thread = threading.Thread(target=handle_client, args=(client,))
        thread.start()


if __name__ == "__main__":
    receive()