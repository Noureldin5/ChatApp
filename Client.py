
import socket
import threading
import json
import sys
import time

def prompt(text, default=None):
    v = input(text)
    if not v and default is not None:
        return default
    return v

def print_online(online):
    print("\nOnline:")
    for user in online:
        print(f"  {user['alias']} ({user['timezone']})")

def print_chat(chat, my_alias):
    print("\n--- Chat ---")
    for m in chat:
        if m.get('deleted'):
            continue
        t = m['timestamp']
        sender = m['sender']
        to = m.get('to')
        msg = m['message']
        mid = m['id']
        if to:
            if to == my_alias:
                print(f"[{mid}] {t} {sender} -> you: {msg}")
            elif sender == my_alias:
                print(f"[{mid}] {t} you -> {to}: {msg}")
            else:
                print(f"[{mid}] {t} {sender} -> {to}: {msg}")
        else:
            who = "you" if sender == my_alias else sender
            print(f"[{mid}] {t} {who}: {msg}")

def main():
    host = "127.0.0.1"
    port = 59394
    alias = prompt("Choose an alias: ")
    tz = prompt("Timezone (e.g. UTC+06:00) [UTC+06:00]: ", "UTC+06:00")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, port))
    except Exception as e:
        print(f"Could not connect to server at {host}:{port} ({e})")
        sys.exit(1)
    s.send((json.dumps({"type": "register", "user": alias, "timezone": tz}) + "\n").encode())
    online = []
    chat = []
    chatlist = []
    lock = threading.Lock()
    running = True

    def format_ts(ts):
        try:
            return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(ts)))
        except:
            return str(ts)

    def print_help():
        print("Commands:")
        print("  send   - send a message. You'll be asked for recipient (blank=group) and message text.")
        print("  delete - delete a message you sent. You need the numeric message ID shown in [id].")
        print("  chats  - request the list of users you've chatted with from the server.")
        print("  online - show current online users and their timezones.")
        print("  quit   - disconnect and exit the client.")
        print("To delete: look at messages' [id] printed in the chat view, then use the delete command and enter that id.")

    def receiver():
        nonlocal online, chat, chatlist, running
        while running:
            try:
                data = s.recv(4096)
                if not data:
                    print("Disconnected from server.")
                    running = False
                    break
                msgs = data.split(b'\n')
                for msg in msgs:
                    if not msg.strip():
                        continue
                    try:
                        obj = json.loads(msg.decode())
                    except:
                        continue
                    if obj["type"] == "online":
                        with lock:
                            online = [
                                {"alias": u, "timezone": t}
                                for u, t in zip(obj["users"], obj["timezones"])
                            ]
                        print_online(online)
                    elif obj["type"] == "chatlist":
                        # Server sends chatlist as 'users'
                        with lock:
                            chatlist = obj.get("users", [])
                        print("\nChats:")
                        for c in chatlist:
                            print(f"  {c}")
                    elif obj["type"] == "message":
                        m = obj
                        msg_obj = {
                            "id": m["id"],
                            "sender": m["from"],
                            "to": m.get("to"),
                            "message": m["text"],
                            "timestamp": format_ts(m["ts"]),
                            "group": m.get("group", False),
                        }
                        with lock:
                            chat.append(msg_obj)
                        print_chat(chat, alias)
                    elif obj["type"] == "delete":
                        mid = obj["id"]
                        with lock:
                            for m in chat:
                                if m["id"] == mid:
                                    m["deleted"] = True
                        print(f"Message {mid} was deleted by {obj.get('deleted_by','unknown')}")
                        print_chat(chat, alias)
            except Exception as e:
                print(f"Error: {e}")
                running = False
                break

    t = threading.Thread(target=receiver, daemon=True)
    t.start()

    print_help()

    try:
        while running:
            cmd = input("\n[send|delete|chats|online|quit]> ").strip()
            if cmd == "quit":
                try:
                    s.send((json.dumps({"type": "disconnect"})+"\n").encode())
                except:
                    pass
                running = False
                s.close()
                break
            elif cmd == "online":
                with lock:
                    print_online(online)
            elif cmd == "chats":
                # request chatlist from server
                s.send((json.dumps({"type": "chatlist"}) + "\n").encode())
                time.sleep(0.1)
            elif cmd == "send":
                to = input("To (blank=all): ").strip()
                msg = input("Message: ")
                payload = {"type": "chat", "text": msg}
                if to:
                    payload["to"] = to
                    payload["group"] = False
                else:
                    payload["group"] = True
                s.send((json.dumps(payload)+"\n").encode())
            elif cmd == "delete":
                mid = input("Message ID to delete: ").strip()
                s.send((json.dumps({"type": "delete_request", "id": mid})+"\n").encode())
            else:
                print("Unknown command.")
    except KeyboardInterrupt:
        try:
            s.send((json.dumps({"type": "disconnect"})+"\n").encode())
        except:
            pass
        s.close()
        running = False

if __name__ == "__main__":
    main()
