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
group_chats = {'group': set()}
messages = []
next_msg_id = 1
msg_id_lock = threading.Lock()
db = sqlite3.connect('chatapp.db', check_same_thread=False)
cur = db.cursor()
cur.execute('''CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, sender TEXT, receiver TEXT, text TEXT, ts INTEGER, deleted INTEGER DEFAULT 0, groupchat INTEGER DEFAULT 0)''')
db.commit()
clients = []
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
                        client.send((json.dumps({'type':'error','what':'duplicate_user'})+"\n").encode('utf-8'))
                        continue
                    users.append(user)
                    timezones.append(tz)
                    user_ids.append(user)
                    online[user] = client
                    group_chats['group'].add(user)
                    broadcast(json.dumps({'type':'online','users':users,'timezones':timezones}))
                elif typ == 'chat':
                    to = obj.get('to')
                    text = obj.get('text','')
                    group = obj.get('group',False)
                    global next_msg_id
                    with msg_id_lock:
                        mid = str(next_msg_id)
                        next_msg_id += 1
                    ts = int(time.time())
                    if group:
                        cur.execute('INSERT INTO messages(sender,receiver,text,ts,groupchat) VALUES(?,?,?,?,1)',(user,'group',text,ts))
                        db.commit()
                        msg = {'type':'message','id':mid,'from':user,'to':'group','text':text,'ts':ts,'group':True}
                        messages.append(msg)
                        targets = [online[u] for u in group_chats['group'] if u in online]
                        if user in online and online[user] not in targets:
                            targets.append(online[user])
                        broadcast(json.dumps(msg), targets)
                    else:
                        cur.execute('INSERT INTO messages(sender,receiver,text,ts,groupchat) VALUES(?,?,?,?,0)',(user,to,text,ts))
                        db.commit()
                        msg = {'type':'message','id':mid,'from':user,'to':to,'text':text,'ts':ts,'group':False}
                        messages.append(msg)
                        targets = []
                        if user in online:
                            targets.append(online[user])
                        if to in online:
                            targets.append(online[to])
                        if targets:
                            broadcast(json.dumps(msg), targets)
                elif typ == 'delete_request':
                    mid = obj.get('id')
                    cur.execute('SELECT sender,receiver,groupchat FROM messages WHERE id=?',(mid,))
                    row = cur.fetchone()
                    if not row:
                        client.send((json.dumps({'type':'error','what':'not_found','id':mid})+"\n").encode('utf-8'))
                        continue
                    sender_db, receiver_db, groupchat_db = row
                    if sender_db != user:
                        client.send((json.dumps({'type':'error','what':'permission_denied','id':mid})+"\n").encode('utf-8'))
                        continue
                    cur.execute('UPDATE messages SET deleted=1 WHERE id=?',(mid,))
                    db.commit()
                    evt = {'type':'delete','id':mid,'deleted_by':user}
                    if groupchat_db:
                        targets = [online[u] for u in group_chats['group'] if u in online]
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
                    chatlist = list(set([m['from'] for m in messages]+[m['to'] for m in messages if m['to']!='group']))
                    client.send((json.dumps({'type':'chatlist','users':chatlist})+"\n").encode('utf-8'))
                elif typ == 'online':
                    client.send((json.dumps({'type':'online','users':users,'timezones':timezones})+"\n").encode('utf-8'))
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
                        if user in group_chats['group']:
                            group_chats['group'].remove(user)
                        broadcast(json.dumps({'type':'online','users':users,'timezones':timezones}))
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
                if user in group_chats['group']:
                    group_chats['group'].remove(user)
                broadcast(json.dumps({'type':'online','users':users,'timezones':timezones}))
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